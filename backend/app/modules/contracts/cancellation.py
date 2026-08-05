"""Calling off a contract that has not yet bound anybody.

A contract is generated the moment terms are agreed, and then sits waiting for
two signatures. That gap is real — people sign hours or days apart — and until
now nothing could happen in it except signing. A brand that changed its mind,
or a creator who got double-booked, had two options: sign something they did
not want, or go quiet and leave a half-signed contract in the other party's
list forever.

WHERE THE DOOR CLOSES, AND WHY THERE ARE TWO CONDITIONS AND NOT ONE.

  * FULLY SIGNED closes it. Both parties have put their name to these terms
    and the module's own docstring says a signed contract is immutable. A
    cancel button on it would be a way to walk out of an agreement by pressing
    something, which is what a contract exists to prevent.

  * AN ESCROW CLOSES IT TOO, with a 409, and this is the condition that has to
    be checked separately rather than assumed to follow from the first.
    Funding requires a fully signed contract today, so in practice the two
    line up — but they are different facts, and the one that matters is the
    money. Once a buyer's money is at the provider, ending the arrangement is
    a question about who is owed what, which is precisely what the dispute and
    resolution path exists to answer and has rules for: a split, a commission
    charged only on what was released, an audit log, an admin. A cancel button
    that ran alongside all of that would be a second, unaudited way for money
    to stop moving, and it would be the one somebody reached for first.

EITHER PARTY MAY DO IT, not just the buyer. Nothing is owed in either
direction yet, and a creator who has realised they cannot deliver should be
able to say so on the platform rather than by not answering. Silence is what
sends the next conversation to WhatsApp.

The cancellation is written to contract_events like every other lifecycle
event, and the other party is notified. Both matter for the same reason: this
is the one module that already keeps an audit trail, and a contract that ends
with no row saying who ended it is a contract nobody can settle an argument
from later.

A separate module from service.py, which is about generating and signing. The
dependency runs one way — router -> cancellation -> models — and escrow is
read through payments.models (MODELS ONLY, never payments.service, which
imports contracts.models and would close the circle). campaigns.editing reads
contracts the same way for the same reason.
"""
from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.contracts import models
from app.modules.notifications.service import notify
from app.modules.payments import models as payments

SIGNED_DETAIL = (
    "This contract is fully signed. Both parties agreed to it, and it is not "
    "something either side can cancel alone."
)

FUNDED_DETAIL = (
    "This contract has money in escrow. Ending it is a question about who is "
    "owed what, which is the dispute and refund path, not a cancellation."
)


def cancel_contract(db: Session, contract_id: str, user_id: str) -> dict:
    """Either party ends a contract before it binds anyone.

    Returns the cancelled contract in the same shape every other contracts
    endpoint returns, so a client can replace the row it is holding rather
    than having to refetch to find out what happened.
    """
    contract = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if contract is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            # The same rule contracts.service enforces, so the same code.
            code="contract_not_found",
            detail="Contract not found",
        )
    if user_id not in (contract.business_user_id, contract.influencer_user_id):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="contract_not_a_party",
            detail="Not a party to this contract",
        )

    if contract.status == models.CANCELLED:
        # Refused rather than treated as a no-op, so a double click does not
        # send the other party a second "this is off" for something that was
        # already off — the same call cancel_campaign makes.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="contract_already_cancelled",
            detail="This contract is already cancelled.",
        )
    if contract.status == models.SIGNED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="contract_cancel_signed",
            detail=SIGNED_DETAIL,
        )

    escrow = (
        db.query(payments.Escrow)
        .filter(payments.Escrow.contract_id == contract.id)
        .first()
    )
    if escrow is not None:
        # Checked even though funding requires a full signature and a fully
        # signed contract was already refused above. The two guards answer
        # different questions, and this is the one about money: if funding
        # ever loosens, the guard that must not have been an assumption is
        # this one.
        raise AppError(
            status.HTTP_409_CONFLICT,
            code="contract_cancel_funded",
            detail=FUNDED_DETAIL,
        )

    contract.status = models.CANCELLED
    db.add(
        models.ContractEvent(
            contract_id=contract.id, actor_user_id=user_id, event="cancelled"
        )
    )
    # The other party, not both. The person who pressed the button knows.
    other = (
        contract.influencer_user_id
        if user_id == contract.business_user_id
        else contract.business_user_id
    )
    notify(
        db,
        other,
        "contract_cancelled",
        "A contract you had not finished signing was cancelled by the other party.",
        link=f"/contracts/{contract.id}",
        params={"key": "contract_cancelled"},
    )
    db.commit()
    db.refresh(contract)
    # The service's own serialiser, so a cancelled contract is described by
    # exactly the same code as any other. fully_signed is False on it, which
    # is both true and the thing a client keys off.
    from app.modules.contracts.service import _out

    return _out(contract)

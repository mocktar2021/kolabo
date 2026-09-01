"""Funding an escrow through a real gateway, which is not one step.

THE SHAPE OF THE PROBLEM. payments.service.fund_escrow was written against a
mock: call collect(), get a reference, write a HELD escrow, done — one function,
one transaction, no way to fail halfway. A real mobile money collection is not
like that. We ask, the payer gets a USSD prompt on a handset we cannot see,
they type a PIN or they do not, and some seconds or minutes later the gateway
tells us what happened. Between those two moments the brand has closed the tab,
the request has returned, and there is no call stack left to finish the job in.

So funding is three moments and a row that survives between them:

    start    write a PENDING intent, ask the gateway, hand back a checkout url
    settle   learn the outcome, and if it succeeded, create the HELD escrow
    read     let the client ask where things stand while it waits

SETTLEMENT IS TRIGGERED FROM TWO PLACES AND MUST BE SAFE FROM BOTH. The webhook
tells us as soon as the gateway knows; the return page asks the moment the payer
lands back on it. Which arrives first is a race we do not control and do not
need to: both call the same settle_intent, both re-read the truth from the
gateway, and the second one finds the work already done. That is not a fallback
for the webhook — it is what makes a checkout that completes while the payer's
phone is on 2G still feel instant when they get back to the browser.

WHAT SETTLEMENT CHECKS BEFORE IT BELIEVES ANYTHING. Three things, and each one
is a real attack or a real bug and not a formality:

    1. the money that arrived is the money we asked for, to the franc
    2. the currency matches
    3. the contract still has no escrow

The first is the cheapest fraud against a marketplace — pay 500 against a
50,000 contract and see whether the platform notices — and the only defence is
comparing two integers on the way in.
"""
import logging

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.modules.auth.models import User
from app.modules.payments import gateway_models as gmodels
from app.modules.payments import models
from app.modules.payments.gateways import base as gwbase
from app.modules.payments.gateways import registry
from app.modules.payments.gateways.base import GatewayError

logger = logging.getLogger(__name__)

# Normalised gateway status -> intent status. A straight rename, kept explicit
# so the two vocabularies can drift apart later without a silent mismapping.
_INTENT_STATUS = {
    gwbase.PENDING: gmodels.INTENT_PENDING,
    gwbase.SUCCEEDED: gmodels.INTENT_SUCCEEDED,
    gwbase.FAILED: gmodels.INTENT_FAILED,
    gwbase.CANCELED: gmodels.INTENT_CANCELED,
}


def _intent_out(intent: gmodels.PaymentIntent) -> dict:
    return {
        "id": intent.id,
        "contract_id": intent.contract_id,
        "amount": intent.amount,
        "currency": intent.currency,
        "status": intent.status,
        "provider": intent.provider,
        "checkout_url": intent.checkout_url,
        "escrow_id": intent.escrow_id,
        "failure_reason": intent.failure_reason,
    }


def start_checkout(
    db: Session,
    business_user_id: str,
    contract_id: str,
    *,
    payer_first_name: str | None = None,
    payer_last_name: str | None = None,
    return_url: str | None = None,
) -> dict:
    """Begin funding a contract. Returns somewhere to send the payer.

    The fundability guards are payments.service's, imported rather than
    reimplemented: "contract exists, is yours, is signed, is not already
    funded" is one rule with one wording, and a second copy of it here would be
    a second place for it to go stale.
    """
    # Imported inside the function, not at module scope. service imports this
    # module for the checkout-vs-direct decision, so a top-level import here
    # would close the cycle. This is the same reason payments.service reaches
    # for deliverables.models rather than deliverables.service.
    from app.modules.payments import service as pay_service

    contract = pay_service.assert_fundable(db, business_user_id, contract_id)
    business = db.query(User).filter(User.id == business_user_id).first()
    if business is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND, code="escrow_business_not_found", detail="Account not found"
        )

    country = business.country_code
    gateway = registry.gateway_for(country, contract.rate_currency)

    # A pending intent for this contract is REUSED rather than duplicated, as
    # long as it still has a live checkout url. A brand who double-clicks Fund,
    # or reloads the checkout page, should see the same payment attempt — not
    # two open transactions at the gateway against one contract, which is how
    # somebody ends up paying twice for one collaboration and needing a refund
    # to fix it.
    existing = (
        db.query(gmodels.PaymentIntent)
        .filter(
            gmodels.PaymentIntent.contract_id == contract_id,
            gmodels.PaymentIntent.status == gmodels.INTENT_PENDING,
            gmodels.PaymentIntent.checkout_url.isnot(None),
        )
        .order_by(gmodels.PaymentIntent.created_at.desc())
        .first()
    )
    if existing is not None and existing.amount == contract.rate_amount:
        return _intent_out(existing)

    intent = gmodels.PaymentIntent(
        contract_id=contract.id,
        business_user_id=business_user_id,
        amount=contract.rate_amount,
        currency=contract.rate_currency,
        country=country,
        provider=gateway.name,
        status=gmodels.INTENT_PENDING,
    )
    db.add(intent)
    # Flushed and COMMITTED before the outbound call, deliberately. If the
    # gateway call times out after it has created a transaction on their side,
    # this row is the only evidence the attempt ever happened; without it the
    # money can move against a transaction we have no record of. A row with a
    # null provider_ref is reconcilable. Nothing is not.
    db.commit()
    db.refresh(intent)

    callback_url = return_url or settings.payment_return_url
    try:
        started = gateway.start_collection(
            amount=intent.amount,
            currency=intent.currency,
            description=f"Kolabo contract {contract.id[:8]}",
            callback_url=f"{callback_url}?intent={intent.id}",
            payer_phone=business.phone,
            payer_country=country,
            payer_first_name=payer_first_name or "Kolabo",
            payer_last_name=payer_last_name or "Client",
            payer_email=business.email,
            merchant_reference=intent.id,
            metadata={"intent_id": intent.id, "contract_id": contract.id},
        )
    except GatewayError as exc:
        logger.exception("Could not start collection for intent %s", intent.id)
        intent.failure_reason = str(exc)[:400]
        intent.updated_at = gmodels.utcnow()
        db.commit()
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            code="payments_gateway_unavailable",
            detail=(
                "We could not reach the payment provider just now. "
                "Nothing has been charged. Please try again in a moment."
            ),
        ) from exc

    intent.provider_ref = started.reference
    intent.checkout_url = started.checkout_url
    intent.updated_at = gmodels.utcnow()
    db.commit()
    db.refresh(intent)
    return _intent_out(intent)


def settle_intent(db: Session, intent: gmodels.PaymentIntent) -> gmodels.PaymentIntent:
    """Ask the gateway what happened, and act on it. Safe to call repeatedly.

    RE-READS FROM THE GATEWAY EVERY TIME rather than trusting whatever told us
    to look. A webhook body is the sender's account of events and the sender is
    whoever got a POST through to our URL; a signature narrows that but the
    signed content is still their claim. This call is ours: our connection, our
    TLS, our bearer token, their host. Everything downstream believes it
    because of that, and believes the webhook only far enough to know when to
    make it.
    """
    if intent.status != gmodels.INTENT_PENDING:
        # Already terminal. Nothing to do and nothing to re-check: an intent
        # that succeeded has an escrow, and one that failed is not going to
        # un-fail. This is the branch the loser of the webhook/return-page race
        # takes, and it is why that race is not a problem.
        return intent

    gateway = registry.gateway_by_name(intent.provider)
    if gateway is None:
        raise AppError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            code="payments_gateway_not_configured",
            detail="This payment cannot be checked right now. Please contact support.",
        )
    if not intent.provider_ref:
        # Started but never reached the gateway. It cannot succeed and it
        # cannot be checked; leaving it pending forever would show a brand a
        # payment that is permanently "in progress".
        return _fail(db, intent, "no_provider_reference")

    state = gateway.read_collection(intent.provider_ref)
    intent.provider_status = state.raw_status
    # Recorded before the branch, so it lands on every terminal path and not
    # only on the happy one. A collection that failed can still have cost us
    # something, and a fee we only store when the money arrived is a fee that
    # is missing from exactly the rows an unprofitable month is hiding in.
    #
    # GUARDED, AND THE GUARD IS THE POINT. payouts._mark has carried the same
    # `if fee is not None` since it was written, for the same reason; this
    # function was the copy that did not, and it needs it slightly more often
    # than the payout leg does.
    #
    # A PENDING INTENT IS SETTLED MORE THAN ONCE, by design and by the
    # docstring above: the webhook and the return page both land here, and
    # get_intent settles on every poll while the payer is still deciding. Each
    # of those is a fresh read_collection, and a read that does not mention a
    # fee is the gateway staying silent — not the gateway telling us the fee is
    # gone. Assigning unconditionally let the quietest read in that sequence
    # delete a cost already recorded, and since the last read before the intent
    # turns terminal is the one that sticks, the deletion was permanent.
    #
    # None is not zero here, and it is not "unchanged" either. It means we
    # learned nothing this time, so we keep what we knew. A reported number
    # still wins, including a corrected one — the guard is on the gateway's
    # silence, not on whether we already hold a value.
    if state.fee is not None:
        intent.gateway_fee = state.fee
    mapped = _INTENT_STATUS.get(state.status, gmodels.INTENT_PENDING)

    if mapped != gmodels.INTENT_SUCCEEDED:
        intent.status = mapped
        intent.failure_reason = state.failure_reason
        intent.updated_at = gmodels.utcnow()
        db.commit()
        db.refresh(intent)
        return intent

    # ---- it says the money arrived. Check that it is OUR money. ----
    if state.amount != intent.amount or state.currency != intent.currency:
        # The single cheapest attack on a marketplace checkout, and the one
        # nobody catches by reading the happy path: pay a fraction of the
        # contract and see whether the platform funds the escrow anyway.
        # Refused loudly, logged loudly, and NOT settled — the money is at the
        # gateway and a human reconciles it, which is the right amount of
        # friction for something that should never happen.
        logger.error(
            "Amount mismatch settling intent %s: expected %s %s, gateway says %s %s",
            intent.id,
            intent.amount,
            intent.currency,
            state.amount,
            state.currency,
        )
        return _fail(db, intent, "amount_mismatch")

    from app.modules.payments import service as pay_service

    existing_escrow = (
        db.query(models.Escrow).filter(models.Escrow.contract_id == intent.contract_id).first()
    )
    if existing_escrow is not None:
        # Funded by some other attempt. The escrow is the unique thing, not the
        # intent, so this one attaches itself to the escrow that exists and
        # records success rather than trying to create a second one. That keeps
        # a double-paid contract visible in the intents table — two succeeded
        # intents, one escrow — which is exactly what a refund decision needs
        # to see.
        intent.escrow_id = existing_escrow.id
        intent.status = gmodels.INTENT_SUCCEEDED
        intent.settled_at = gmodels.utcnow()
        intent.updated_at = gmodels.utcnow()
        db.commit()
        db.refresh(intent)
        return intent

    escrow = pay_service.hold_funds(
        db,
        contract_id=intent.contract_id,
        provider_name=intent.provider,
        fund_ref=intent.provider_ref,
    )
    intent.escrow_id = escrow.id
    intent.status = gmodels.INTENT_SUCCEEDED
    intent.settled_at = gmodels.utcnow()
    intent.updated_at = gmodels.utcnow()
    db.commit()
    db.refresh(intent)
    return intent


def _fail(db: Session, intent: gmodels.PaymentIntent, reason: str) -> gmodels.PaymentIntent:
    intent.status = gmodels.INTENT_FAILED
    intent.failure_reason = reason
    intent.updated_at = gmodels.utcnow()
    db.commit()
    db.refresh(intent)
    return intent


def get_intent(db: Session, user_id: str, intent_id: str) -> dict:
    """Where a payment stands, for the party who started it.

    Settles on read. The return page calls this the instant the payer lands
    back on it, which in practice is the fastest path to a funded escrow — the
    webhook is the safety net for the case where the payer never comes back.
    """
    intent = db.query(gmodels.PaymentIntent).filter(gmodels.PaymentIntent.id == intent_id).first()
    if intent is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND, code="payment_intent_not_found", detail="Payment not found"
        )
    if intent.business_user_id != user_id:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="payment_intent_not_yours",
            detail="Not your payment",
        )
    if intent.status == gmodels.INTENT_PENDING:
        try:
            intent = settle_intent(db, intent)
        except GatewayError:
            # A read that cannot reach the gateway answers "still pending"
            # rather than failing the page. The client polls; the webhook is
            # coming; and telling a brand their payment errored because OUR
            # outbound call timed out would be a lie about their money.
            logger.warning("Could not refresh intent %s from the gateway", intent.id)
    return _intent_out(intent)

"""Payments and escrow business logic (Epic G). Highest-risk module.

KOL-28: fund an escrow via Mobile Money. Funding requires a fully signed
contract (the Epic E gate), moves money into a held state through the provider
abstraction, and never handles raw PINs.
KOL-36: release the escrow to the influencer once the business confirms
delivery, deducting commission at release, or auto release after a timeout if
the business does not respond.
KOL-37: a dispute freezes the escrow and an admin settles it. Raising one and
the response window live in payments/disputes.py; the admin's split decision
lives in payments/resolution.py. What stays here is the ordinary money path
and the two things both of those reuse: commission_for and _release.

No real money moves: all provider calls go through the mock provider until a real
Mobile Money provider is contracted.
"""
import logging
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.models import User
from app.modules.auth.referrals import award_for_completed_order
from app.modules.contracts import models as contracts
# MODELS ONLY, never deliverables.service — that module imports THIS one, and
# taking its service here would close the circle. Its models import nothing but
# Base, so this direction is safe. contracts/cancellation.py reads payments the
# same way for the same reason.
from app.modules.deliverables import models as deliverables
from app.modules.notifications.service import notify
from app.modules.payments import models, provider

logger = logging.getLogger(__name__)

payment_provider: provider.MobileMoneyProvider = provider.default_provider


def commission_for(amount: int) -> int:
    """The platform's cut of money that actually reached a creator.

    One definition, used by the ordinary release and by a disputed split, so
    the two can never end up disagreeing about what the fee on a payment is.
    Integer division in minor units: the rounding remainder stays with the
    creator, which is the side it should stay with.
    """
    return amount * settings.commission_bps // 10000


def _out(escrow: models.Escrow) -> dict:
    return {
        "id": escrow.id,
        "contract_id": escrow.contract_id,
        "campaign_id": escrow.campaign_id,
        "business_user_id": escrow.business_user_id,
        "influencer_user_id": escrow.influencer_user_id,
        "amount": escrow.amount,
        "currency": escrow.currency,
        "commission_amount": escrow.commission_amount,
        "status": escrow.status,
    }


def _event(db: Session, escrow: models.Escrow, actor_id: str, event: str) -> None:
    db.add(models.EscrowEvent(escrow_id=escrow.id, actor_id=actor_id, event=event))


def fund_escrow(db: Session, business_user_id: str, contract_id: str) -> dict:
    contract = db.query(contracts.Contract).filter(contracts.Contract.id == contract_id).first()
    if contract is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
    if contract.business_user_id != business_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your contract")
    if contract.status != contracts.SIGNED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contract must be fully signed before funding")
    if db.query(models.Escrow).filter(models.Escrow.contract_id == contract_id).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This contract is already funded")

    business = db.query(User).filter(User.id == business_user_id).first()
    fund_ref = payment_provider.collect(business.phone, contract.rate_amount, contract.rate_currency)

    now = models.utcnow()
    escrow = models.Escrow(
        contract_id=contract.id,
        campaign_id=contract.campaign_id,
        business_user_id=contract.business_user_id,
        influencer_user_id=contract.influencer_user_id,
        amount=contract.rate_amount,
        currency=contract.rate_currency,
        provider="mock",
        provider_fund_ref=fund_ref,
        status=models.HELD,
        held_at=now,
        due_release_at=now + timedelta(days=settings.auto_release_days),
    )
    db.add(escrow)
    db.flush()
    _event(db, escrow, business_user_id, "funded")
    notify(db, escrow.influencer_user_id, "payment", "Funds are held in escrow for your collaboration",
           link=f"/contracts/{escrow.contract_id}", params={"key": "escrow_funded_creator"})
    notify(db, escrow.business_user_id, "payment", "Your payment is held in escrow",
           link=f"/contracts/{escrow.contract_id}", params={"key": "escrow_funded_brand"})
    db.commit()
    db.refresh(escrow)
    return _out(escrow)


def _award_referral_credits(db: Session, escrow: models.Escrow) -> None:
    """Referral rewards for a completed order — deliberately unable to fail.

    A released escrow is an order completed: the payout has ALREADY been made
    at the provider by the time this runs. NOTHING HERE MAY EVER PROPAGATE.
    A bug in the rewards code must not turn a successful payment into a failed
    request, because the two failures are not comparable — missing credit is a
    support ticket somebody can fix later, while a release that 500s is a
    creator who was not paid and an escrow stuck in a state nobody trusts.
    Hence the bare except: it is not laziness, it is the requirement.

    Both parties are offered up, not just the influencer: a creator's code
    brings in businesses too, so either side of the contract may be somebody's
    referee.
    """
    try:
        award_for_completed_order(
            db,
            (escrow.influencer_user_id, escrow.business_user_id),
            escrow.contract_id,
        )
    except Exception:  # noqa: BLE001 - swallowing is the point; see the docstring
        logger.exception("Referral credit award failed for escrow %s", escrow.id)


def _release(db: Session, escrow: models.Escrow, actor_id: str) -> None:
    influencer = db.query(User).filter(User.id == escrow.influencer_user_id).first()
    commission = commission_for(escrow.amount)
    payout_amount = escrow.amount - commission
    payout_ref = payment_provider.payout(influencer.phone, payout_amount, escrow.currency)
    escrow.commission_amount = commission
    escrow.provider_payout_ref = payout_ref
    escrow.status = models.RELEASED
    escrow.resolved_at = models.utcnow()
    _event(db, escrow, actor_id, "released")
    notify(db, escrow.influencer_user_id, "payment", "Escrow released, your payout is on the way",
           link=f"/contracts/{escrow.contract_id}", params={"key": "escrow_released_creator"})
    notify(db, escrow.business_user_id, "payment", "Escrow released to the influencer",
           link=f"/contracts/{escrow.contract_id}", params={"key": "escrow_released_brand"})
    # Last, and only once the release itself is settled in the session: this is
    # the single point every UNDISPUTED release passes through — business
    # confirmation and auto release after timeout — so the reward hangs off
    # order completion rather than off one button. A disputed escrow is
    # settled by resolution.resolve_dispute, which makes the same call for the
    # same reason when any money reached the creator.
    _award_referral_credits(db, escrow)


def release_escrow(db: Session, business_user_id: str, escrow_id: str) -> dict:
    escrow = db.query(models.Escrow).filter(models.Escrow.id == escrow_id).first()
    if escrow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escrow not found")
    if escrow.business_user_id != business_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the business can confirm delivery")
    if escrow.status != models.HELD:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Escrow is not in a held state")
    _release(db, escrow, business_user_id)
    db.commit()
    db.refresh(escrow)
    return _out(escrow)


def run_due_auto_releases(db: Session, now=None) -> int:
    """Pay out escrows whose review window closed with the brand saying nothing.

    AUTO-RELEASE NOW MEANS "REVIEWED BY SILENCE", AND ONLY THAT. It used to
    mean something much weaker, because due_release_at was set at FUNDING
    (held_at + auto_release_days) and nothing here asked whether the creator
    had delivered: an escrow funded and then forgotten paid itself out seven
    days later whether or not any work existed. The brand's protection was a
    clock that started before there was anything to look at.

    So the sweep now takes escrows with an OPEN submission on their contract.
    That single filter carries three rules at once, because a submission
    leaves the open set the moment it is answered:

      * NOTHING SUBMITTED -> never auto-releases. Un-delivered money waits.
        A brand whose creator has gone quiet has the dispute path, which is
        where a claim on frozen money belongs.
      * CHANGES REQUESTED -> the clock stops. Work the brand has rejected must
        not quietly auto-pay while the creator is redoing it; the next
        submission opens a fresh window (deliverables.service.submit).
      * WITHDRAWN -> the clock stops, for the plainest version of the same
        reason: there is nothing in front of the brand to review.

    A submission that IS open and past its window still releases, which is the
    point — a creator who delivered is not held hostage by a brand that never
    clicks anything.
    """
    now = now or models.utcnow()
    # The contracts with work actually awaiting an answer. A subquery rather
    # than a join, so the escrow rows come back unduplicated even if a
    # contract somehow carried more than one open submission.
    awaiting_review = select(deliverables.DeliverableSubmission.contract_id).where(
        deliverables.DeliverableSubmission.status.in_(deliverables.OPEN_STATUSES)
    )
    due = (
        db.query(models.Escrow)
        .filter(
            models.Escrow.status == models.HELD,
            models.Escrow.due_release_at <= now,
            models.Escrow.contract_id.in_(awaiting_review),
        )
        .all()
    )
    for escrow in due:
        _release(db, escrow, "system_auto_release")
    db.commit()
    return len(due)


def get_escrow(db: Session, user_id: str, escrow_id: str) -> dict:
    escrow = db.query(models.Escrow).filter(models.Escrow.id == escrow_id).first()
    if escrow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escrow not found")
    if user_id not in (escrow.business_user_id, escrow.influencer_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this escrow")
    return _out(escrow)


def get_escrow_by_contract(db: Session, user_id: str, contract_id: str) -> dict:
    escrow = db.query(models.Escrow).filter(models.Escrow.contract_id == contract_id).first()
    if escrow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No escrow for this contract")
    if user_id not in (escrow.business_user_id, escrow.influencer_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this escrow")
    return _out(escrow)

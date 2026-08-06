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

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
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
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="escrow_contract_not_found",
            detail="Contract not found",
        )
    if contract.business_user_id != business_user_id:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="escrow_not_your_contract",
            detail="Not your contract",
        )
    if contract.status != contracts.SIGNED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="escrow_contract_not_signed",
            detail="Contract must be fully signed before funding",
        )
    if db.query(models.Escrow).filter(models.Escrow.contract_id == contract_id).first() is not None:
        raise AppError(
            status.HTTP_409_CONFLICT,
            code="escrow_already_funded",
            detail="This contract is already funded",
        )

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


def _refund(db: Session, escrow: models.Escrow, actor_id: str) -> None:
    """Give the whole amount back. The mirror of _release, and NO COMMISSION.

    The platform's fee is a share of a collaboration that happened. Nothing
    happened here, so taking a cut of a refund would be charging a brand for
    the privilege of not receiving anything — which is both wrong and the
    fastest way to make a buyer never fund an escrow again.

    Whole amounts only. A split belongs to payments.resolution, where an admin
    has read a dispute and decided who is owed what; this path has no such
    judgement behind it and must not pretend to one. If some of the work
    arrived, this is not the function for it — see run_non_delivery_refunds
    for why an escrow with any submission against it never reaches here.
    """
    business = db.query(User).filter(User.id == escrow.business_user_id).first()
    refund_ref = payment_provider.payout(business.phone, escrow.amount, escrow.currency)
    escrow.provider_payout_ref = refund_ref
    escrow.status = models.REFUNDED
    escrow.resolved_at = models.utcnow()
    _event(db, escrow, actor_id, "refunded")
    notify(
        db,
        escrow.business_user_id,
        "payment",
        "Nothing was delivered, so your escrow has been refunded in full.",
        link=f"/contracts/{escrow.contract_id}",
        params={"key": "escrow_refunded_brand"},
    )
    notify(
        db,
        escrow.influencer_user_id,
        "payment",
        "The delivery window closed with nothing submitted, so the escrow was refunded.",
        link=f"/contracts/{escrow.contract_id}",
        params={"key": "escrow_refunded_creator"},
    )
    # No referral credit. _award_referral_credits hangs off a COMPLETED order,
    # and this is the opposite of one.


def release_escrow(db: Session, business_user_id: str, escrow_id: str) -> dict:
    escrow = db.query(models.Escrow).filter(models.Escrow.id == escrow_id).first()
    if escrow is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="escrow_not_found",
            detail="Escrow not found",
        )
    if escrow.business_user_id != business_user_id:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="escrow_release_business_only",
            detail="Only the business can confirm delivery",
        )
    if escrow.status != models.HELD:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="escrow_not_held",
            detail="Escrow is not in a held state",
        )
    # HARD GATE (Deliverables D2): confirming delivery is APPROVING what the
    # creator handed in, so it needs a hand-in to approve. Before this, the
    # button released money while recording nothing about what it paid for —
    # and if a submission WAS open it left it sitting unanswered against an
    # escrow that had already paid out, so deliverable state and escrow state
    # told two different stories. Approval and release are now one act on this
    # path too, exactly as they are in deliverables.service.approve.
    #
    # deliverables.MODELS only, never its service: payments.service is the
    # bottom of that dependency, and run_due_auto_releases reads the same table
    # the same way. At most one submission is open per contract (enforced in
    # deliverables.service.submit), so "the open one" is unambiguous;
    # newest-first is belt-and-braces.
    submission = (
        db.query(deliverables.DeliverableSubmission)
        .filter(
            deliverables.DeliverableSubmission.contract_id == escrow.contract_id,
            deliverables.DeliverableSubmission.status.in_(deliverables.OPEN_STATUSES),
        )
        .order_by(deliverables.DeliverableSubmission.created_at.desc())
        .first()
    )
    if submission is None:
        # No open hand-in: either nothing was ever submitted, or the only
        # attempts are closed (changes requested, withdrawn). Either way there
        # is nothing to confirm, and a business does not pay out of the
        # deliverable flow — the money waits for the creator to deliver.
        # Legacy and off-platform escrows with no submission resolve through
        # auto-release, the non-delivery refund, or a dispute, not here.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="escrow_release_needs_submission",
            detail=(
                "There is nothing to confirm yet: the creator has not submitted "
                "any work against this escrow. Once they submit it, confirming "
                "delivery approves that submission and releases the payment."
            ),
        )
    # Approval and payout in one transaction — the same pairing approve() makes,
    # through the same _release, so commission, the payout, the escrow event and
    # the referral hook stay in exactly one place.
    deliverables.mark_approved(submission, business_user_id)
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


def _undelivered_escrows(db: Session):
    """Held escrows on contracts that have NEVER had a submission against them.

    NEVER, in any status — not "no open submission", which is what the
    auto-release sweep asks. The difference is the whole boundary between the
    two jobs and it is deliberate:

      * A contract with no submission row at all is a NON-DELIVERY. Nobody has
        offered anything, so there is nothing to review, nothing to dispute
        about the work, and the only honest ending is the brand's money going
        back.
      * A contract with ANY submission row — open, approved, changes
        requested, even withdrawn — has had work offered on it. What happens
        next is a question about that work: the brand reviews it, or one of
        them opens a dispute. It is not this job's business, and a creator who
        submitted and then withdrew must not have their escrow refunded out
        from under them by a clock.

    That also makes the two sweeps disjoint by construction rather than by
    both of them remembering to check. An escrow is in exactly one of the two
    sets, and the set it is in cannot change back.
    """
    ever_submitted = select(deliverables.DeliverableSubmission.contract_id)
    return (
        db.query(models.Escrow, contracts.Contract)
        .join(contracts.Contract, contracts.Contract.id == models.Escrow.contract_id)
        .filter(
            models.Escrow.status == models.HELD,
            models.Escrow.contract_id.not_in(ever_submitted),
        )
    )


def run_non_delivery_refunds(db: Session, now=None) -> dict:
    """Warn, then refund, an escrow nobody ever delivered against.

    THIS IS THE HOLE THE AUTO-RELEASE FIX OPENED. Anchoring auto-release to a
    submission was right — money must not pay itself out for work that does
    not exist — but it left the opposite case with no ending at all: a brand
    funds an escrow, the creator goes quiet, and the money sits held forever.
    Nothing refunded it, nothing chased it, and neither party was told
    anything. "Forever" is not a state a payment system may have.

    THE DEADLINE IS THE CREATOR'S OWN PROMISE. contract.timeline_days is what
    they quoted and what the brand accepted, so the delivery date is
    held_at + timeline_days: the clock starts at funding because that is when
    the creator may actually begin — deliverables.submit refuses work on an
    unfunded contract. Derived rather than stored, because both halves are
    immutable once signed, and deriving it means escrows funded BEFORE this
    shipped are covered too. Those are exactly the ones stuck today.

    TWO STAGES, because refunding without warning is how you turn a late
    creator into a dispute. At the deadline both parties are told and the
    escrow is stamped; only after non_delivery_grace_days more does the money
    move. A creator who submits anything in between leaves the set entirely
    and no refund happens — see _undelivered_escrows.

    Disputed escrows are never touched: the filter is HELD only, so a frozen
    escrow belongs to the dispute path from the moment it freezes.
    """
    now = now or models.utcnow()
    warned = 0
    refunded = 0

    for escrow, contract in _undelivered_escrows(db).filter(
        models.Escrow.non_delivery_warned_at.is_(None)
    ):
        if escrow.held_at + timedelta(days=contract.timeline_days) <= now:
            escrow.non_delivery_warned_at = now
            _event(db, escrow, "system_non_delivery", "delivery_overdue")
            notify(
                db,
                escrow.influencer_user_id,
                "payment",
                (
                    "The delivery date on this contract has passed with nothing submitted. "
                    f"The escrow is refunded to the brand in {settings.non_delivery_grace_days} "
                    "days unless you submit your work."
                ),
                link=f"/contracts/{escrow.contract_id}",
                params={"key": "delivery_overdue_creator", "days": settings.non_delivery_grace_days},
            )
            notify(
                db,
                escrow.business_user_id,
                "payment",
                (
                    "The delivery date on this contract has passed with nothing submitted. "
                    f"Your escrow is refunded automatically in {settings.non_delivery_grace_days} "
                    "days if nothing arrives."
                ),
                link=f"/contracts/{escrow.contract_id}",
                params={"key": "delivery_overdue_brand", "days": settings.non_delivery_grace_days},
            )
            warned += 1

    # Read AFTER the warning pass and with its own cutoff, so an escrow warned
    # in this same run cannot also be refunded by it: the grace period has to
    # be time somebody could actually have used, not a formality a single
    # sweep satisfies on its own.
    #
    # That holds whether or not the session autoflushes. Unflushed, the rows
    # just warned still read as NULL and fail the IS NOT NULL filter; flushed,
    # they carry `now` and fail the cutoff. Two different reasons, same
    # answer — worth knowing, because a test that turns autoflush on or off
    # would otherwise look like it was testing this.
    cutoff = now - timedelta(days=settings.non_delivery_grace_days)
    for escrow, _contract in _undelivered_escrows(db).filter(
        models.Escrow.non_delivery_warned_at.is_not(None),
        models.Escrow.non_delivery_warned_at <= cutoff,
    ):
        _refund(db, escrow, "system_non_delivery")
        refunded += 1

    db.commit()
    return {"warned": warned, "refunded": refunded}


def get_escrow(db: Session, user_id: str, escrow_id: str) -> dict:
    escrow = db.query(models.Escrow).filter(models.Escrow.id == escrow_id).first()
    if escrow is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="escrow_not_found",
            detail="Escrow not found",
        )
    if user_id not in (escrow.business_user_id, escrow.influencer_user_id):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="escrow_not_a_party",
            detail="Not a party to this escrow",
        )
    return _out(escrow)


def get_escrow_by_contract(db: Session, user_id: str, contract_id: str) -> dict:
    escrow = db.query(models.Escrow).filter(models.Escrow.contract_id == contract_id).first()
    if escrow is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="escrow_none_for_contract",
            detail="No escrow for this contract",
        )
    if user_id not in (escrow.business_user_id, escrow.influencer_user_id):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="escrow_not_a_party",
            detail="Not a party to this escrow",
        )
    return _out(escrow)

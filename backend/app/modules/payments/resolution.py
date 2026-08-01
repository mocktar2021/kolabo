"""How an admin ends a dispute: a split, and a fee that follows the work.

THE OUTCOME IS TWO FIGURES, NOT A VERDICT. The old resolution was release or
refund, and real disputes almost never fit either: the work was late but it
ran, two of three deliverables landed, the reel was posted to the wrong
account and then reposted. A binary outcome forces a wrong answer on
somebody — the creator loses everything for a partial failure, or the buyer
pays in full for a partial delivery — and the loser of that coin flip is the
one who stops using the platform. So the admin says how much goes each way.

THEY MUST ADD UP TO THE ESCROW, EXACTLY. Not at most, not about. The escrow is
money that already left the buyer's wallet and sits at the provider; anything
less invents a remainder nobody owns and anything more pays out money that was
never collected. A rounding gap here is not a display bug, it is a real loss
that only surfaces at reconciliation, so it is refused at the door with both
figures and the total named.

COMMISSION IS CHARGED ON THE RELEASED PART ONLY. Refunded money never earned a
fee: the platform's cut is a share of a transaction that happened, and the
refunded half is the part that did not.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.admin.models import AdminActionLog
from app.modules.auth.models import User
from app.modules.notifications.service import notify
from app.modules.payments import disputes, models
from app.modules.payments import service as payments_service


def _checked_amounts(escrow: models.Escrow, released: int, refunded: int) -> None:
    if released < 0 or refunded < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Neither amount can be negative.",
        )
    total = released + refunded
    if total != escrow.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"released_amount ({released}) and refunded_amount ({refunded}) "
                f"add up to {total}, but the escrow holds {escrow.amount} "
                f"{escrow.currency}. Money must not be invented or destroyed."
            ),
        )


def resolve_dispute(db: Session, admin_id: str, escrow_id: str, payload) -> dict:
    """Settle a frozen escrow by splitting it, and close the dispute with it.

    Either figure may be zero, which reproduces exactly the old full-release
    and full-refund outcomes — they were never wrong, they were just the only
    two points on a line.
    """
    escrow = disputes.load_escrow(db, escrow_id)
    if escrow.status != models.DISPUTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Escrow is not under dispute"
        )
    # The OPEN one, specifically. An escrow can carry several dispute rows
    # over its life now that escrow_id is indexed rather than unique — one
    # withdrawn, then a second raised when the work later failed — and asking
    # by escrow_id alone would hand back whichever row came first and write
    # this split onto a case that closed weeks ago.
    dispute = disputes.open_dispute_for_escrow(db, escrow.id)
    if dispute is None:
        # A frozen escrow always has an open dispute: the freeze and the row
        # are written in the same transaction, and every path that closes one
        # unfreezes the other. So this is corrupt state rather than an old
        # record. Settling it anyway would write two amounts against a claim
        # nobody can read — the audit trail would say money moved and never
        # say why.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This escrow is frozen with no open dispute attached. Report it before settling.",
        )

    released = payload.released_amount
    refunded = payload.refunded_amount
    _checked_amounts(escrow, released, refunded)

    # The fee, on the released part only, through the one definition of it.
    commission = payments_service.commission_for(released)
    payout_amount = released - commission

    creator_ref = None
    if released > 0:
        influencer = (
            db.query(User).filter(User.id == escrow.influencer_user_id).first()
        )
        creator_ref = payments_service.payment_provider.payout(
            influencer.phone, payout_amount, escrow.currency
        )
        payments_service._event(db, escrow, admin_id, "released")
    refund_ref = None
    if refunded > 0:
        business = db.query(User).filter(User.id == escrow.business_user_id).first()
        refund_ref = payments_service.payment_provider.payout(
            business.phone, refunded, escrow.currency
        )
        payments_service._event(db, escrow, admin_id, "refunded")

    now = models.utcnow()
    escrow.commission_amount = commission
    # One column, and a split can be two movements. The creator's payout is
    # the reference worth keeping when there is one, because it is the leg a
    # support ticket asks about; both legs are on escrow_events either way,
    # which is the record reconciliation actually reads.
    escrow.provider_payout_ref = creator_ref or refund_ref
    # RELEASED the moment anything reached the creator, however little.
    # "Refunded" has to mean the buyer got their money back, and a buyer who
    # got 40 percent of it did not.
    escrow.status = models.RELEASED if released > 0 else models.REFUNDED
    escrow.resolved_at = now

    dispute.status = models.DISPUTE_RESOLVED
    dispute.resolved_at = now
    dispute.resolved_by = admin_id
    dispute.resolution = payload.note
    dispute.released_amount = released
    dispute.refunded_amount = refunded
    payments_service._event(db, escrow, admin_id, "dispute_resolved")

    # Both parties, with the figures. "Your dispute was resolved" with no
    # numbers in it is a message that generates the support ticket it was
    # meant to prevent.
    notify(
        db,
        escrow.influencer_user_id,
        "payment",
        f"Your dispute was decided: {payout_amount} {escrow.currency} is on its way "
        f"to you and {refunded} {escrow.currency} was refunded to the brand.",
    )
    notify(
        db,
        escrow.business_user_id,
        "payment",
        f"Your dispute was decided: {refunded} {escrow.currency} is being refunded "
        f"to you and {released} {escrow.currency} was released to the creator.",
    )

    db.add(
        AdminActionLog(
            admin_id=admin_id,
            action="dispute_resolved",
            target_type="escrow",
            target_id=escrow.id,
            reason=payload.note,
        )
    )

    # THE REFERRAL HOOK. A split counts as a completed order when ANY money
    # reached the creator, and not at all when it was fully refunded. The
    # reward exists to pay for transactions that cleared escrow rather than
    # for accounts, and a partial payment is still a job somebody did and got
    # paid for; a full refund is the transaction being unwound, and crediting
    # it would make "dispute, then refund" a free way to mint credit. Same
    # call service._release makes, for the same reason, and it is just as
    # unable to fail: the payout has already happened at the provider.
    if released > 0:
        payments_service._award_referral_credits(db, escrow)

    db.commit()
    db.refresh(dispute)
    db.refresh(escrow)
    return disputes.dispute_out(db, dispute, escrow)

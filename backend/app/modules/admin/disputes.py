"""The dispute queue an admin actually works from.

Separate from admin/service.py because that file is the verification queue and
the dashboard, and this is a third queue with its own joins; the dashboard
already only wants a COUNT of these, which it has.

ORDERING IS THE FEATURE. awaiting_admin first, because those are the cases
where the two parties have had their window and it did not settle anything —
they are the only ones an admin is supposed to decide today. awaiting_response
cases are shown after, so the desk can see what is coming without being able
to reach into a conversation that is still the parties' own. Within each
group, oldest first: frozen money is somebody not being paid, and the fair
order for that is the order it arrived in.
"""
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.identity import creator_identities
from app.modules.profiles.models import BusinessProfile


def list_dispute_queue(db: Session) -> list[dict]:
    """Open disputes, worst-waiting first, with everything needed to triage.

    The counts and the names are two grouped queries and one identity lookup
    for the whole page rather than three per row — the per-row version is what
    turns a fifty-case queue into two hundred round trips.
    """
    # Imported here, as dashboard_summary does: admin is reachable from the
    # payments router, and keeping the payments import inside the call means
    # the module graph cannot close on itself however the packages move.
    from app.modules.payments import models as payments

    queue_statuses = (payments.AWAITING_ADMIN, payments.AWAITING_RESPONSE)
    waiting_first = case(
        (payments.Dispute.status == payments.AWAITING_ADMIN, 0), else_=1
    )
    rows = (
        db.query(payments.Dispute, payments.Escrow)
        .join(payments.Escrow, payments.Escrow.id == payments.Dispute.escrow_id)
        .filter(payments.Dispute.status.in_(queue_statuses))
        .order_by(waiting_first.asc(), payments.Dispute.created_at.asc())
        .all()
    )
    if not rows:
        return []

    message_counts = dict(
        db.query(
            payments.DisputeMessage.dispute_id,
            func.count(payments.DisputeMessage.id),
        )
        .filter(
            payments.DisputeMessage.dispute_id.in_([d.id for d, _ in rows])
        )
        .group_by(payments.DisputeMessage.dispute_id)
        .all()
    )

    # creator_identities is the one shape every list that shows a creator
    # spends, so the queue shows the same name and photo the buyer saw when
    # they booked. It only answers for creators — there is no InfluencerProfile
    # behind a brand — so the business side is its company name, which is the
    # equivalent fact about that party.
    identities = creator_identities(db, [e.influencer_user_id for _, e in rows])
    companies = dict(
        db.query(BusinessProfile.user_id, BusinessProfile.company_name)
        .filter(
            BusinessProfile.user_id.in_({e.business_user_id for _, e in rows})
        )
        .all()
    )

    return [
        {
            "id": dispute.id,
            "escrow_id": escrow.id,
            "status": dispute.status,
            "reason": dispute.reason,
            "amount": escrow.amount,
            "currency": escrow.currency,
            "opened_by_user_id": dispute.opened_by_user_id,
            "business_user_id": escrow.business_user_id,
            "business_name": companies.get(escrow.business_user_id),
            "creator_user_id": escrow.influencer_user_id,
            "creator_name": (
                identities.get(escrow.influencer_user_id) or {}
            ).get("display_name"),
            "message_count": message_counts.get(dispute.id, 0),
            "respond_by": dispute.respond_by.isoformat(),
            "created_at": dispute.created_at.isoformat(),
        }
        for dispute, escrow in rows
    ]

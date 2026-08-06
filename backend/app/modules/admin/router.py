"""Admin operations (Epic B verification queue, Epic I dashboard and config).

Admin identity is a real login: a bearer token belonging to a user whose
is_admin is set, which app.modules.auth.admins keeps in step with a configured
list of phone numbers on every boot. It replaced an X-Admin-Id header that
accepted any non-empty string — a placeholder that was fine until it stood in
front of moving money.

Role based access control beyond the single is_admin flag is still not built.
There is one kind of admin and they can do everything on this router.
"""
from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.modules.admin import disputes, service
from app.modules.auth.deps import get_current_user_id
from app.modules.auth.models import User
from app.modules.campaigns import orders as campaign_orders
from app.modules.config import service as config_service
from app.modules.config.schemas import CountryConfigIn, CountryConfigOut, EnabledIn
from app.modules.payments import disputes as payments_disputes
from app.modules.payments import service as payments_service

router = APIRouter()


def get_current_admin(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> str:
    """The caller, proved to be an admin, or a refusal.

    This used to read an X-Admin-Id header and return whatever was in it. That
    was not authentication — it was a string anybody could type, in front of
    an endpoint that splits a disputed escrow. See app.modules.auth.admins for
    what replaced it and why the admin list lives in deployment config.

    401 vs 403 is the ordinary distinction and both halves matter here. A
    missing or invalid token is get_current_user_id's answer (401: we do not
    know who you are). A valid token belonging to somebody who is not an admin
    is 403 — we know exactly who you are, and the answer is still no.

    Returns the USER ID, so AdminActionLog.admin_id and Dispute.resolved_by
    now name an account somebody logged into rather than a header value.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_admin:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="admin_not_authorised",
            detail="This account is not an administrator",
        )
    return user.id


@router.get("/dashboard")
def dashboard_summary(db: Session = Depends(get_db), admin_id: str = Depends(get_current_admin)):
    """Queue counts across verification, disputes, payouts, and reports. KOL-33."""
    return service.dashboard_summary(db)


@router.post("/jobs/run")
def run_scheduled_jobs(db: Session = Depends(get_db), admin_id: str = Depends(get_current_admin)):
    """Run every time-based job, now, and say what each one did.

    THERE IS STILL NO SCHEDULER, and this is the honest interim answer rather
    than a fourth job quietly waiting for one. Four things in this codebase
    only happen when time passes — an order lapsing, a review window closing,
    a dispute nobody answered reaching the queue, and now an escrow nobody
    delivered against going back to the buyer — and every one of them was a
    function that nothing called. A rule that never runs is not a rule; it is
    a comment.

    So: one endpoint, behind the same admin login as the rest of this router,
    that an operator or an external cron can hit. `curl -XPOST -H
    'Authorization: Bearer <admin token>' .../admin/jobs/run` is a scheduler,
    for a pilot.

    IDEMPOTENT BY CONSTRUCTION, which is what makes that safe. Every job
    filters on the state it is about to change — a lapsed order is no longer
    open, a released escrow is no longer held, a warned escrow carries the
    stamp that says so — so running this twice in a minute does the work once
    and reports zero the second time. Nothing here depends on being called on
    a schedule, only on being called.

    The counts come back per job rather than as a total, because "17" tells an
    operator nothing and "3 escrows refunded" tells them to go and look.
    """
    return {
        "orders_expired": campaign_orders.expire_stale_orders(db),
        "escrows_auto_released": payments_service.run_due_auto_releases(db),
        "non_delivery": payments_service.run_non_delivery_refunds(db),
        "disputes_escalated": payments_disputes.escalate_stale_disputes(db),
    }


@router.get("/disputes")
def dispute_queue(db: Session = Depends(get_db), admin_id: str = Depends(get_current_admin)):
    """The dispute queue: cases whose response window closed come first.

    Oldest first within each group, with the amount at stake, the reason, both
    parties and how much has been said. The full case, including the thread
    and its evidence, is GET /payments/disputes/{id}, which an admin may read.
    KOL-37.
    """
    return disputes.list_dispute_queue(db)


@router.get("/countries", response_model=list[CountryConfigOut])
def list_countries(
    enabled_only: bool = False,
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """List configured countries from the database. KOL-34."""
    return config_service.list_countries(db, enabled_only)


@router.post("/countries", response_model=CountryConfigOut, status_code=201)
def upsert_country(
    payload: CountryConfigIn,
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """Add or edit a country as config, no deploy required. KOL-34."""
    return config_service.upsert_country(db, admin_id, payload.model_dump())


@router.post("/countries/{code}/enabled", response_model=CountryConfigOut)
def set_country_enabled(
    code: str,
    payload: EnabledIn,
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """Turn a market on or off. KOL-34."""
    return config_service.set_enabled(db, admin_id, code, payload.enabled)


@router.get("/verification-queue")
def verification_queue(
    item_type: str | None = None,
    item_status: str | None = None,
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """List pending verification documents and social accounts. KOL-18."""
    return service.list_verification_queue(db, item_type, item_status)


@router.post("/verification-documents/{doc_id}/decision")
def decide_document(
    doc_id: str,
    decision: str = Body(..., embed=True),
    reason: str | None = Body(default=None, embed=True),
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """Approve or reject a verification document, logged with admin id. KOL-18."""
    return service.decide_document(db, admin_id, doc_id, decision, reason)


@router.post("/social-accounts/{social_id}/decision")
def decide_social(
    social_id: str,
    decision: str = Body(..., embed=True),
    reason: str | None = Body(default=None, embed=True),
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """Approve or reject a manually connected social account, logged. KOL-18."""
    return service.decide_social(db, admin_id, social_id, decision, reason)

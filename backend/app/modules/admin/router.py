"""Admin operations (Epic B verification queue, Epic I dashboard and config).

Admin authentication and role based access control are not built yet, so admin
identity is taken from an X-Admin-Id header for now. This is a deliberate
placeholder to be replaced by real admin auth in a later epic; it is enough to
attribute and log decisions during the manual pilot.
"""
from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.db import get_db
from app.modules.admin import disputes, service
from app.modules.campaigns import orders as campaign_orders
from app.modules.payments import disputes as payments_disputes
from app.modules.payments import service as payments_service
from app.modules.config import service as config_service
from app.modules.config.schemas import CountryConfigIn, CountryConfigOut, EnabledIn

router = APIRouter()


def get_current_admin(x_admin_id: str | None = Header(default=None)) -> str:
    if not x_admin_id:
        raise AppError(
            status.HTTP_401_UNAUTHORIZED,
            code="admin_id_missing",
            detail="Missing X-Admin-Id header",
        )
    return x_admin_id


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

    So: one endpoint, behind the same X-Admin-Id placeholder as the rest of
    this router, that an operator or an external cron can hit. `curl -XPOST
    -H 'X-Admin-Id: ...' .../admin/jobs/run` is a scheduler, for a pilot.

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

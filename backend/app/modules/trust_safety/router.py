"""Trust and safety routes (Epic H): reviews and reports."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.admin.router import get_current_admin
from app.modules.auth.deps import get_current_user_id
from app.modules.trust_safety import schemas, service

router = APIRouter()


@router.post("/reviews", response_model=schemas.ReviewOut, status_code=201)
def submit_review(
    payload: schemas.ReviewIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Rate a collaboration partner after the escrow is released. KOL-31."""
    return service.submit_review(db, user_id, payload.escrow_id, payload.stars, payload.comment)


@router.get("/users/{user_id}/reviews", response_model=schemas.UserReviewsOut)
def user_reviews(user_id: str, db: Session = Depends(get_db)):
    """Public reputation for a user: revealed reviews only. KOL-31."""
    return service.user_reviews(db, user_id)


@router.post("/reports", response_model=schemas.ReportOut, status_code=201)
def create_report(
    payload: schemas.ReportIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Report suspicious behavior into the admin queue. KOL-32."""
    return service.create_report(
        db, user_id, payload.target_type, payload.target_id, payload.reason_code, payload.details
    )


@router.get("/reports")
def list_reports(
    report_status: str | None = None,
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """Admin queue of reported cases. KOL-32."""
    return service.list_reports(db, report_status)


@router.post("/reports/{report_id}/resolve", response_model=schemas.ReportOut)
def resolve_report(
    report_id: str,
    payload: schemas.ResolveReportIn,
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """Mark a reported case reviewed or dismissed, logged to the admin trail. KOL-32."""
    return service.resolve_report(db, admin_id, report_id, payload.decision)

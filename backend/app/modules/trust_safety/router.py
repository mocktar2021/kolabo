"""Trust and safety routes (Epic H): reviews, reports and blocks."""
from fastapi import APIRouter, Depends, status
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


@router.post("/blocks/{user_id}", response_model=schemas.BlockOut, status_code=status.HTTP_201_CREATED)
def block_user(
    user_id: str,
    payload: schemas.BlockIn | None = None,
    db: Session = Depends(get_db),
    me: str = Depends(get_current_user_id),
):
    """Stop dealing with somebody.

    The body is optional: a plain block from a profile menu sends none, and
    the combined block-and-report action sends the reported reason so the two
    rows can be read together later.

    ALWAYS 201, including when the block already existed. Pressing block twice
    is somebody on a slow connection tapping again, not a conflict worth
    arguing about, so the second call hands back the same row rather than an
    error on a safety control.
    """
    return service.block_user(db, me, user_id, payload.reason_code if payload else None)


@router.delete("/blocks/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unblock_user(
    user_id: str,
    db: Session = Depends(get_db),
    me: str = Depends(get_current_user_id),
):
    """Undo your own block. Silent when there was nothing to undo.

    Removes only the caller's row. If the other person blocked them too, that
    decision is theirs and is untouched.
    """
    service.unblock_user(db, me, user_id)


@router.get("/blocks", response_model=list[schemas.BlockOut])
def list_blocks(
    db: Session = Depends(get_db),
    me: str = Depends(get_current_user_id),
):
    """The caller's own blocked accounts, newest first, for a settings screen.

    Only rows the caller created. Somebody who blocked THEM never appears
    here: a list that showed it would turn this screen into a way of finding
    out who has blocked you, which is the one thing a block exists to keep
    somebody from learning.
    """
    return service.list_blocks(db, me)

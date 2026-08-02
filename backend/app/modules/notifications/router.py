"""Epic F (KOL-35): notification listing and email preferences.

Enough surface for a bell and a list: a capped, newest-first page, the unread
count the badge draws, mark one read and mark them all read. Every route takes
its subject from the bearer token and there is no id parameter naming a user,
so there is nothing here to walk through somebody else's notifications with.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import get_current_user_id
from app.modules.notifications import schemas, service

router = APIRouter()


@router.get("/", response_model=list[schemas.NotificationOut])
def list_notifications(
    limit: int = service.DEFAULT_LIMIT,
    offset: int = 0,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """The caller's own notifications, newest first, one page at a time.

    limit is clamped to service.MAX_LIMIT rather than refused: a bell asking
    for too many wants as many as it can have, and a 422 there is a blank menu.
    """
    return service.list_notifications(db, user_id, limit, offset)


# Declared before "/{notification_id}/read" with the other literal first
# segments, following the convention in campaigns.router: FastAPI matches in
# declaration order and a literal that arrives after a parameterised route is
# a bug waiting for somebody to widen the pattern.
@router.get("/unread-count", response_model=schemas.UnreadCountOut)
def unread_count(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """How many unread notifications the caller has.

    Separate from the list because the list is capped and the badge must not
    be: a count taken from a page would silently stop rising past the page
    size, which is worse than no badge at all.
    """
    return service.unread_count(db, user_id)


@router.post("/read-all", response_model=schemas.MarkAllReadOut)
def mark_all_read(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Clear the caller's whole bell, and say how many rows that was.

    The alternative is one request per row, which for somebody returning after
    a week is dozens of round trips to dismiss a badge.
    """
    return service.mark_all_read(db, user_id)


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    """Mark one notification read. Somebody else's answers 404, not 403 — a
    403 would confirm the id exists."""
    return service.mark_read(db, user_id, notification_id)


@router.put("/preferences")
def set_subscription(
    payload: schemas.SubscriptionIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Turn email for a notification type on or off. Critical types stay on."""
    return service.set_email_subscription(db, user_id, payload.type, payload.email_enabled)

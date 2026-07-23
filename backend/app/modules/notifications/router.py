"""Epic F (KOL-35): notification listing and email preferences."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import get_current_user_id
from app.modules.notifications import schemas, service

router = APIRouter()


@router.get("/", response_model=list[schemas.NotificationOut])
def list_notifications(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.list_notifications(db, user_id)


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.mark_read(db, user_id, notification_id)


@router.put("/preferences")
def set_subscription(
    payload: schemas.SubscriptionIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Turn email for a notification type on or off. Critical types stay on."""
    return service.set_email_subscription(db, user_id, payload.type, payload.email_enabled)

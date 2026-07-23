"""Notification logic (Epic D and Epic F).

notify() records an in-app notification and delivers it by email through the
sender interface. Critical types (payment, dispute) are always delivered.
Non critical types are delivered unless the user has unsubscribed from that
type. Delivery is synchronous so it goes out immediately, which meets the
"within 1 minute" criterion in KOL-35. The caller commits the transaction.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.notifications import email
from app.modules.notifications.models import Notification, NotificationPreference

CRITICAL_TYPES = {"payment", "dispute"}

email_sender: email.Sender = email.default_email_sender


def _muted_types(db: Session, user_id: str) -> list[str]:
    pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
    return list(pref.muted_types) if pref else []


def notify(db: Session, user_id: str, type: str, message: str) -> None:
    db.add(Notification(user_id=user_id, type=type, message=message))
    should_email = type in CRITICAL_TYPES or type not in _muted_types(db, user_id)
    if should_email:
        user = db.query(User).filter(User.id == user_id).first()
        if user is not None:
            target = user.email or user.phone
            email_sender.send(target, type, message)


def list_notifications(db: Session, user_id: str) -> list[dict]:
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return [{"id": n.id, "type": n.type, "message": n.message, "is_read": n.is_read} for n in rows]


def mark_read(db: Session, user_id: str, notification_id: str) -> dict:
    n = db.query(Notification).filter(Notification.id == notification_id).first()
    if n is None or n.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    n.is_read = True
    db.commit()
    return {"id": n.id, "is_read": True}


def set_email_subscription(db: Session, user_id: str, type: str, enabled: bool) -> dict:
    if type in CRITICAL_TYPES and not enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Critical notifications (payment, dispute) cannot be turned off",
        )
    pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
    if pref is None:
        pref = NotificationPreference(user_id=user_id, muted_types=[])
        db.add(pref)
    muted = set(pref.muted_types or [])
    if enabled:
        muted.discard(type)
    else:
        muted.add(type)
    pref.muted_types = sorted(muted)
    db.commit()
    return {"muted_types": pref.muted_types}

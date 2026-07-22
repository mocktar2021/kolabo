"""Notification helper. Records an in-app notification on the current session.

The caller commits the surrounding transaction. Email delivery is added in
Epic F (KOL-35); this only persists the record.
"""
from sqlalchemy.orm import Session

from app.modules.notifications.models import Notification


def notify(db: Session, user_id: str, type: str, message: str) -> None:
    db.add(Notification(user_id=user_id, type=type, message=message))

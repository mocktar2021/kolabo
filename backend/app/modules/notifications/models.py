"""In-app notification store and email preferences.

Introduced in Epic D and extended in Epic F (KOL-35) with email delivery and an
unsubscribe preference for non critical notification types.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    # The English prose. KEPT even now that the client renders from params,
    # because it is still the EMAIL body (email has no user to localise for and
    # no client to render it) and the FALLBACK the client shows for any row
    # written before params existed. type stays coarse — it drives muting and
    # CRITICAL_TYPES and the client's route fallback — so it is not enough on
    # its own to pick a message or a link.
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # Where clicking the notification goes, built at emit time BECAUSE THAT IS
    # WHERE THE RECIPIENT'S SIDE IS KNOWN: the same event links a brand to its
    # /campaigns/{id} and a creator to /invitations, and only the code raising
    # the notification knows which of the two it is telling. Null falls back to
    # the client's routeForType(type), which is a list screen — so a row
    # without a link still opens the right area, just not the exact record.
    link: Mapped[str | None] = mapped_column(String, nullable=True)
    # What the client renders the localised body from: a {"key": ...} naming
    # the i18n template plus its interpolation values (campaign title, actor
    # name, amount, currency, reason, hours…). Null on old rows and on any type
    # not yet migrated, in which case the client shows `message` verbatim. The
    # backend still writes `message` from the same values so the email matches.
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    # Non critical notification types the user has unsubscribed from by email.
    muted_types: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

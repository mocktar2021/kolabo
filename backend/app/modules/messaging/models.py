"""Messaging models (Epic F). Messages are tied to a specific campaign."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    sender_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    recipient_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)
    # When the recipient opened the thread carrying this message. NULL means
    # unread, and that is the whole unread count.
    #
    # A timestamp rather than the boolean notifications use (is_read). A
    # notification is a nudge and only has to know whether it still needs
    # showing; a message lives in a work channel hanging off a contract, and
    # in a dispute "when did you see this" is a real question — the brand says
    # it asked for the revision on the 3rd, the creator says they only saw it
    # on the 9th. A boolean cannot answer that. Naive UTC like every other
    # datetime here.
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

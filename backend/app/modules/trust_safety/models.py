"""Trust and safety models (Epic H): reviews and reports."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


OPEN = "open"
REVIEWED = "reviewed"
DISMISSED = "dismissed"


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("escrow_id", "reviewer_user_id", name="uq_review_per_reviewer"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    escrow_id: Mapped[str] = mapped_column(ForeignKey("escrows.id"), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(String, nullable=False)
    reviewer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewee_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    stars: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Double blind: a review is hidden until both parties have submitted.
    revealed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    reporter_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String, nullable=False)  # user, campaign, message
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    reason_code: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default=OPEN, nullable=False)
    reviewer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

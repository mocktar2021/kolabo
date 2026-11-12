"""Trust and safety models (Epic H): reviews, reports and blocks."""
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


class Block(Base):
    """One person's decision to stop dealing with another.

    A ROW IS A DECISION, NOT A STATE MACHINE. It exists or it does not, and
    unblocking deletes it. There is deliberately no `unblocked_at` and no
    soft delete: the only question any caller asks is "are these two blocked
    right now", and a kept history of blocks and unblocks would be a new
    record of who fell out with whom, held for nobody's benefit. If a
    moderation case ever needs that history it should arrive as something a
    user can be told about, not as a column that quietly accumulated.

    ONE ROW IS ONE DIRECTION, AND THE EFFECT IS SYMMETRIC. The pair is
    unique, so A blocking B is one row and B blocking A is a second one, and
    unblocking removes only the one you created. What is symmetric is what
    the row DOES: see blocks.blocked_pair_ids for why a block has to hide
    both faces rather than only one.

    WHAT A BLOCK DOES NOT DO, because this is a marketplace and not a social
    app: it does not cancel a contract, move money, or delete a thread. Two
    people can be bound by a signed agreement with funds in escrow, and a
    button cannot undo that. The enforcement that follows this table stops
    NEW dealings and mutes further messages; the contract, the escrow and the
    thread history stay exactly where they are, because the history is the
    evidence a dispute runs on.

    reason_code is null for a plain block and carries the reported reason
    when the block arrived through the combined block-and-report action, so
    the two rows can be read together later without a join through a free
    text field.
    """

    __tablename__ = "blocks"
    __table_args__ = (
        UniqueConstraint("blocker_user_id", "blocked_user_id", name="uq_block_pair"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    blocker_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    blocked_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    reason_code: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

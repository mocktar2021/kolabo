"""Escrow models (Epic G).

Money is in minor units with an explicit currency. The escrow lifecycle is
held, then released (with commission deducted) or refunded, with a disputed
state that freezes it pending an admin decision.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


HELD = "held"
RELEASED = "released"
REFUNDED = "refunded"
DISPUTED = "disputed"


class Escrow(Base):
    __tablename__ = "escrows"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), unique=True, nullable=False)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    business_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    influencer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    commission_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_fund_ref: Mapped[str] = mapped_column(String, nullable=False)
    provider_payout_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default=HELD, nullable=False)
    held_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    due_release_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class EscrowEvent(Base):
    """Immutable audit trail of escrow lifecycle events."""

    __tablename__ = "escrow_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    escrow_id: Mapped[str] = mapped_column(ForeignKey("escrows.id"), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    event: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

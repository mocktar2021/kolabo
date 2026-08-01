"""Contract and signature models (Epic E).

A contract is generated from an accepted proposal, capturing a snapshot of the
agreed terms so later edits to the campaign or proposal do not change it. Once
both parties sign, the contract is immutable and payment can be unlocked.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


PENDING = "pending_signatures"
SIGNED = "signed"
VOID = "void"
# Called off by one of the two parties before it was fully signed and while no
# escrow existed against it (contracts.cancellation).
#
# Its own status rather than VOID, which has never been written by any code
# path and reads as "this document was never valid" — a statement about the
# paper. Cancelled is a statement about the deal: it was real, it was on the
# table, and somebody ended it before it bound anyone. The two want telling
# apart the first time a contract genuinely has to be voided for a defect.
#
# The row is kept, like every other ended thing here. A creator who signed and
# then watched the brand walk away has a record worth keeping, and the
# contract_events trail hangs off the row.
CANCELLED = "cancelled"


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), unique=True, nullable=False)
    business_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    influencer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    rate_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_currency: Mapped[str] = mapped_column(String, nullable=False)
    timeline_days: Mapped[int] = mapped_column(Integer, nullable=False)
    deliverables: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String, default=PENDING, nullable=False)
    business_signature: Mapped[str | None] = mapped_column(String, nullable=True)
    business_signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    influencer_signature: Mapped[str | None] = mapped_column(String, nullable=True)
    influencer_signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ContractEvent(Base):
    """Immutable audit trail of contract lifecycle events."""

    __tablename__ = "contract_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), nullable=False, index=True)
    actor_user_id: Mapped[str] = mapped_column(String, nullable=False)
    event: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

"""Escrow models (Epic G) and the dispute that freezes one (KOL-37).

Money is in minor units with an explicit currency. The escrow lifecycle is
held, then released (with commission deducted) or refunded, with a disputed
state that freezes it pending an admin decision.

WHY THE DISPUTE TABLES LIVE HERE. A dispute has no life apart from the escrow
it freezes: it is opened against one, it is closed by settling one, and every
query that reads it reads the escrow in the same breath. Splitting the two
across modules would buy a cross-module import for a read model. What DID get
its own module is the logic (payments/disputes.py) — that is the part that was
growing, not the schema.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
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

# Why a closed set rather than free text. Two things read this column and
# neither can read prose. The admin queue triages by it — an admin looking at
# fifty frozen escrows sorts by what went wrong before reading a single
# statement — and, later, fraud analytics counts it: "payment_issue from the
# same buyer eleven times this month" is a pattern a free-text box can never
# be counted into. The statement is where the words go; this is the label.
DISPUTE_REASONS = (
    "not_delivered",
    "late",
    "wrong_content",
    "quality",
    "payment_issue",
    "other",
)

# Dispute lifecycle. awaiting_response is the 72 hour window in which the two
# parties can still settle it themselves; awaiting_admin is the queue.
AWAITING_RESPONSE = "awaiting_response"
AWAITING_ADMIN = "awaiting_admin"
DISPUTE_RESOLVED = "resolved"
DISPUTE_WITHDRAWN = "withdrawn"


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
    # When both parties were told the delivery date had passed with nothing
    # submitted. Null means not yet, which is the state every escrow starts in
    # and most stay in. The DEADLINE itself is not stored — it is held_at plus
    # the contract's timeline_days, both immutable once signed, which is what
    # lets the sweep cover escrows funded before it existed. See
    # payments.service.run_non_delivery_refunds.
    non_delivery_warned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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


class Dispute(Base):
    """One disagreement over one escrow. An escrow may have several, in turn.

    escrow_id is INDEXED, NOT UNIQUE, and that is the whole rule: one OPEN
    dispute at a time, not one dispute forever. Unique looked like the same
    thing and was not — it meant an escrow that had ever been disputed could
    never be disputed again, so two parties who settled a first disagreement
    themselves by withdrawing it had spent the escrow's only dispute. A
    creator who then failed to deliver on that same contract left the brand
    with no claim to make on money the brand had already paid in.

    So the conflict is enforced in disputes.raise_dispute against
    disputes.OPEN_STATUSES instead. "Is there a live one" is a question about
    status, and a column cannot ask it. Everything that reads a dispute from
    an escrow — the raise path, resolution — has to say which one it means.

    released_amount / refunded_amount are the admin's split, recorded on the
    dispute rather than only on the escrow: the escrow says where the money
    ended up, this says what was decided and by whom.
    """

    __tablename__ = "disputes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    escrow_id: Mapped[str] = mapped_column(ForeignKey("escrows.id"), nullable=False, index=True)
    opened_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, default=AWAITING_RESPONSE, nullable=False)
    # When the other party's exclusive window closes. Naive UTC, like every
    # other timestamp in the system.
    respond_by: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    released_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    refunded_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class DisputeMessage(Base):
    """One turn in the thread the two parties settle it in."""

    __tablename__ = "dispute_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    dispute_id: Mapped[str] = mapped_column(ForeignKey("disputes.id"), nullable=False, index=True)
    author_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class DisputeAttachment(Base):
    """An image offered as evidence, on the opening statement or on a message.

    It points at a media_assets row rather than carrying bytes of its own.
    Creators and brands already have a working image upload with an owner, a
    content type and a serving route; a dispute-only image store would be a
    second upload path, a second size limit and a second thing to move to
    object storage later, to hold exactly the same JPEGs.

    message_id is NULL for the images attached to the opening statement, and
    set for images attached to a later message — one table for both, because
    an admin reading the case wants the evidence in the order it arrived, not
    split across two queries.
    """

    __tablename__ = "dispute_attachments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    dispute_id: Mapped[str] = mapped_column(ForeignKey("disputes.id"), nullable=False, index=True)
    message_id: Mapped[str | None] = mapped_column(ForeignKey("dispute_messages.id"), nullable=True)
    media_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

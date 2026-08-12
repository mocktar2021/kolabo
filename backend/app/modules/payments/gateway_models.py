"""Rows the gateway layer needs: the attempt, the disbursement, the receipt.

WHY THESE ARE NOT IN payments/models.py. That file is the escrow and the
dispute — the platform's own account of who owes what, which is true whether or
not any gateway exists and which the mock provider exercises end to end. These
three are the record of talking to an outside system, and they have the shape
outside systems force on you: retry counters, raw status strings, an
idempotency key. Keeping them apart means the escrow model stays readable as a
description of the business, and it means a second gateway lands here without
touching the file everything else imports.

    PaymentIntent   one attempt by a brand to fund one contract
    Payout          one attempt to push money to one person's wallet
    GatewayEvent    one webhook we have already processed

THE THIRD ONE IS THE INTERESTING ONE. Webhooks are delivered at-least-once by
every gateway worth using — FedaPay retries, and so does anything sitting
between us and them. So "we already handled this" has to be a fact in the
database with a unique constraint on it, not a hope. Without it, two deliveries
of the same `transaction.approved` race, both find no escrow, and both create
one for the same contract; the unique index on escrows.contract_id would catch
that particular case, but only by raising an IntegrityError inside a webhook,
which is a 500 that makes the gateway retry, forever.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# PaymentIntent lifecycle. Mirrors gateways.base but stored as its own strings
# so a future gateway with a fifth state does not have to fit in four.
INTENT_PENDING = "pending"
INTENT_SUCCEEDED = "succeeded"
INTENT_FAILED = "failed"
INTENT_CANCELED = "canceled"
INTENT_OPEN_STATUSES = (INTENT_PENDING,)

# Payout lifecycle.
PAYOUT_PENDING = "pending"
PAYOUT_SENT = "sent"
PAYOUT_FAILED = "failed"
# The state that exists because a creator can be owed money before they have
# told us where to send it. See payout_methods.py — this is not a gateway
# failure and must not be retried against the gateway.
PAYOUT_NO_METHOD = "awaiting_method"
PAYOUT_RETRYABLE_STATUSES = (PAYOUT_PENDING, PAYOUT_FAILED)

# What a payout is for. A release pays the creator; a refund gives a brand
# their money back. Same mechanism, opposite direction, and the ledger has to
# be able to tell them apart.
PAYOUT_KIND_RELEASE = "release"
PAYOUT_KIND_REFUND = "refund"


class PaymentIntent(Base):
    """One attempt to fund one contract.

    NOT UNIQUE ON contract_id, and that is deliberate. A brand whose first
    attempt failed — wrong PIN, no balance, closed the tab — must be able to
    try again, and each try is its own row with its own gateway reference. What
    IS unique is the escrow: only one intent per contract can ever succeed,
    enforced where it belongs, on escrows.contract_id.

    `amount` and `currency` are COPIED off the contract at creation rather than
    read through a join at settlement. If a contract's rate could ever change
    between funding and settling, a join would silently settle the new number
    against the old payment. The copy is what lets settlement assert that the
    money that arrived is the money that was asked for.
    """

    __tablename__ = "payment_intents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), nullable=False, index=True)
    business_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    # The gateway's id for this transaction. Nullable for the instant between
    # writing our row and hearing back from theirs — a window that exists so
    # that a gateway call which times out AFTER creating a transaction leaves
    # us a row to reconcile instead of nothing at all.
    provider_ref: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default=INTENT_PENDING, nullable=False, index=True)
    # Their word for it, kept verbatim next to our normalised one. When a
    # payment goes wrong at 2am, "declined" versus "canceled" versus a status
    # we had never seen is the difference between a five minute diagnosis and
    # an afternoon, and the normalised column has thrown that away by design.
    provider_status: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    escrow_id: Mapped[str | None] = mapped_column(ForeignKey("escrows.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Payout(Base):
    """One attempt to push money out to one person's wallet.

    THE WHOLE REASON THIS TABLE EXISTS: escrow.status = released is a DECISION,
    and a payout is an EVENT, and they fail differently. Before this, _release
    called provider.payout() inline and stamped the escrow RELEASED in the same
    breath — fine against a mock that cannot fail, wrong against a network. A
    real payout can time out, be declined by the network, or sit in `processing`
    for an hour. If that failure propagated it would 500 a release the platform
    had already decided on; if it were swallowed it would leave an escrow that
    says the creator was paid when nobody was.

    So: the escrow records the decision and never un-records it, and this row
    records what happened to the money, retried by a sweep until it is terminal.
    A creator with a failed payout is visibly owed money by the platform, which
    is the truth, and is a support ticket rather than a silent loss.

    escrow_id is not unique for the same reason: a payout that failed is
    followed by another one for the same escrow.
    """

    __tablename__ = "payouts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    escrow_id: Mapped[str] = mapped_column(ForeignKey("escrows.id"), nullable=False, index=True)
    recipient_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String, default=PAYOUT_KIND_RELEASE, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_ref: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, default=PAYOUT_PENDING, nullable=False, index=True)
    provider_status: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    # Counted so the sweep can back off and, eventually, stop and escalate to a
    # human. An unbounded retry against a permanently invalid destination is a
    # loop that bills us per attempt and never succeeds.
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PayoutMethod(Base):
    """Where one creator wants to be paid, and over which network.

    THE MODE IS NOT GUESSED FROM THE PHONE NUMBER, and this table is the whole
    reason why. Operator prefix ranges in Benin and Cote d'Ivoire have been
    reassigned more than once, number portability moves a subscriber between
    networks without changing a digit, and a mobile money payout sent down the
    wrong network does not bounce cleanly — it fails late, or worse, it lands in
    a wallet the recipient does not check. Asking once and storing the answer
    costs one screen; inferring it costs support tickets about missing money,
    which is the most expensive kind a marketplace can generate.

    One row per user, so `user_id` is unique: a creator is paid one way. Changing
    it is an update, and the audit of what was actually used lives on the Payout
    rows, which carry their own destination at the time they were sent.
    """

    __tablename__ = "payout_methods"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False)
    # The gateway's network string, validated against gateways.fedapay.PAYOUT_MODES
    # when it is saved so a bad value is refused at the form, not at the payout.
    mode: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    account_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class GatewayEvent(Base):
    """A webhook we have already seen. The idempotency key, and only that.

    (provider, event_id) is UNIQUE and the insert happens BEFORE the work, not
    after. That ordering is the entire mechanism: two concurrent deliveries of
    the same event both try to insert, exactly one wins the constraint, and the
    loser knows it lost before it has done anything. Inserting after the work
    would leave the window open for precisely as long as the work takes, which
    is when the duplicate delivery arrives.

    `payload` is kept because a payment webhook is the closest thing we have to
    a receipt from the outside world, and the first question in any dispute
    about whether money moved is what the gateway actually told us and when.
    """

    __tablename__ = "gateway_events"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_gateway_event"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    event_id: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

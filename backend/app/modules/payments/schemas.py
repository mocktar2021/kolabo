"""Schemas for the payments module."""
from datetime import datetime

from pydantic import BaseModel, Field


class FundIn(BaseModel):
    contract_id: str


class ResolveIn(BaseModel):
    """An admin's decision, as two figures that have to add up.

    Either may be zero, which reproduces the old full-release and full-refund
    outcomes. The sum is checked against the escrow in the service, where the
    refusal can name both figures and the total.
    """

    released_amount: int
    refunded_amount: int
    note: str | None = None


class DisputeIn(BaseModel):
    """What raising a dispute now costs the person raising it.

    A reason, a statement and optional evidence — the bounds and the closed
    set of reasons are checked in the service so the refusal names the rule
    instead of naming a field.
    """

    reason: str
    statement: str
    media_ids: list[str] = []


class DisputeMessageIn(BaseModel):
    body: str
    media_ids: list[str] = []


class EscrowOut(BaseModel):
    id: str
    contract_id: str
    campaign_id: str
    business_user_id: str
    influencer_user_id: str
    amount: int
    currency: str
    commission_amount: int | None
    status: str


class EarningPaymentOut(BaseModel):
    """One line of a creator's statement.

    gross, commission and net all three, side by side. Net is the number that
    matters — it is what reaches the wallet — but showing it alone would make
    the platform's cut invisible, and a fee somebody cannot see is a fee they
    assume was a mistake. The three columns are how a creator checks our
    arithmetic against their own.
    """

    escrow_id: str
    contract_id: str
    campaign_title: str | None = None
    # The buyer, by company name. Null while they have written no profile:
    # a phone number is the only other thing on the users row and it is never
    # handed to the other side of a deal.
    counterparty_name: str | None = None
    gross: int
    commission: int
    net: int
    currency: str
    status: str
    # Settled when it settled, funded when it has not. A statement line has
    # one date on it.
    date: datetime | None = None


class EarningsOut(BaseModel):
    """The creator's money, in three states and never summed across currencies.

    Each total is a map of currency to minor units. A single figure spanning
    two markets would not be a rounding problem, it would be a meaningless
    number on the screen a creator trusts most.

    disputed is its own field and not part of pending, because frozen money is
    not money on its way. See app.modules.payments.earnings.
    """

    earned: dict[str, int] = Field(default_factory=dict)
    pending: dict[str, int] = Field(default_factory=dict)
    disputed: dict[str, int] = Field(default_factory=dict)
    payments: list[EarningPaymentOut] = Field(default_factory=list)


class DisputeOut(BaseModel):
    id: str
    escrow_id: str
    opened_by_user_id: str
    reason: str
    statement: str
    status: str
    respond_by: str
    resolved_at: str | None = None
    resolution: str | None = None
    released_amount: int | None = None
    refunded_amount: int | None = None
    resolved_by: str | None = None
    # When the case was opened. An escrow can carry several disputes over its
    # life, so "which one is this" is answered by a date as often as by an id:
    # a list of a contract's cases is unreadable without it. dispute_out has
    # always built it; leaving it off here quietly stripped it back out of the
    # one dispute response that has a schema.
    created_at: str
    attachments: list[str] = []
    escrow: EscrowOut | None = None

"""Schemas for the payments module."""
from pydantic import BaseModel


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

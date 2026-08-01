"""Schemas for the payments module."""
from pydantic import BaseModel


class FundIn(BaseModel):
    contract_id: str


class ResolveIn(BaseModel):
    decision: str  # release or refund


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
    attachments: list[str] = []
    escrow: EscrowOut | None = None

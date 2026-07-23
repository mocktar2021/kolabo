"""Schemas for the payments module."""
from pydantic import BaseModel


class FundIn(BaseModel):
    contract_id: str


class ResolveIn(BaseModel):
    decision: str  # release or refund


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

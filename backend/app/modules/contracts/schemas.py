"""Schemas for the contracts module."""
from pydantic import BaseModel, Field


class SignIn(BaseModel):
    signature: str = Field(min_length=1, max_length=120)


class ContractOut(BaseModel):
    id: str
    campaign_id: str
    proposal_id: str
    business_user_id: str
    influencer_user_id: str
    language: str
    status: str
    rate_amount: int
    rate_currency: str
    timeline_days: int
    business_signed: bool
    influencer_signed: bool
    fully_signed: bool


class ContractDetailOut(ContractOut):
    body: str

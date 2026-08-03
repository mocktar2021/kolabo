"""Schemas for the contracts module."""
from datetime import datetime

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


class ContractListItem(ContractOut):
    """A row of GET /contracts/mine: the contract, plus what a card needs to be
    read at a glance without opening it. All three of the added identity fields
    are nullable — the campaign could predate the title column, and the other
    party may have written no profile yet, in which case the row carries a null
    rather than a phone number or a bare user id."""
    campaign_title: str | None
    counterparty_name: str | None
    counterparty_avatar_url: str | None
    created_at: datetime


class ContractDetailOut(ContractOut):
    body: str

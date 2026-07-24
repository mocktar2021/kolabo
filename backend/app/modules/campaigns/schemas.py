"""Schemas for the campaigns module."""
from datetime import date

from pydantic import BaseModel, Field


class Deliverable(BaseModel):
    platform: str
    type: str
    quantity: int = Field(ge=1)


class CampaignCreate(BaseModel):
    title: str = Field(min_length=1)
    budget_amount: int | None = Field(default=None, ge=1)
    budget_currency: str | None = None
    deliverables: list[Deliverable] = Field(default_factory=list)
    deadline: date | None = None
    publish: bool = False


class CampaignOut(BaseModel):
    id: str
    business_user_id: str
    title: str
    budget_amount: int | None
    budget_currency: str | None
    deliverables: list[Deliverable]
    deadline: date | None
    status: str


class InvitationOut(BaseModel):
    id: str
    campaign_id: str
    influencer_user_id: str
    status: str


class ProposalIn(BaseModel):
    rate_amount: int = Field(ge=1)
    rate_currency: str = Field(min_length=3, max_length=3)
    timeline_days: int = Field(ge=1)


class ProposalOut(BaseModel):
    id: str
    campaign_id: str
    influencer_user_id: str
    version: int
    rate_amount: int
    rate_currency: str
    timeline_days: int
    status: str


class CampaignDetailOut(CampaignOut):
    invitations: list[InvitationOut] = Field(default_factory=list)
    proposals: list[ProposalOut] = Field(default_factory=list)


class InvitationWithCampaign(BaseModel):
    id: str
    campaign_id: str
    influencer_user_id: str
    status: str
    campaign: CampaignOut

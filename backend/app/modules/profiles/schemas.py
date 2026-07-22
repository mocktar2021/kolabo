"""Schemas for the profiles module."""
from pydantic import BaseModel, Field

SOCIAL_PLATFORMS = {"instagram", "tiktok", "facebook", "youtube", "linkedin", "snapchat", "x"}
SOCIAL_METHODS = {"oauth", "manual"}


class InfluencerProfileIn(BaseModel):
    bio: str | None = None
    categories: list[str] = Field(default_factory=list)
    rate_card: dict = Field(default_factory=dict)


class InfluencerProfileOut(BaseModel):
    user_id: str
    bio: str | None
    categories: list[str]
    rate_card: dict
    completion_percent: int
    is_searchable: bool


class BusinessProfileIn(BaseModel):
    company_name: str = Field(min_length=1)
    industry: str | None = None
    description: str | None = None


class BusinessProfileOut(BaseModel):
    user_id: str
    company_name: str
    industry: str | None
    description: str | None


class SocialAccountConnect(BaseModel):
    platform: str
    handle: str = Field(min_length=1)
    method: str
    proof_url: str | None = None


class SocialAccountOut(BaseModel):
    id: str
    platform: str
    handle: str
    method: str
    status: str


class VerificationDocumentOut(BaseModel):
    id: str
    doc_type: str
    filename: str
    status: str
    rejection_reason: str | None = None

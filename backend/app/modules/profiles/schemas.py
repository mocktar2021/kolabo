"""Schemas for the profiles module."""
from pydantic import BaseModel, Field

from app.core.platforms import SOCIAL_PLATFORMS  # noqa: F401  (re-exported)

SOCIAL_METHODS = {"oauth", "manual"}


class InfluencerProfileIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    headline: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=120)
    avatar_media_id: str | None = None
    bio: str | None = None
    categories: list[str] = Field(default_factory=list)
    rate_card: dict = Field(default_factory=dict)
    follower_count: int | None = None


class InfluencerProfileOut(BaseModel):
    user_id: str
    display_name: str | None = None
    headline: str | None = None
    location: str | None = None
    avatar_media_id: str | None = None
    avatar_url: str | None = None
    bio: str | None
    categories: list[str]
    rate_card: dict
    follower_count: int | None = None
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
    follower_count: int | None = Field(default=None, ge=0)


class SocialAccountOut(BaseModel):
    id: str
    platform: str
    handle: str
    method: str
    status: str
    follower_count: int | None = None
    enriched: bool = False


class OnboardingStatusOut(BaseModel):
    has_bio: bool
    has_categories: bool
    has_pricing: bool
    has_packages: bool
    has_social: bool
    is_live: bool


class VerificationDocumentOut(BaseModel):
    id: str
    doc_type: str
    filename: str
    status: str
    rejection_reason: str | None = None


class MediaOut(BaseModel):
    id: str
    url: str


class PackageIn(BaseModel):
    platform: str
    deliverable_type: str
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    price_amount: int = Field(ge=1)
    currency: str = Field(min_length=3, max_length=3)
    is_active: bool = True


class PackageOut(BaseModel):
    id: str
    user_id: str
    platform: str
    deliverable_type: str
    title: str
    description: str | None
    price_amount: int
    currency: str
    is_active: bool


class PortfolioItemIn(BaseModel):
    media_id: str


class PortfolioItemOut(BaseModel):
    id: str
    media_id: str
    url: str


class PublicProfileOut(BaseModel):
    user_id: str
    display_name: str | None
    headline: str | None
    location: str | None
    avatar_url: str | None
    bio: str | None
    categories: list[str]
    follower_count: int | None
    is_searchable: bool
    average_stars: float | None
    review_count: int
    packages: list[PackageOut]
    portfolio: list[PortfolioItemOut]
    social_accounts: list[SocialAccountOut]

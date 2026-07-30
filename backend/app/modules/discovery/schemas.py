"""Schemas for the discovery module."""
from pydantic import BaseModel


class SocialSummary(BaseModel):
    platform: str
    handle: str
    follower_count: int | None = None


class InfluencerSearchResult(BaseModel):
    user_id: str
    display_name: str | None = None
    headline: str | None = None
    location: str | None = None
    avatar_url: str | None = None
    cover_url: str | None = None
    socials: list[SocialSummary] = []
    bio: str | None
    categories: list[str]
    follower_count: int | None
    country_code: str
    is_verified: bool
    starting_price_amount: int | None = None
    starting_price_currency: str | None = None
    average_stars: float | None = None
    review_count: int = 0


class FavoriteOut(BaseModel):
    influencer_user_id: str

"""Schemas for the discovery module."""
from pydantic import BaseModel


class InfluencerSearchResult(BaseModel):
    user_id: str
    display_name: str | None = None
    headline: str | None = None
    avatar_url: str | None = None
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

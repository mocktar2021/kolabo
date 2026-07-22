"""Schemas for the discovery module."""
from pydantic import BaseModel


class InfluencerSearchResult(BaseModel):
    user_id: str
    bio: str | None
    categories: list[str]
    follower_count: int | None
    country_code: str
    is_verified: bool


class FavoriteOut(BaseModel):
    influencer_user_id: str

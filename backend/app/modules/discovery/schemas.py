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
    # A shortlist is rendered as cards, and a card needs a person on it. Every
    # one of these is optional because a creator can be favourited before they
    # have filled in anything: an empty card is still usable, a 500 is not.
    display_name: str | None = None
    avatar_url: str | None = None
    headline: str | None = None
    # From the users table, which is the only place a country lives. It is
    # also the only field taken from there: the sole other identifier a user
    # row holds is a phone number, and that never reaches a payload.
    country_code: str | None = None

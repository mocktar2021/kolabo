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
    # The shared creator identity (app.core.identity.creator_identities): the
    # same four fields the campaign page's invitations and proposals carry, so
    # a business shortlisting somebody and a business reviewing their offer
    # are reading the same card. Every one is optional because a creator can
    # be favourited before they have filled in anything.
    display_name: str | None = None
    avatar_url: str | None = None
    # The single biggest connected platform, never a total across platforms:
    # somebody following on two networks would otherwise be counted twice.
    top_platform: str | None = None
    top_follower_count: int | None = None
    # headline deliberately no longer travels on a favourite row. It was here
    # only to be a subtitle under the name, and creators write their name into
    # it — so the card said the same thing twice. The audience number is what
    # a business actually shortlists on. headline is untouched on the profile
    # and on the search result card, where it earns its space.
    #
    # country_code comes from the users table, and stays the only field taken
    # from there: the sole other identifier a user row holds is a phone
    # number, and a phone number never reaches a payload.
    country_code: str | None = None

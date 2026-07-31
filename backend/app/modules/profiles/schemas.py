"""Schemas for the profiles module."""
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.core.platforms import SOCIAL_PLATFORMS  # noqa: F401  (re-exported)

SOCIAL_METHODS = {"oauth", "manual"}

# The closed set behind the duration chip. Data, not free text, so the chip
# can be rendered (and translated) from the unit.
DURATION_UNITS = {"seconds", "minutes", "hours"}


class InfluencerProfileIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    headline: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=120)
    avatar_media_id: str | None = None
    bio: str | None = None
    bio_fr: str | None = None
    bio_en: str | None = None
    categories: list[str] = Field(default_factory=list)
    rate_card: dict = Field(default_factory=dict)
    # Answers to the two standard profile questions, keyed by stable question
    # id ("audience", "brands"). Rides the exclude_unset upsert like every
    # other field, so a form that does not know about the faq cannot wipe it.
    faq: dict = Field(default_factory=dict)
    follower_count: int | None = None
    # Required to go live (creators must be 18+; the service enforces the
    # age), never shown publicly.
    birth_date: date | None = None
    # Optional and never public. A closed set so analytics see categories,
    # not free text.
    gender: str | None = Field(default=None, pattern="^(female|male|other|prefer_not_to_say)$")
    # Languages the creator works in, e.g. ["fr", "en"]. Public.
    languages: list[str] = Field(default_factory=list)


class BioGenerateIn(BaseModel):
    language: str = Field(pattern="^(fr|en)$")


class BioGenerateOut(BaseModel):
    language: str
    bio: str
    # A draft, not a saved value: the creator accepts it by saving the profile.
    saved: bool = False
    generations_remaining: int


class InfluencerProfileOut(BaseModel):
    user_id: str
    display_name: str | None = None
    headline: str | None = None
    location: str | None = None
    avatar_media_id: str | None = None
    avatar_url: str | None = None
    bio: str | None
    bio_fr: str | None = None
    bio_en: str | None = None
    categories: list[str]
    rate_card: dict
    faq: dict = {}
    follower_count: int | None = None
    # Owner-facing only: birth_date and gender prefill the edit form here but
    # are deliberately absent from PublicProfileOut.
    birth_date: date | None = None
    gender: str | None = None
    languages: list[str] = []
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


class SocialAccountUpdate(BaseModel):
    """Partial edit of a connected account. Follows the profile upsert's
    exclude_unset contract: only fields the client actually sent are applied,
    so a form that does not know about proof_url cannot wipe it."""

    handle: str | None = Field(default=None, min_length=1)
    follower_count: int | None = Field(default=None, ge=0)
    proof_url: str | None = None


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
    # The 18+ gate: a profile without a date of birth cannot go live.
    has_birth_date: bool
    # Progress toward MIN_LIVE_PACKAGES, so the wizard can say "1 of 3".
    active_package_count: int
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
    # Collabstr-style spec chips: quantity is the "×10", the duration pair is
    # the "30 Seconds". quantity is capped so a typo (×1000 stories) cannot
    # become a listing. The unit is a closed set (see DURATION_UNITS); the
    # cross-field rule that value and unit come together lives in the service,
    # because it is about the pair, not the shape of either field.
    quantity: int = Field(default=1, ge=1, le=100)
    duration_value: int | None = Field(default=None, ge=1)
    duration_unit: str | None = Field(default=None, pattern="^(seconds|minutes|hours)$")
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
    quantity: int = 1
    duration_value: int | None = None
    duration_unit: str | None = None
    is_active: bool


class PortfolioItemIn(BaseModel):
    media_id: str


class PortfolioItemOut(BaseModel):
    id: str
    media_id: str
    url: str


class ReviewOut(BaseModel):
    """A single revealed review shown on the public creator page."""

    stars: int
    comment: str | None = None
    created_at: datetime
    # From the reviewer's influencer profile when they have one. Business
    # reviewers stay null until business profiles carry a public name; the
    # users table only holds a phone number, which is never exposed.
    reviewer_display_name: str | None = None


class PublicProfileOut(BaseModel):
    user_id: str
    display_name: str | None
    headline: str | None
    location: str | None
    avatar_url: str | None
    # Resolved to the viewer's language, falling back to whichever is filled.
    bio: str | None
    bio_fr: str | None = None
    bio_en: str | None = None
    categories: list[str]
    # Public on purpose; birth_date and gender never appear on this schema.
    languages: list[str] = []
    follower_count: int | None
    is_searchable: bool
    # Only the answers the creator actually wrote; the question wording is
    # rendered by the frontend from i18n, in the viewer's language.
    faq: dict = {}
    average_stars: float | None
    review_count: int
    # Revealed reviews only, newest first, capped at 20.
    reviews: list[ReviewOut] = []
    packages: list[PackageOut]
    portfolio: list[PortfolioItemOut]
    social_accounts: list[SocialAccountOut]

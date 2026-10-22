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
    # The cross-platform total, and deliberately the one follower number with
    # no source of its own: no single connected account can state it. The
    # per-platform numbers carry their provenance on SocialAccountOut.
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


class PartyDetailsIn(BaseModel):
    """What a user states about itself for a contract to print.

    ONE MODEL FOR BOTH SIDES OF THE MARKET. A buyer's block and a creator's
    block have the same shape, so one model validates both, one renderer
    prints both, and an agency creator who IS a registered company needs no
    second form. See app.modules.profiles.models.PARTY_TYPES.

    display_label IS NOT ON THIS MODEL, and its absence is load-bearing. The
    label a contract prints is DERIVED server side from legal_name at capture
    (see party_details.derive_display_label) so that a renderer and a contract
    card have one field to read without branching on party_type. A client that
    sends one anyway has it dropped rather than refused: pydantic ignores keys
    it does not know, which is the behaviour we want here, because a 422 would
    fail the save of an otherwise correct form over a field the client was
    never meant to fill in the first place.

    WHAT IS REQUIRED HERE AND WHAT IS NOT. The four fields every party type
    shares are required by this model, because they are always part of the
    shape. Everything a single type adds is optional here and decided by
    party_details.py, which refuses a block missing a field its own type needs
    with `party_details_invalid`. That is the same line this module already
    draws for a package's duration pair: the schema owns the shape of a field,
    the service owns a rule about the relationship between fields. It also
    keeps the refusal translatable, because a 422 body is not something either
    client's error catalogue covers.

    NOTHING STATED HERE IS CHECKED BY ANYBODY. These are self declared
    contract details, exactly as they would be on paper. The form's copy has
    to say so plainly, and no surface may render a tick, a badge or the word
    verified next to any of it.
    """

    # One of models.PARTY_TYPES, and it decides which of the fields below
    # matter. NO pattern here on purpose, for the same reason `platform` and
    # `method` carry none: the closed set lives in models.py and the refusal
    # belongs next to the rule, in the service, under a code the two error
    # catalogues can translate.
    party_type: str = Field(min_length=1, max_length=40)
    # ISO 3166-1 alpha-2, the country this party contracts from. Two
    # characters is the shape; that they are letters, and uppercase, is
    # normalised by the service. NOT restricted to the pilot markets: a buyer
    # contracting from outside them is an ordinary case, not an error.
    country: str = Field(min_length=2, max_length=2)
    # One free text field, deliberately not split into street, city and
    # postcode. Addresses in the launch markets do not reliably decompose that
    # way, nothing joins on the parts, and a form that demands a postcode from
    # a creator in Cotonou is a form that does not get completed.
    address: str = Field(min_length=1, max_length=500)
    # The entity's registered name, or the natural person's own name for a
    # sole trader. Required for all three types, because display_label is
    # derived from it and a contract with no name on it is the defect this
    # whole change exists to fix.
    legal_name: str = Field(min_length=1, max_length=200)
    # SARL, SA, Ltd, GmbH. A registered_company states one; the other two
    # types have nothing to put here.
    legal_form: str | None = Field(default=None, max_length=120)
    # RCCM, companies house number, association register number. Required of a
    # registered_company and of an association, meaningless for a sole trader.
    registration_number: str | None = Field(default=None, max_length=120)
    # IFU in Benin, TIN elsewhere. Required of a registered_company, OPTIONAL
    # for a sole trader (many genuinely have none) and not asked of an
    # association.
    tax_identifier: str | None = Field(default=None, max_length=120)
    # The human who signs for an entity, and the capacity they sign in
    # ("Gerant", "Directrice generale", "President"). Both required of a
    # registered_company and of an association. A sole trader signs for
    # themselves, so asking would be asking them to name themselves twice.
    representative_name: str | None = Field(default=None, max_length=200)
    representative_capacity: str | None = Field(default=None, max_length=120)


class PartyDetailsOut(BaseModel):
    """A stored party block, as the profile holds it now.

    EVERY TYPE-SPECIFIC FIELD IS NULLABLE HERE, because only the keys
    belonging to the stated party_type are stored: an association block
    carries no legal_form at all rather than an empty one. A client renders
    from party_type and ignores the nulls.

    display_label IS PRESENT HERE AND ABSENT FROM THE REQUEST MODEL. It is
    what a contract and a contract card print as the party name, derived from
    legal_name at capture so that nothing downstream has to branch on
    party_type to find a name.

    THERE IS NO `verified` FIELD AND THERE MUST NEVER BE ONE. Nothing in this
    block has been checked by anybody, so there is nothing for a client to
    badge. A flag here, even one that was always false, would be an invitation
    to render a tick the day somebody adds a review queue that does not exist.
    """

    party_type: str
    display_label: str
    country: str
    address: str
    legal_name: str
    legal_form: str | None = None
    registration_number: str | None = None
    tax_identifier: str | None = None
    representative_name: str | None = None
    representative_capacity: str | None = None


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
    # ONE OF FOUR VALUES, THREE OF WHICH A STOREFRONT HAS TO TELL APART:
    #
    #   "pending"    a handle somebody typed. Nothing has checked it.
    #   "connected"  the creator authorised Kolabo on the platform and the
    #                account was read back through the platform's own API.
    #                Control of the account is proved; identity is not.
    #   "verified"   an admin checked a real identity document.
    #   "rejected"   an admin looked and said no.
    #
    # A BADGE SAYING "VERIFIED" MUST GO ON THE THIRD ONE AND ON NOTHING ELSE.
    # See app.modules.profiles.models.CONNECTED for why the word was not
    # widened to cover a social login, which is the whole reason this field
    # grew a third value rather than reusing one that already existed.
    #
    # A client that has only ever heard of "pending" and "verified" renders
    # "connected" as neither, which is wrong but safe: it understates. The web
    # and mobile changes that give it a badge of its own follow separately.
    status: str
    follower_count: int | None = None
    # WHERE follower_count CAME FROM: "self_reported" (the creator typed it)
    # or "platform_api" (the platform stated it) — see
    # app.modules.profiles.models.FOLLOWER_SOURCES. Null means no number is
    # recorded, or that the row predates these columns and its origin is
    # genuinely unknown; a client should say nothing about a null rather than
    # assume the creator typed it.
    #
    # NOT A SECOND `status`. That field is about the handle — whether the
    # creator controls the account — and a verified handle can perfectly well
    # carry a self-reported number. A client that wants one badge must decide
    # which question it is answering.
    follower_source: str | None = None
    # Stamped only for platform_api, so a client can render "verified on
    # <date>" rather than an undated claim that quietly ages.
    follower_verified_at: datetime | None = None
    enriched: bool = False


class OAuthStartIn(BaseModel):
    """Everything a client may say about an authorization it is starting.

    WHICH IS ALMOST NOTHING, AND THAT IS THE DESIGN. The platform is a path
    parameter and the creator comes from the bearer token, so there is no field
    in this body that could name somebody else's account or another platform's
    provider. The only thing the client gets to choose is where its own user
    ends up afterwards.
    """

    # Where to send the creator's browser once the callback has finished: a web
    # route, or a kolabo:// deep link on mobile. Stored on the state row and
    # read back by the callback rather than being carried through the
    # platform's `state`, which has to stay an opaque unguessable token.
    #
    # VALIDATED AGAINST AN ALLOWLIST, AND NOT BY THIS SCHEMA. The callback now
    # answers a real 302 to this value, which makes it an open-redirect
    # surface, so oauth_service.redirect_allowed decides it: the web app's own
    # origin (settings.web_public_base_url) or a kolabo:// deep link, and
    # nothing else. Not a pydantic pattern here, for two reasons. The rule
    # depends on deployment configuration rather than on the shape of the
    # string, and a schema refusal would be a 422 at the one moment the right
    # answer is to carry on without the value: a destination we will not honour
    # is dropped and logged, and the connection still completes. See
    # oauth_service.start_authorization, which is where the check runs, and
    # _allowlisted_or_discarded, which is why it does not raise.
    redirect_to: str | None = None


class OAuthStartOut(BaseModel):
    """Where to send the creator. The state and the challenge are inside the
    URL the provider built; nothing about the row is exposed."""

    authorize_url: str


class OAuthCallbackOut(BaseModel):
    """What the callback answers when there is nowhere to send the creator.

    THE OTHER ANSWER IS A 302, and which of the two a caller gets depends on
    whether `start` was given an allowlisted `redirect_to`. With one, the
    callback redirects to it and this model is never built. Without one, this
    is the body, byte for byte what it has been since #167. That is what keeps
    the redirect additive: a caller that sends no `redirect_to` cannot tell
    from the outside that redirects exist at all.

    `redirect_to` STAYS ON THE MODEL AND IS ALWAYS NULL HERE, which reads like
    a contradiction and is not. A request that produced this body either named
    no destination or named one the allowlist refused, and the router blanks
    the second case rather than echo a URL it has just declined to send
    anybody to. The field remains because it has been part of the documented
    response since #167 and removing it is a client change, not a server one.
    """

    account: SocialAccountOut
    redirect_to: str | None = None


class SocialPageOut(BaseModel):
    """One Page a creator manages, offered so they can say which one they sell on.

    NOT A SocialAccountOut, AND THE DIFFERENCE IS THE POINT. A SocialAccountOut
    is a row on somebody's profile: a claim this platform is making on their
    behalf, with provenance columns behind it. This is a CHOICE, read live from
    the platform and stored nowhere. Nothing on this model has been recorded
    about anybody, and nothing will be until the creator posts the id back.

    `id` is the platform's own id for the Page. It is the only field a client
    ever sends back, and the server treats it as untrusted when it arrives: see
    oauth_service.select_page, which re-reads the creator's own list rather
    than believing it.

    `follower_count` is null for a Page the platform did not state a number
    for. A client should show nothing there rather than a zero, for the same
    reason SocialAccountOut says nothing about a null.
    """

    id: str
    name: str | None = None
    follower_count: int | None = None


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
    # PARTY DETAILS ARE DELIBERATELY NOT ON THIS MODEL, and will look like an
    # omission to anybody reading the spec beside it. Spec section 4
    # recommends adding has_party_details here so that a creator who has not
    # stated who they are is not discoverable, the same way one without a
    # birth date is not. That is spec section 11 question 1, the founder has
    # not answered it, and it is a product decision rather than a tidy-up: it
    # changes who appears in search. Until she answers, party details gate
    # CONTRACT GENERATION ONLY (contracts/service.py) and nothing else.


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
    # Carries follower_source and follower_verified_at with each account, so
    # the page a brand reads before it spends can say which numbers on it have
    # been checked and which are the creator's own word.
    social_accounts: list[SocialAccountOut]
    # PARTY DETAILS ARE NOT ON THIS MODEL AND MUST NOT BE ADDED TO IT. A party
    # block is a legal name, an address, a registration number and a
    # representative: contract content, visible to a counterparty on a
    # contract they are party to and to admins, and to nobody else. This
    # endpoint is unauthenticated (see the router's module docstring), so a
    # field here would publish a creator's home address to the open internet.

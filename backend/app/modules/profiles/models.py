"""Profile and verification models for Epic B, plus creator packages and media.

Datetimes are naive UTC for consistent comparison across SQLite and PostgreSQL.
Verification document bytes are stored encrypted (see app.core.crypto); the raw
document is never persisted. Public profile images (avatar, portfolio) are NOT
sensitive and are stored as-is in media_assets; object storage replaces the
in-database blob before production.
"""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Verification status values shared by documents and social accounts.
PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
VERIFIED = "verified"

# A SOCIAL ACCOUNT HAS THREE STATES, NOT TWO, AND CONNECTED IS THE NEW MIDDLE
# ONE. It is only ever written to social_accounts.status; a verification
# document has nothing it could be connected to.
#
#   PENDING     a handle somebody typed into a form. An unproven claim, and
#               the state every manually connected account still starts in.
#   CONNECTED   the creator signed in to the platform, granted the
#               permissions, and Kolabo read the account back through the
#               platform's own API using the creator's own token. Control of
#               the account is proved. Nothing about the person is.
#   VERIFIED    an admin read a real identity document and decided. Unchanged
#               by this constant arriving, and still written in exactly one
#               place: admin.service.decide_social.
#
# "VERIFIED" MEANS ONE THING ACROSS THE WHOLE PRODUCT AND IS NOT BEING
# WIDENED. That is the entire reason a third state exists rather than the
# easier change of promoting an OAuth connection straight to VERIFIED. A
# social login proves somebody holds the credentials to an account; it proves
# nothing whatever about who they are, and cannot tell a creator apart from
# the agency that runs their Page or from whoever bought the login. A brand
# reading "verified" next to a name is being told that a person was checked,
# and that promise only stays worth something while it keeps costing an
# identity document. Widening the word would be free here and expensive for
# the rest of this product's life, because it would then mean two different
# things depending on which row it sat on.
#
# The third state exists because the two-state version was ALSO wrong on
# screen: a creator who had logged in to Facebook, granted permissions and
# chosen their Page saw the same "En attente" badge as somebody who had typed
# a handle into a box, and so did every brand looking at them.
CONNECTED = "connected"

# The social account states that nobody with an identity document in front of
# them has decided on yet: what the admin verification queue and the dashboard
# count beside it both mean by "waiting".
#
# BOTH OF THEM, NOT JUST PENDING, so that the queue holds exactly what it held
# before CONNECTED existed. An authorised account used to be written as
# PENDING and therefore stood in front of an admin; it is written as CONNECTED
# now, and a filter on PENDING alone would have silently dropped it out of the
# queue and out of the count on the day this shipped. Proving control of an
# account is not the act an admin performs, so a connected account is still
# waiting for one.
AWAITING_SOCIAL_REVIEW = (PENDING, CONNECTED)

# Where a follower number came from, which until now nothing recorded at all.
#
#   None            no number is recorded — nobody has claimed anything, and
#                   that includes every row written before these columns
#                   existed, because we genuinely do not know where those
#                   numbers came from and a guess would read as a fact.
#   SELF_REPORTED   the creator typed it. Nothing has checked it.
#   PLATFORM_API    the platform itself stated it, in an API response about
#                   its own account. This is the only source that earns a
#                   follower_verified_at timestamp.
#
# THIS IS NOT `status`, AND THE SEPARATION IS THE POINT. `status` above
# answers "does this creator control this handle" — the question an admin
# actually decides in admin.service.decide_social by looking at a proof link.
# These constants answer "who supplied this number", which nobody decides by
# looking at a link. A VERIFIED handle whose count is still SELF_REPORTED is a
# real and common state — it is, in fact, the normal state of every reviewed
# account on the platform today — and collapsing the two would hang a
# verified-looking provenance on a figure nobody has ever counted.
SELF_REPORTED = "self_reported"
PLATFORM_API = "platform_api"
FOLLOWER_SOURCES = {SELF_REPORTED, PLATFORM_API}

# WHAT KIND OF THING SIGNS A CONTRACT. The discriminator inside
# party_details, and the only field in a party block that decides which other
# fields mean anything.
#
#   REGISTERED_COMPANY  an entity with a registration number: a SARL, a
#                       limited company, a GmbH. States its legal form, its
#                       registration number, a tax identifier, and the human
#                       who signs for it together with the capacity they sign
#                       in.
#   SOLE_TRADER         a natural person contracting under their own name.
#                       States their name, and a tax identifier only if they
#                       have one. This is what nearly every creator is, and
#                       what a great many of the buyers in the launch markets
#                       are too.
#   ASSOCIATION         a registered non profit or NGO. Registered, like a
#                       company, and represented by a named person, like a
#                       company, but has no legal form worth printing and
#                       often no tax identifier at all.
#
# SOLE_TRADER IS FIRST AMONG EQUALS AND MUST NEVER READ AS A LESSER OPTION.
# Per the founder, businesses on this platform are explicitly NOT limited to
# registered ones, so the unregistered branch is not a fallback for people who
# failed the real form: it is the ordinary case. A form that buries it, or
# copy that calls it "individual" where the other says "company", is a
# product defect and not a cosmetic one.
#
# A PLAIN SET WITH PYTHON CONSTANTS, not a SQLAlchemy Enum and not a native
# database enum, for the reason SocialAccount.status gives at length below:
# the value lives inside a JSON blob the database has no opinion about, the
# closed set lives in this module, and a fourth type the day an agency needs
# one costs no migration at all.
#
# NOTHING HERE IS VERIFIED. See party_details on both profiles.
REGISTERED_COMPANY = "registered_company"
SOLE_TRADER = "sole_trader"
ASSOCIATION = "association"
PARTY_TYPES = (REGISTERED_COMPANY, SOLE_TRADER, ASSOCIATION)


class InfluencerProfile(Base):
    __tablename__ = "influencer_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    headline: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_media_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Kolabo is bilingual, and the bio is the most read part of a profile: an
    # Ivorian brand should not land on an English bio, nor a Ghanaian brand on
    # a French one. `bio` is the pre-split column, kept until the backfill has
    # been checked in production and then dropped.
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Counts AI draft requests so one creator cannot loop the retry button.
    bio_generations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    categories: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    rate_card: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # Answers to the two standard profile questions, keyed by stable question
    # id ("audience", "brands"). The question wording lives in frontend i18n
    # so it renders in the viewer's language; only the creator's free-text
    # answers are stored, and two fixed questions do not justify a table.
    faq: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # Backs the 18+ gate: creators must be adults (legal register,
    # child-safety item). Enforced in the service on every write, and never
    # exposed on any public payload.
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Optional self-description from a closed set validated at the schema
    # (female, male, other, prefer_not_to_say). Never public: collected for
    # analytics and support, not for buyers.
    gender: Mapped[str | None] = mapped_column(String, nullable=True)
    # Languages the creator works in, e.g. ["fr", "en"]. Public: brands pick
    # creators by the language their audience speaks.
    languages: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # Self reported for now; to be replaced by verified analytics from
    # connected social accounts in a later epic.
    #
    # A CROSS-PLATFORM TOTAL, which is why it carries no provenance columns of
    # its own and why enrichment never overwrites it: no single connected
    # account can state a creator's whole audience, so there is no source to
    # name. The per-platform numbers, which CAN be sourced, live on
    # SocialAccount below.
    follower_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # WHO THIS CREATOR IS ON A CONTRACT, as they state it themselves. The
    # shape is documented on BusinessProfile.party_details, which carries the
    # whole argument once rather than twice; both columns are deliberately
    # identical.
    #
    # WHY A CREATOR NEEDS ONE AT ALL, since display_name already exists.
    # display_name is a storefront name. It is nullable, it is self asserted,
    # and profiles.service._apply_enrichment writes it from whatever a social
    # platform's API returned when the creator connected an account, so a
    # great many of them are handles rather than names. "Signed by @afrovibes"
    # is not a party to an agreement. A contract needs the name the person
    # would write on paper, and the two are different fields on purpose: a
    # creator who rebrands their storefront has not changed who they are.
    #
    # Nearly always SOLE_TRADER in practice, and the same shape is used on
    # both sides anyway so that an agency account can state a company and one
    # renderer still serves both.
    party_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # WHO THIS BUYER IS ON A CONTRACT, as they state it themselves. This
    # column, and the matching one on InfluencerProfile, are the whole of what
    # a generated contract has to work with when it names its parties.
    #
    # WHY company_name WAS NOT ENOUGH. It is one line of free text,
    # overwritten whole on every save with no history, and it is the ONLY
    # thing this table has ever held about the entity. There is no legal form,
    # no registration number, no tax identifier, no address, no representative
    # and no capacity, so a contract could not state any of them, and the
    # signature column on the other side had no legal name in this database to
    # be a signature OF. See claude/kolabo-contract-parties-spec.md.
    #
    # THE SHAPE, which the schema asserts and party_details.py enforces:
    #
    #   party_type      one of PARTY_TYPES above, and it decides the rest
    #   display_label   what to print as the party name. DERIVED server side
    #                   from legal_name at capture, never accepted from a
    #                   client, and stored so that a renderer and a contract
    #                   card have one field to read without branching on the
    #                   type.
    #   country         ISO 3166-1 alpha-2, the country this party contracts
    #                   from. Not restricted to the pilot markets: a buyer
    #                   contracting from France is an ordinary case.
    #   address         free text, a single field, deliberately NOT structured
    #                   into street, city and postcode. Addresses in the
    #                   launch markets do not reliably decompose that way, and
    #                   nothing joins on the parts.
    #   legal_name      the entity, or the natural person for a sole trader
    #
    # then, by party_type: REGISTERED_COMPANY adds legal_form,
    # registration_number, tax_identifier, representative_name and
    # representative_capacity; SOLE_TRADER adds an optional tax_identifier;
    # ASSOCIATION adds registration_number, representative_name and
    # representative_capacity. Only the keys belonging to the stated type are
    # written, so an association block carries no empty legal_form.
    #
    # A DEFAULT, NOT THE RECORD. This column holds the user's CURRENT details
    # and stays editable at any time. What a contract says is the snapshot
    # taken at generation and frozen there (contracts.business_party), so
    # editing this changes the next contract and nothing about one that
    # already exists. party_type is the one field that stops being editable,
    # once any contract has been generated against this profile: changing it
    # retroactively would make past contracts read as though they had been
    # signed by a different kind of entity.
    #
    # NOTHING IN HERE IS VERIFIED AND NO SURFACE MAY IMPLY OTHERWISE. These
    # are self declared, exactly as they would be on a paper contract: the
    # platform records what each party states about itself and checks none of
    # it. Kolabo collects no personal identity document (decided 3 October
    # 2026; migration b1d7e3a05c92 emptied the store of the ones it held), and
    # business_registration documents, which DO exist, are counted rather than
    # read and are not connected to these fields in any way. A tick beside a
    # registration number nobody has looked up is the most expensive lie this
    # product could tell a brand.
    #
    # Nullable because nobody has stated anything yet, and no backfill was
    # possible: company_name alone cannot be promoted into a party block
    # without inventing a party_type and a country for somebody.
    party_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    handle: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False)  # oauth or manual
    # Audience on this specific platform. Self reported until the platform
    # API confirms it; None where the platform exposes no public metric.
    follower_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Where that number came from: one of FOLLOWER_SOURCES, or None when no
    # number is recorded. See the constants above for why this is a separate
    # question from `status` below.
    follower_source: Mapped[str | None] = mapped_column(String, nullable=True)
    # When a platform API stated the number. Set only alongside PLATFORM_API,
    # so a client can render "verified on <date>" instead of an undated claim,
    # and so a stale verification can be told from a fresh one.
    follower_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # PENDING, CONNECTED or VERIFIED, plus REJECTED when an admin said no. The
    # constants above say what each one promises, and in particular why an
    # authorisation earns CONNECTED and never VERIFIED.
    #
    # A PLAIN STRING COLUMN WITH PYTHON CONSTANTS, not a SQLAlchemy Enum and
    # not a native database enum, which is why a third value needed no
    # migration at all: the database has only ever seen a VARCHAR here (see
    # alembic/versions/5f3a9c80d26f_initial_schema.py) and the closed set
    # lives in this module. Anybody turning this into a real enum later owns
    # writing the migration for every value in it.
    status: Mapped[str] = mapped_column(String, default=PENDING, nullable=False)
    proof_url: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class SocialToken(Base):
    """The OAuth credentials behind one connected social account.

    A SEPARATE TABLE, NOT COLUMNS ON SocialAccount, and the reason is the read
    path rather than tidiness. SocialAccount is loaded on every public profile
    view — get_public_profile returns one row per connected account, to anybody,
    with no token anywhere in the request — so token ciphertext hung on that
    model would be SELECTed and carried through the ORM on every storefront hit
    by a stranger, into every log line that prints a row and every future
    `.dict()` somebody writes in a hurry. A separate table means the bytes are
    only ever loaded by code that asks for them by name.

    CIPHERTEXT, NEVER PLAINTEXT, with the same Fernet helpers and the same
    document_encryption_key as VerificationDocument.ciphertext — the pattern
    this module already established for bytes that must not be readable in a
    database dump. An access token is a bearer credential for somebody else's
    account on somebody else's platform: leaking one is not leaking data about
    a creator, it is handing over the ability to act as them.

    ONE ROW PER ACCOUNT (social_account_id is unique). Re-authorising REPLACES
    the credentials rather than appending to a history of them: a superseded
    token is not evidence of anything, and keeping it is keeping another live
    secret alive for as long as the platform honours it.

    NO relationship() BACK TO SocialAccount, deliberately. A relationship is an
    invitation to lazy-load, and the one thing this table exists to prevent is
    tokens arriving somewhere nobody asked for them.
    """

    __tablename__ = "social_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    # Unique AND indexed, which SQLAlchemy emits as one unique index named
    # ix_social_tokens_social_account_id — the same name the migration creates,
    # so a create_all schema and a migrated schema agree.
    social_account_id: Mapped[str] = mapped_column(
        ForeignKey("social_accounts.id"), unique=True, index=True, nullable=False
    )
    access_token_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Nullable because not every provider issues one: an implicit-style grant,
    # or a platform whose access token simply outlives the connection, leaves
    # this empty and the creator re-authorises when it lapses.
    refresh_token_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Nullable for the same reason, and separately from the access expiry
    # because the two run on very different clocks — hours against months.
    refresh_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # The scopes the platform actually granted, which is not always what was
    # asked for. Stored so a failure can be read as "the creator declined the
    # stats permission" rather than as a broken integration.
    scope: Mapped[str | None] = mapped_column(String, nullable=True)
    # The platform's own id for the account (TikTok's open_id, Google's sub).
    # It is what identifies the SAME account across re-authorisations, since a
    # handle can be changed by its owner at any time and an id cannot.
    provider_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class OAuthState(Base):
    """One authorization attempt in flight: the CSRF state and the PKCE verifier.

    THE STATE ROW IS THE AUTHENTICATION FOR THE CALLBACK, and that sentence is
    the entire security surface of this feature. The callback is a browser
    redirect arriving from the platform: it cannot carry a bearer token, there
    is no Authorization header to read, and the caller is — as far as the API
    can tell — an anonymous stranger holding a URL. The only thing that says
    WHOSE profile the resulting account attaches to is `user_id` on the row
    this `state` resolves to. Everything else about the request is attacker
    controlled.

    So the row is written to three rules, all of which are load-bearing:

      * UNGUESSABLE. `state` is secrets.token_urlsafe(32) — 256 bits from a
        CSPRNG. Anything shorter, anything sequential, and anything derived
        from the user id is an account takeover: guess a live state and the
        platform account you just authorised lands on somebody else's profile.
      * SINGLE USE. `consumed` is flipped ATOMICALLY (a conditional UPDATE, not
        a read-then-write) the moment the callback claims it, so a replayed
        callback URL — out of a browser history, a referer header, a shared
        screenshot — is refused rather than replayed.
      * SHORT LIVED. Ten minutes, which is longer than any real authorization
        takes and short enough that a leaked URL is stale before it is read.

    The verifier is PKCE (RFC 7636): the challenge goes out with the
    authorization request and the verifier is presented at the exchange, so an
    authorization code intercepted in transit cannot be redeemed without this
    row. It is stored in plaintext ON PURPOSE and is not a credential: it is
    worthless without the code, worthless after `consumed`, and worthless ten
    minutes from now.

    Rows are not deleted after use. A consumed state is the record that this
    connection happened, and expiry plus a sweep is a better answer than a
    delete that erases the only evidence of a replay attempt.
    """

    __tablename__ = "oauth_states"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    # Unique and indexed: the callback's only lookup, and the uniqueness is
    # what makes "resolves to exactly one creator" a property of the schema
    # rather than of the query that happens to be written above it.
    state: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    code_verifier: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    # Where to send the creator's browser once the callback has finished — a
    # web page or a mobile deep link. Nullable: an API client that just wants
    # the result does not need one.
    redirect_to: Mapped[str | None] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class VerificationDocument(Base):
    __tablename__ = "verification_documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    doc_type: Mapped[str] = mapped_column(String, nullable=False)  # business_registration, the only accepted value
    filename: Mapped[str] = mapped_column(String, nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    status: Mapped[str] = mapped_column(String, default=PENDING, nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class MediaAsset(Base):
    """Public profile image (avatar or portfolio). Blob in the database for now;
    swap for object storage before production."""

    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class PortfolioItem(Base):
    """An image in a creator's portfolio gallery, ordered by position."""

    __tablename__ = "portfolio_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    media_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Package(Base):
    """A fixed-price offering on a creator's profile (the instant-hire model)."""

    __tablename__ = "packages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    deliverable_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_amount: Mapped[int] = mapped_column(Integer, nullable=False)  # minor units
    currency: Mapped[str] = mapped_column(String, nullable=False)
    # Collabstr-style package specs: quantity renders as the "×10" chip and
    # duration as "30 Seconds". Quantity is how many deliverables the bundle
    # contains; the duration pair describes each one and is only set where
    # length is part of the spec (a reel, not a story mention), which is why
    # it stays nullable.
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    duration_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # One of seconds/minutes/hours — closed set enforced at the schema, and
    # always paired with duration_value (service rule).
    duration_unit: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

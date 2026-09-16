"""Auth data models: users, OTP challenges, and password reset tokens.

Datetimes are stored as naive UTC for consistent comparison across SQLite and
PostgreSQL. Use utcnow() everywhere rather than mixing aware and naive values.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# The two halves of a referral. The referrer shared the code; the referee
# signed up with it and then completed an order.
REFERRER = "referrer"
REFEREE = "referee"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    # A CONTACT DETAIL, not an identity, and not collected at registration any
    # more. Nullable and no longer unique: migration f3c0a84e17d9 says why the
    # uniqueness went as well as the NOT NULL, and what update_me gives up by
    # being the only thing left that enforces it.
    #
    # Kept rather than dropped because accounts created before the flip have a
    # number in it, a business's number is what payments/checkout.py puts on
    # the FedaPay customer object, and PATCH /auth/me can still write one.
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    # THE LOGIN IDENTITY. Unique and indexed because no two accounts may be
    # the same mailbox, and because registration, verification, login and
    # password reset all start from a lookup on this column.
    #
    # NOT NULL since b4e9c2a71f05, which is the revision that finished the
    # identity flip: e1b7d4c92f08 made an address unique, f3c0a84e17d9 took
    # the identity away from the phone, and this column now has to BE there
    # as well as be unique. The API layer still decides what a well formed
    # address is and reports a bad one to the person who typed it; the column
    # decides that an account has one at all, which is the half of the rule a
    # service check cannot hold on its own.
    #
    # AN ACCOUNT WITH NO ADDRESS IS THEREFORE NO LONGER REPRESENTABLE. The
    # migration refuses to run rather than invent an address for a row that
    # has none, so any database that has reached head carries one on every
    # user. Code that still reads this column defensively is belt and braces
    # rather than a live case.
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    country_code: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Admin access, and the ONLY thing that grants it. Kept as a flag rather
    # than a fourth role so every existing role check keeps working unchanged:
    # an admin is also an ordinary marketplace user, with a role of their own.
    # Nothing in the API sets this — app.modules.auth.admins reconciles it
    # with a configured list of email addresses on every boot.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # THE GOOGLE ACCOUNT THIS ONE IS LINKED TO, as Google's `sub` claim, or
    # null for the overwhelming majority of rows that have never seen a Google
    # token. Until a7f1c6e3d940 there was no such state anywhere: the claim was
    # verified on every sign in and then dropped, so a settings screen could
    # not say "connected with Google", there was nothing to revoke, and nothing
    # could tell that two Kolabo accounts were one person's single Google
    # account.
    #
    # A COLUMN RATHER THAN A TABLE because there is exactly one provider and at
    # most one value per account. A google_identities table would put a join on
    # the sign in path and give one fact two homes, and it would be justified
    # only by rows this product cannot have: many providers per user, or many
    # links per provider. social_accounts and social_tokens are separate tables
    # for reasons that do not apply here, and the day a second provider arrives
    # is the day that migration earns itself.
    #
    # UNIQUE BECAUSE TWO KOLABO ACCOUNTS MUST NEVER CLAIM ONE GOOGLE IDENTITY,
    # and that is not something the service layer can promise on its own: two
    # sign ins racing through the gap between a SELECT and an UPDATE both pass
    # a check written in Python, and only the database can refuse the second.
    # Indexed for the reason ix_users_email is indexed, because it is looked up
    # by value. Nullable because almost no account has one, and both Postgres
    # and SQLite let any number of rows sit under a unique index with a null in
    # the indexed column.
    #
    # NOT A CREDENTIAL, AND NEVER A RESPONSE FIELD. A `sub` proves nothing on
    # its own (a token signed by Google is what proves something) and it is a
    # stable cross site identifier for a person, so it stays on this row: MeOut
    # carries google_linked, a boolean, because whether the link exists is the
    # only part of it a client has any use for.
    google_sub: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, index=True)
    # Referral: a shareable code (minted lazily, see the auth service) and who
    # brought this user in. What that attribution is worth, and when, is
    # decided in app.modules.auth.referrals.
    referral_code: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, index=True)
    referred_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ReferralCredit(Base):
    """Platform credit earned from a referral.

    One row per recipient per award. The product decisions behind this table —
    why credit and not cash, why the first completed order and not signup —
    live at the top of app.modules.auth.referrals.

    The presence of a "referee" row for a user IS the record that their first
    order has completed and been rewarded; nothing else tracks it, and that is
    what stops a second order paying out again.
    """

    __tablename__ = "referral_credits"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # Minor units and an explicit currency, like every other amount on the
    # platform. Denominated in the RECIPIENT's market, not the order's.
    currency: Mapped[str] = mapped_column(String, nullable=False)
    # REFERRER or REFEREE: which side of the pair this row pays.
    kind: Mapped[str] = mapped_column(String, nullable=False)
    # The other half of the pair: the referrer on a referee row, the referred
    # user on a referrer row. Nullable so an earned credit survives the other
    # account being deleted.
    source_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # The order that triggered the award. A plain string rather than an FK:
    # the credit is already earned and must outlive any later contract
    # housekeeping.
    contract_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Wrong guesses spent against this code. Six digits stays guessable for
    # the whole of a ten minute life unless something counts, and nothing did:
    # a wrong code neither incremented anything nor consumed the challenge,
    # and there is no rate limiting anywhere in the app. See
    # app.modules.auth.otp.MAX_ATTEMPTS, and spend_attempt for why the count
    # is charged to every live code for the account rather than only this row.
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class PasswordResetToken(Base):
    """One reset code, for one account, good once.

    The token column holds a SIX DIGIT CODE, the same shape the registration
    OTP uses, because it is delivered the same way: an email to the address
    that is the login identity. Nobody retypes a 43 character urlsafe string
    from one window into another.

    Which is exactly why the column is INDEXED BUT NOT UNIQUE. Six digits is a
    million values, so across enough resets two accounts WILL be handed the
    same code eventually, and a unique constraint would turn that collision
    into a 500 for whichever user asked second — a locked-out user refused
    entry because somebody unrelated is also resetting. Uniqueness was never
    the property that mattered: a code is looked up together with the address
    it was sent to (see auth.account.confirm_password_reset), so the pair is
    what identifies it, and a bare code on its own is not meant to be an
    identifier at all.

    Six digits also means it has to be guess-proofed the same way the
    registration challenge is, and more urgently: spending a reset code
    changes the password, so an unlimited guess is a takeover rather than a
    nuisance. Hence `attempts` below.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # See OtpChallenge.attempts. Same allowance, same helper, higher stakes.
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

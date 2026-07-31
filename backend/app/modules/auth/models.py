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
    phone: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    country_code: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

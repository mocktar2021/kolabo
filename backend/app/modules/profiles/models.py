"""Profile and verification models for Epic B, plus creator packages and media.

Datetimes are naive UTC for consistent comparison across SQLite and PostgreSQL.
Verification document bytes are stored encrypted (see app.core.crypto); the raw
document is never persisted. Public profile images (avatar, portfolio) are NOT
sensitive and are stored as-is in media_assets; object storage replaces the
in-database blob before production.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, LargeBinary, String, Text
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


class InfluencerProfile(Base):
    __tablename__ = "influencer_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    headline: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_media_id: Mapped[str | None] = mapped_column(String, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    categories: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    rate_card: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # Self reported for now; to be replaced by verified analytics from
    # connected social accounts in a later epic.
    follower_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    status: Mapped[str] = mapped_column(String, default=PENDING, nullable=False)
    proof_url: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class VerificationDocument(Base):
    __tablename__ = "verification_documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    doc_type: Mapped[str] = mapped_column(String, nullable=False)  # business_registration or identity
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
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

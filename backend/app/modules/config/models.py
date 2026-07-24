"""Country configuration model (Epic I, KOL-34).

Country settings move out of a hard coded dict and into a table so a new market
can be added or enabled by an admin without a code change or deploy. Money stays
in minor units elsewhere; this table only records the currency code, the phone
prefix, the intended mobile money provider, and whether the country is live.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CountryConfig(Base):
    __tablename__ = "country_configs"

    code: Mapped[str] = mapped_column(String, primary_key=True)  # ISO 3166-1 alpha-2
    name: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)  # ISO 4217
    phone_prefix: Mapped[str] = mapped_column(String, nullable=False)  # e.g. +229
    phone_example: Mapped[str | None] = mapped_column(String, nullable=True)
    # Selection is not finalized yet, so this stays nullable and is filled per
    # country by an admin once a provider is chosen.
    mobile_money_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

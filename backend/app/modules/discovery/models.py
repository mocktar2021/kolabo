"""Discovery models (Epic C). Favorites shortlist for businesses."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("business_user_id", "influencer_user_id", name="uq_favorite"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    business_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    influencer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

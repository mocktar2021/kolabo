"""Discovery business logic (Epic C).

KOL-19: search influencers by category and follower range. Only searchable
profiles are returned, and verified profiles rank above unverified. At pilot
data volume the candidate set is small (hundreds), so filtering and ordering
run in application code; this can move to PostgreSQL indexes or full text search
when volume grows.
KOL-20: favorites shortlist for a business, persisted and removable.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.discovery.models import Favorite
from app.modules.profiles import models as profiles


def _is_searchable(p: profiles.InfluencerProfile) -> bool:
    return bool(p.bio) and bool(p.categories) and bool(p.rate_card)


def search_influencers(
    db: Session,
    category: str | None = None,
    min_followers: int | None = None,
    max_followers: int | None = None,
    country: str | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    rows = (
        db.query(profiles.InfluencerProfile, User)
        .join(User, User.id == profiles.InfluencerProfile.user_id)
        .all()
    )
    matched = []
    for prof, user in rows:
        if not _is_searchable(prof):
            continue
        if country and user.country_code != country:
            continue
        if category and category not in (prof.categories or []):
            continue
        if min_followers is not None or max_followers is not None:
            fc = prof.follower_count
            if fc is None:
                continue
            if min_followers is not None and fc < min_followers:
                continue
            if max_followers is not None and fc > max_followers:
                continue
        if q and (not prof.bio or q.lower() not in prof.bio.lower()):
            continue
        matched.append((prof, user))

    # Verified first, then higher follower count, then oldest profile first.
    def sort_key(item):
        prof, user = item
        fc = prof.follower_count if prof.follower_count is not None else -1
        return (0 if user.is_verified else 1, -fc, prof.created_at)

    matched.sort(key=sort_key)
    page = matched[offset : offset + limit]
    return [
        {
            "user_id": prof.user_id,
            "bio": prof.bio,
            "categories": prof.categories,
            "follower_count": prof.follower_count,
            "country_code": user.country_code,
            "is_verified": user.is_verified,
        }
        for prof, user in page
    ]


def add_favorite(db: Session, business_user_id: str, influencer_user_id: str) -> dict:
    if db.query(User).filter(User.id == influencer_user_id).first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Influencer not found")
    existing = (
        db.query(Favorite)
        .filter(Favorite.business_user_id == business_user_id, Favorite.influencer_user_id == influencer_user_id)
        .first()
    )
    if existing is None:
        db.add(Favorite(business_user_id=business_user_id, influencer_user_id=influencer_user_id))
        db.commit()
    return {"influencer_user_id": influencer_user_id}


def remove_favorite(db: Session, business_user_id: str, influencer_user_id: str) -> None:
    fav = (
        db.query(Favorite)
        .filter(Favorite.business_user_id == business_user_id, Favorite.influencer_user_id == influencer_user_id)
        .first()
    )
    if fav is not None:
        db.delete(fav)
        db.commit()


def list_favorites(db: Session, business_user_id: str) -> list[dict]:
    favs = (
        db.query(Favorite)
        .filter(Favorite.business_user_id == business_user_id)
        .order_by(Favorite.created_at.asc())
        .all()
    )
    return [{"influencer_user_id": f.influencer_user_id} for f in favs]

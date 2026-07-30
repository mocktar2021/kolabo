"""Discovery business logic (Epic C).

KOL-19: search influencers by category and follower range. Only searchable
profiles are returned, and verified profiles rank above unverified. At pilot
data volume the candidate set is small (hundreds), so filtering and ordering
run in application code; this can move to PostgreSQL indexes or full text search
when volume grows.
KOL-20: favorites shortlist for a business, persisted and removable.

Results carry the display name, photo, rating, and starting package price so a
result card can be shown without a second request per creator.
"""
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.discovery.models import Favorite
from app.modules.profiles import models as profiles
from app.modules.trust_safety import models as trust_safety


def _is_searchable(p: profiles.InfluencerProfile, has_package: bool) -> bool:
    """A profile is discoverable once it says who it is, what it covers, and
    what it costs. A published package counts as pricing, so a creator using
    packages does not also have to fill the legacy rate card."""
    return bool(p.bio) and bool(p.categories) and (bool(p.rate_card) or has_package)


def _starting_prices(db: Session) -> dict:
    """Cheapest active package per creator, as {user_id: (amount, currency)}."""
    rows = (
        db.query(profiles.Package.user_id, profiles.Package.price_amount, profiles.Package.currency)
        .filter(profiles.Package.is_active.is_(True))
        .order_by(profiles.Package.user_id, profiles.Package.price_amount.asc())
        .all()
    )
    out: dict = {}
    for user_id, amount, currency in rows:
        if user_id not in out:
            out[user_id] = (amount, currency)
    return out


def _rating_summary(db: Session) -> dict:
    """Revealed review average and count per creator, as {user_id: (avg, count)}."""
    rows = (
        db.query(
            trust_safety.Review.reviewee_user_id,
            func.avg(trust_safety.Review.stars),
            func.count(trust_safety.Review.id),
        )
        .filter(trust_safety.Review.revealed.is_(True))
        .group_by(trust_safety.Review.reviewee_user_id)
        .all()
    )
    return {uid: (round(float(avg), 2), int(count)) for uid, avg, count in rows}


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
    prices = _starting_prices(db)
    ratings = _rating_summary(db)

    matched = []
    for prof, user in rows:
        if not _is_searchable(prof, prof.user_id in prices):
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
        if q:
            haystack = " ".join(filter(None, [prof.bio, prof.display_name, prof.headline])).lower()
            if q.lower() not in haystack:
                continue
        matched.append((prof, user))

    # Verified first, then higher follower count, then oldest profile first.
    def sort_key(item):
        prof, user = item
        fc = prof.follower_count if prof.follower_count is not None else -1
        return (0 if user.is_verified else 1, -fc, prof.created_at)

    matched.sort(key=sort_key)
    page = matched[offset : offset + limit]

    results = []
    for prof, user in page:
        price = prices.get(prof.user_id)
        avg, count = ratings.get(prof.user_id, (None, 0))
        results.append(
            {
                "user_id": prof.user_id,
                "display_name": prof.display_name,
                "headline": prof.headline,
                "avatar_url": f"/profiles/media/{prof.avatar_media_id}" if prof.avatar_media_id else None,
                "bio": prof.bio,
                "categories": prof.categories,
                "follower_count": prof.follower_count,
                "country_code": user.country_code,
                "is_verified": user.is_verified,
                "starting_price_amount": price[0] if price else None,
                "starting_price_currency": price[1] if price else None,
                "average_stars": avg,
                "review_count": count,
            }
        )
    return results


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

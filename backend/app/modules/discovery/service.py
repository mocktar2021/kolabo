"""Discovery business logic (Epic C).

KOL-19: search influencers by category and follower range. Only searchable
profiles are returned, and verified profiles rank above unverified. At pilot
data volume the candidate set is small (hundreds), so filtering and ordering
run in application code; this can move to PostgreSQL indexes or full text search
when volume grows.
KOL-20: favorites shortlist for a business, persisted and removable.

Results carry the display name, cover image, per platform audience, rating, and
starting package price so a result card can be shown without a second request
per creator.

The landing page's featured strip lives next door in discovery.featured. It
reuses _is_searchable, _card_context and _result_card from here rather than
restating any of them: two definitions of "who is live" would mean a creator
visible in one surface and missing from the other, which is a bug nobody
reports because each screen looks fine on its own.
"""
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.identity import creator_identities
from app.core.platforms import SOCIAL_PLATFORMS
from app.core.pricing import MIN_LIVE_PACKAGES
from app.modules.auth.models import User
from app.modules.discovery.models import Favorite
from app.modules.profiles import models as profiles
from app.modules.trust_safety import models as trust_safety


def _is_searchable(p: profiles.InfluencerProfile, active_package_count: int) -> bool:
    """A profile is discoverable once it says who it is, what it covers, and
    has a real storefront: at least MIN_LIVE_PACKAGES active packages, the
    same bar profiles.onboarding_status sets for going live. Searchable and
    live must not diverge, or a profile the wizard calls live could be
    invisible in search. (Going live additionally requires a birth date; that
    only tightens "live", so every live profile is still searchable.) A bio in
    either language counts, exactly as it does for onboarding."""
    has_bio = bool(p.bio_fr or p.bio_en or p.bio)
    return has_bio and bool(p.categories) and active_package_count >= MIN_LIVE_PACKAGES


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


def _active_package_counts(db: Session) -> dict:
    """Active packages per creator, as {user_id: count}. Feeds the searchable
    check, which needs the count and not just the cheapest price."""
    rows = (
        db.query(profiles.Package.user_id, func.count(profiles.Package.id))
        .filter(profiles.Package.is_active.is_(True))
        .group_by(profiles.Package.user_id)
        .all()
    )
    return {user_id: int(count) for user_id, count in rows}


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


def _socials_by_user(db: Session) -> dict:
    """Connected accounts per creator, biggest audience first."""
    rows = (
        db.query(profiles.SocialAccount)
        .order_by(profiles.SocialAccount.created_at.asc())
        .all()
    )
    out: dict = {}
    for a in rows:
        out.setdefault(a.user_id, []).append(
            {"platform": a.platform, "handle": a.handle, "follower_count": a.follower_count}
        )
    for items in out.values():
        items.sort(key=lambda i: i["follower_count"] or -1, reverse=True)
    return out


def _cover_by_user(db: Session) -> dict:
    """First portfolio image per creator, used as the card cover."""
    rows = (
        db.query(profiles.PortfolioItem)
        .order_by(profiles.PortfolioItem.user_id, profiles.PortfolioItem.position.asc())
        .all()
    )
    out: dict = {}
    for item in rows:
        out.setdefault(item.user_id, f"/profiles/media/{item.media_id}")
    return out


def _active_package_platforms(db: Session) -> set:
    """(user_id, platform) pairs with an active package. An active package
    counts as presence on a platform: a UGC creator has no account to connect,
    the package itself is what they sell there."""
    rows = (
        db.query(profiles.Package.user_id, profiles.Package.platform)
        .filter(profiles.Package.is_active.is_(True))
        .all()
    )
    return set(rows)


def _card_context(db: Session) -> dict:
    """Everything a result card needs, looked up once for the whole page.

    Five queries however many creators come back, never five per creator —
    that is the reason these are maps keyed by user id rather than per-row
    lookups. Gathered into one object so a second surface showing the same
    card (discovery.featured) cannot accidentally load four of the five and
    render a strip of creators with no prices on them.
    """
    return {
        "prices": _starting_prices(db),
        "package_counts": _active_package_counts(db),
        "ratings": _rating_summary(db),
        "socials": _socials_by_user(db),
        "covers": _cover_by_user(db),
    }


def _result_card(prof: profiles.InfluencerProfile, user: User, ctx: dict) -> dict:
    """One creator as a card, in the one shape every discovery surface shows.

    Extracted from search so the featured strip is literally the same card
    rather than a copy of it. A copy is how a field gets added to search and
    quietly goes missing from the landing page — the two would drift on the
    exact screen where a brand forms its first impression of the roster.
    """
    price = ctx["prices"].get(prof.user_id)
    avg, count = ctx["ratings"].get(prof.user_id, (None, 0))
    return {
        "user_id": prof.user_id,
        "display_name": prof.display_name,
        "headline": prof.headline,
        "location": prof.location,
        "avatar_url": f"/profiles/media/{prof.avatar_media_id}" if prof.avatar_media_id else None,
        "cover_url": ctx["covers"].get(prof.user_id),
        "socials": ctx["socials"].get(prof.user_id, []),
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


def search_influencers(
    db: Session,
    category: str | None = None,
    min_followers: int | None = None,
    max_followers: int | None = None,
    country: str | None = None,
    q: str | None = None,
    platform: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    # An unknown platform can match nobody. Treat it like an unknown category
    # (empty results) rather than erroring the whole search page: the filter
    # values come from a UI selector, not free text, so a mismatch means a
    # stale client, and a quiet empty list degrades better than a 400.
    if platform is not None and platform not in SOCIAL_PLATFORMS:
        return []

    rows = (
        db.query(profiles.InfluencerProfile, User)
        .join(User, User.id == profiles.InfluencerProfile.user_id)
        .all()
    )
    ctx = _card_context(db)
    package_platforms = _active_package_platforms(db) if platform else set()

    matched = []
    for prof, user in rows:
        if not _is_searchable(prof, ctx["package_counts"].get(prof.user_id, 0)):
            continue
        if country and user.country_code != country:
            continue
        if category and category not in (prof.categories or []):
            continue
        if platform:
            # Presence on a platform is a connected social account or an
            # active package sold on it. Accounts come from the same map the
            # result card shows, so the filter and the card always agree.
            has_account = any(
                s["platform"] == platform for s in ctx["socials"].get(prof.user_id, [])
            )
            if not has_account and (prof.user_id, platform) not in package_platforms:
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

    return [_result_card(prof, user, ctx) for prof, user in page]


def _countries(db: Session, user_ids: list[str]) -> dict:
    """Country per user, in one query.

    The only thing a favourite row takes from the users table, and it stays
    the only thing: the sole other identifier a user row holds is a phone
    number, and a phone number is never part of a payload handed to the other
    side of a deal. Who the creator IS — name, photo, audience — comes from
    app.core.identity, which every creator-facing list now shares.
    """
    if not user_ids:
        return {}
    return dict(db.query(User.id, User.country_code).filter(User.id.in_(set(user_ids))).all())


def _favorite_out(influencer_user_id: str, identity: dict, country_code: str | None) -> dict:
    return {
        "influencer_user_id": influencer_user_id,
        "country_code": country_code,
        **identity,
    }


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
    # The same card shape the list returns: the row the client just added
    # renders as a person immediately, instead of as an id until the next
    # refresh.
    identity = creator_identities(db, [influencer_user_id])[influencer_user_id]
    country = _countries(db, [influencer_user_id]).get(influencer_user_id)
    return _favorite_out(influencer_user_id, identity, country)


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
    """The business shortlist, as cards rather than as ids.

    Inviting someone to a campaign starts here, so the row has to say who the
    person is: a name, a face, and the audience they can reach. That identity
    is the shared one (app.core.identity), which is the same shape the
    campaign page's invitations and proposals now carry — a business should
    not have to recognise the same creator from two different card layouts.

    Three queries for the whole shortlist regardless of its length, not three
    per row: a twenty-creator list used to be what turned into forty round
    trips.
    """
    favs = (
        db.query(Favorite)
        .filter(Favorite.business_user_id == business_user_id)
        .order_by(Favorite.created_at.asc())
        .all()
    )
    user_ids = [f.influencer_user_id for f in favs]
    identities = creator_identities(db, user_ids)
    countries = _countries(db, user_ids)
    return [
        _favorite_out(
            f.influencer_user_id,
            identities[f.influencer_user_id],
            countries.get(f.influencer_user_id),
        )
        for f in favs
    ]

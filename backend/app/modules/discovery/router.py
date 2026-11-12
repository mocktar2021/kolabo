"""Epic C (KOL-3): Discovery."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import get_current_user_id, get_optional_user_id
from app.modules.discovery import featured, schemas, service

router = APIRouter()


@router.get("/search", response_model=list[schemas.InfluencerSearchResult])
def search_influencers(
    category: str | None = None,
    min_followers: int | None = None,
    max_followers: int | None = None,
    country: str | None = None,
    q: str | None = None,
    platform: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    viewer_id: str | None = Depends(get_optional_user_id),
):
    """Search influencers by category, follower range, and platform. Verified rank first. KOL-19.

    STILL PUBLIC. The optional dependency identifies a caller when there is
    one and answers None when there is not, so a brand with no account sees
    the whole roster exactly as before. A token buys a SHORTER list, never
    the right to a list: anyone the viewer is blocked with is dropped.
    """
    return service.search_influencers(
        db,
        category=category,
        min_followers=min_followers,
        max_followers=max_followers,
        country=country,
        q=q,
        platform=platform,
        limit=limit,
        offset=offset,
        viewer_id=viewer_id,
    )


@router.get("/featured", response_model=list[schemas.InfluencerSearchResult])
def featured_creators(
    limit: int = featured.DEFAULT_FEATURED_LIMIT,
    db: Session = Depends(get_db),
    viewer_id: str | None = Depends(get_optional_user_id),
):
    """A random sample of searchable creators for the landing page strip.

    Same eligibility rule and same card as /search, different ordering: search
    is deterministic on purpose, which meant the landing page showed the same
    eight faces on every visit and the ninth-ranked creator was invisible to
    every brand that never scrolled. This one shuffles, so the roster gets
    seen.

    Public, exactly like /search: a creator's storefront exists to be found,
    and putting the landing page behind a login would mean a brand has to sign
    up before it can see whether anybody is on the platform. Blocks are
    honoured for a signed-in viewer for the same reason they are in search:
    a face somebody blocked must not come back on the home page.
    """
    return featured.featured_creators(db, limit, viewer_id=viewer_id)


@router.post("/favorites/{influencer_id}", response_model=schemas.FavoriteOut, status_code=status.HTTP_201_CREATED)
def add_favorite(
    influencer_id: str,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Save an influencer to the current business favorites. KOL-20."""
    return service.add_favorite(db, business_user_id, influencer_id)


@router.delete("/favorites/{influencer_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    influencer_id: str,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    service.remove_favorite(db, business_user_id, influencer_id)


@router.get("/favorites", response_model=list[schemas.FavoriteOut])
def list_favorites(
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    return service.list_favorites(db, business_user_id)

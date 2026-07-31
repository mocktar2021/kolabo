"""Epic C (KOL-3): Discovery."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import get_current_user_id
from app.modules.discovery import schemas, service

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
):
    """Search influencers by category, follower range, and platform. Verified rank first. KOL-19."""
    return service.search_influencers(db, category, min_followers, max_followers, country, q, platform, limit, offset)


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

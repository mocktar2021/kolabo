"""Epic C (KOL-3): Discovery."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/search")
def search_influencers():
    """See KOL-19. Verified profiles rank above unverified."""
    raise NotImplementedError


@router.post("/favorites/{influencer_id}")
def add_favorite(influencer_id: str):
    """See KOL-20."""
    raise NotImplementedError

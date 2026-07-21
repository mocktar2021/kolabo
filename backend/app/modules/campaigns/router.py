"""Epic D (KOL-11): Campaigns & Collaboration."""
from fastapi import APIRouter

router = APIRouter()


@router.post("/")
def create_campaign():
    """See KOL-21."""
    raise NotImplementedError


@router.post("/{campaign_id}/invite")
def invite_influencer(campaign_id: str):
    """See KOL-22."""
    raise NotImplementedError


@router.post("/{campaign_id}/proposals")
def submit_proposal(campaign_id: str):
    """See KOL-23."""
    raise NotImplementedError

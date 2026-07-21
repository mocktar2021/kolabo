"""Epic H (KOL-8): Trust, Safety & Reputation."""
from fastapi import APIRouter

router = APIRouter()


@router.post("/campaigns/{campaign_id}/rate")
def rate_campaign(campaign_id: str):
    """See KOL-31. Double-blind reveal — unlocks after both submit."""
    raise NotImplementedError


@router.post("/reports")
def report_user():
    """See KOL-32."""
    raise NotImplementedError

"""Epic G (KOL-7): Payments & Escrow. Highest-risk module — see Part 18.

Mobile Money providers sit behind an internal abstraction so provider
switching doesn't touch escrow/business logic. No provider is wired up
yet — provider selection is an open item pending direct outreach.
"""
from fastapi import APIRouter

router = APIRouter()


@router.post("/campaigns/{campaign_id}/fund")
def fund_escrow(campaign_id: str):
    """See KOL-28."""
    raise NotImplementedError


@router.post("/campaigns/{campaign_id}/release")
def release_escrow(campaign_id: str):
    """See KOL-36. Commission deducted automatically on release."""
    raise NotImplementedError


@router.post("/disputes/{campaign_id}/resolve")
def resolve_dispute(campaign_id: str):
    """See KOL-37. Admin manual decision at MVP."""
    raise NotImplementedError

"""Epic D (KOL-11): Campaigns and Collaboration."""
from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import get_current_user_id
from app.modules.campaigns import schemas, service

router = APIRouter()


@router.post("/", response_model=schemas.CampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(
    payload: schemas.CampaignCreate,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Create a campaign as draft, or published if publish is true. KOL-21."""
    return service.create_campaign(db, business_user_id, payload)


@router.post("/{campaign_id}/publish", response_model=schemas.CampaignOut)
def publish_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Publish a draft once budget, deliverables, and deadline are set. KOL-21."""
    return service.publish_campaign(db, campaign_id, business_user_id)


@router.post("/{campaign_id}/invitations", response_model=schemas.InvitationOut, status_code=status.HTTP_201_CREATED)
def invite_influencer(
    campaign_id: str,
    influencer_id: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Invite a verified influencer to a published campaign. KOL-22."""
    return service.invite_influencer(db, campaign_id, business_user_id, influencer_id)


@router.post("/{campaign_id}/proposals", response_model=schemas.ProposalOut, status_code=status.HTTP_201_CREATED)
def submit_proposal(
    campaign_id: str,
    payload: schemas.ProposalIn,
    db: Session = Depends(get_db),
    influencer_user_id: str = Depends(get_current_user_id),
):
    """Submit a proposal. Resubmitting creates a new version. KOL-23."""
    return service.submit_proposal(db, campaign_id, influencer_user_id, payload)

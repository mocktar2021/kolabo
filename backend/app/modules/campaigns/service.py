"""Campaigns and collaboration business logic (Epic D).

KOL-21: create a campaign brief. Draft save is allowed with any fields;
publishing requires budget, deliverables, and a deadline.
KOL-22: invite a specific influencer. Blocked if the influencer is not verified;
the influencer is notified.
KOL-23: submit a proposal. A proposal is locked once submitted, so an edit is a
new version and the previous one is superseded; the business is notified.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.campaigns import models, schemas
from app.modules.notifications.service import notify


def _require_campaign_owner(db: Session, campaign_id: str, business_user_id: str) -> models.Campaign:
    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.business_user_id != business_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your campaign")
    return campaign


def _publish_ready(campaign: models.Campaign) -> bool:
    return bool(campaign.budget_amount) and bool(campaign.deliverables) and campaign.deadline is not None


def _to_out(campaign: models.Campaign) -> dict:
    return {
        "id": campaign.id,
        "business_user_id": campaign.business_user_id,
        "title": campaign.title,
        "budget_amount": campaign.budget_amount,
        "budget_currency": campaign.budget_currency,
        "deliverables": campaign.deliverables,
        "deadline": campaign.deadline,
        "status": campaign.status,
    }


def create_campaign(db: Session, business_user_id: str, payload: schemas.CampaignCreate) -> dict:
    deliverables = [d.model_dump() for d in payload.deliverables]
    campaign = models.Campaign(
        business_user_id=business_user_id,
        title=payload.title,
        budget_amount=payload.budget_amount,
        budget_currency=payload.budget_currency,
        deliverables=deliverables,
        deadline=payload.deadline,
        status=models.DRAFT,
    )
    if payload.publish:
        if not _publish_ready(campaign):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Budget, deliverables, and deadline are required to publish",
            )
        campaign.status = models.PUBLISHED
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _to_out(campaign)


def publish_campaign(db: Session, campaign_id: str, business_user_id: str) -> dict:
    campaign = _require_campaign_owner(db, campaign_id, business_user_id)
    if not _publish_ready(campaign):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Budget, deliverables, and deadline are required to publish",
        )
    campaign.status = models.PUBLISHED
    db.commit()
    db.refresh(campaign)
    return _to_out(campaign)


def invite_influencer(db: Session, campaign_id: str, business_user_id: str, influencer_user_id: str) -> dict:
    campaign = _require_campaign_owner(db, campaign_id, business_user_id)
    if campaign.status != models.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Publish the campaign before inviting")
    influencer = db.query(User).filter(User.id == influencer_user_id).first()
    if influencer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Influencer not found")
    if not influencer.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This influencer is not verified yet and cannot be invited",
        )
    invitation = models.CampaignInvitation(
        campaign_id=campaign_id, influencer_user_id=influencer_user_id, status=models.INVITED
    )
    db.add(invitation)
    notify(db, influencer_user_id, "campaign_invitation", f"You were invited to the campaign {campaign.title}")
    db.commit()
    db.refresh(invitation)
    return {
        "id": invitation.id,
        "campaign_id": invitation.campaign_id,
        "influencer_user_id": invitation.influencer_user_id,
        "status": invitation.status,
    }


def submit_proposal(db: Session, campaign_id: str, influencer_user_id: str, payload: schemas.ProposalIn) -> dict:
    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.status != models.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign is not open for proposals")

    previous = (
        db.query(models.Proposal)
        .filter(
            models.Proposal.campaign_id == campaign_id,
            models.Proposal.influencer_user_id == influencer_user_id,
            models.Proposal.status == models.SUBMITTED,
        )
        .order_by(models.Proposal.version.desc())
        .first()
    )
    next_version = 1
    if previous is not None:
        previous.status = models.SUPERSEDED
        next_version = previous.version + 1

    proposal = models.Proposal(
        campaign_id=campaign_id,
        influencer_user_id=influencer_user_id,
        version=next_version,
        rate_amount=payload.rate_amount,
        rate_currency=payload.rate_currency.upper(),
        timeline_days=payload.timeline_days,
        status=models.SUBMITTED,
    )
    db.add(proposal)
    notify(db, campaign.business_user_id, "proposal_submitted", f"A new proposal was submitted for {campaign.title}")
    db.commit()
    db.refresh(proposal)
    return {
        "id": proposal.id,
        "campaign_id": proposal.campaign_id,
        "influencer_user_id": proposal.influencer_user_id,
        "version": proposal.version,
        "rate_amount": proposal.rate_amount,
        "rate_currency": proposal.rate_currency,
        "timeline_days": proposal.timeline_days,
        "status": proposal.status,
    }

"""Campaigns and collaboration business logic (Epic D).

KOL-21: create a campaign brief. Draft save is allowed with any fields;
publishing requires budget, deliverables, and a deadline. Every deliverable a
brief does name is validated against the shared platform catalog, the same
source of truth packages sell from.
KOL-22: invite a specific influencer. Blocked if the influencer is not verified;
the influencer is notified.
KOL-23: submit a proposal. A proposal is locked once submitted, so an edit is a
new version and the previous one is superseded; the business is notified.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.platforms import PLATFORM_DELIVERABLES, is_valid_pair
from app.modules.auth.models import User
from app.modules.campaigns import models, schemas
from app.modules.notifications.service import notify

# Nobody briefs a hundred-plus of anything in one campaign; past that the
# number is a typo (an amount pasted into the quantity box), so reject it
# instead of inviting creators to an impossible job.
MAX_DELIVERABLE_QUANTITY = 100

# The role that may not author a brief. Stated as who is excluded rather than
# who is allowed: a new buyer-side role should be able to brief on the day it
# is introduced, without anyone remembering to add it to a whitelist here.
AUTHOR_EXCLUDED_ROLE = "influencer"


def _require_campaign_owner(db: Session, campaign_id: str, business_user_id: str) -> models.Campaign:
    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.business_user_id != business_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your campaign")
    return campaign


def _require_campaign_author(db: Session, user_id: str) -> User:
    """Only the buying side of the market may author a brief.

    A campaign is a brand-side artifact: a brief with a budget that creators
    bid on. A creator's equivalent is a package, which they price and sell
    themselves. A brief posted by a creator muddles who is buying, and every
    step after this one assumes a business counterparty — invitations go from
    the campaign owner to a creator, proposals come back the other way, and
    the contract names the campaign owner as the payer.

    Agencies buy on behalf of brands, so they sit on the same side as a
    business and are allowed through.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role == AUTHOR_EXCLUDED_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only businesses and agencies can create campaigns.",
        )
    return user


def _validate_deliverables(deliverables: list) -> None:
    """Reject briefs that ask for something no platform sells.

    Same catalog and same message style as the packages module's
    _validate_pair: the error names the offending pair and lists what IS
    allowed, so the fix is in the message. An empty list passes untouched —
    drafts are allowed to have no deliverables yet; whether a campaign may be
    published without any is _publish_ready's call, not this one's.
    """
    for d in deliverables:
        platform = d.get("platform")
        deliverable_type = d.get("type")
        if platform not in PLATFORM_DELIVERABLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{platform} is not a supported platform. Allowed: {', '.join(sorted(PLATFORM_DELIVERABLES))}",
            )
        if not is_valid_pair(platform, deliverable_type):
            allowed = ", ".join(PLATFORM_DELIVERABLES.get(platform, [])) or "none"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{deliverable_type} is not available on {platform}. Allowed: {allowed}",
            )
        quantity = d.get("quantity")
        # bool is an int subclass in Python, so `true` would otherwise slip
        # through as a quantity of 1.
        if not isinstance(quantity, int) or isinstance(quantity, bool) or not (
            1 <= quantity <= MAX_DELIVERABLE_QUANTITY
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Deliverable quantity must be a whole number between 1 and {MAX_DELIVERABLE_QUANTITY}",
            )


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
    # Checked before anything is validated or written: who may author a brief
    # is a question about the caller, not about the payload, and answering it
    # first keeps a creator from getting field-level errors on a request that
    # was never going to be accepted.
    _require_campaign_author(db, business_user_id)
    deliverables = [d.model_dump() for d in payload.deliverables]
    # Validated even for drafts: a draft with deliverables the catalog does
    # not recognise would only blow up later, at publish, when the fix is no
    # longer fresh in the author's mind.
    _validate_deliverables(deliverables)
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
    # Re-checked at publish even though create validates too: rows saved
    # before this validation existed (or edited outside the API) must not
    # become a live brief asking creators for something that does not exist.
    _validate_deliverables(campaign.deliverables or [])
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


def _invitation_out(inv: models.CampaignInvitation) -> dict:
    return {
        "id": inv.id,
        "campaign_id": inv.campaign_id,
        "influencer_user_id": inv.influencer_user_id,
        "status": inv.status,
    }


def _proposal_out(p: models.Proposal) -> dict:
    return {
        "id": p.id,
        "campaign_id": p.campaign_id,
        "influencer_user_id": p.influencer_user_id,
        "version": p.version,
        "rate_amount": p.rate_amount,
        "rate_currency": p.rate_currency,
        "timeline_days": p.timeline_days,
        "status": p.status,
    }


def list_my_campaigns(db: Session, business_user_id: str) -> list[dict]:
    rows = (
        db.query(models.Campaign)
        .filter(models.Campaign.business_user_id == business_user_id)
        .order_by(models.Campaign.created_at.desc())
        .all()
    )
    return [_to_out(c) for c in rows]


def get_campaign_detail(db: Session, campaign_id: str, business_user_id: str) -> dict:
    campaign = _require_campaign_owner(db, campaign_id, business_user_id)
    invitations = (
        db.query(models.CampaignInvitation)
        .filter(models.CampaignInvitation.campaign_id == campaign_id)
        .order_by(models.CampaignInvitation.created_at.desc())
        .all()
    )
    proposals = (
        db.query(models.Proposal)
        .filter(models.Proposal.campaign_id == campaign_id)
        .order_by(models.Proposal.version.desc())
        .all()
    )
    out = _to_out(campaign)
    out["invitations"] = [_invitation_out(i) for i in invitations]
    out["proposals"] = [_proposal_out(p) for p in proposals]
    return out


def list_my_invitations(db: Session, influencer_user_id: str) -> list[dict]:
    invitations = (
        db.query(models.CampaignInvitation)
        .filter(models.CampaignInvitation.influencer_user_id == influencer_user_id)
        .order_by(models.CampaignInvitation.created_at.desc())
        .all()
    )
    result = []
    for inv in invitations:
        campaign = db.query(models.Campaign).filter(models.Campaign.id == inv.campaign_id).first()
        if campaign is None:
            continue
        item = _invitation_out(inv)
        item["campaign"] = _to_out(campaign)
        result.append(item)
    return result

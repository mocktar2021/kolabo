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
from app.modules.profiles.models import BusinessProfile, InfluencerProfile

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
    identity = _proposer_identity(db, [influencer_user_id]).get(influencer_user_id)
    return _proposal_out(proposal, identity)


def _invitation_out(inv: models.CampaignInvitation) -> dict:
    return {
        "id": inv.id,
        "campaign_id": inv.campaign_id,
        "influencer_user_id": inv.influencer_user_id,
        "status": inv.status,
    }


def _proposer_identity(db: Session, influencer_user_ids: list[str]) -> dict:
    """Display name and photo for the creators behind a set of proposals.

    A business reviewing proposals is choosing between people, and a list of
    ids gives it nothing to choose with: "Créateur 424275c0" is not somebody
    you can hire. One query for the whole list, not one per row — a campaign
    with thirty proposals should not cost thirty extra round trips.

    Null when the creator has no profile yet, and null is where it stops. The
    users table could supply a phone number and nothing else, and a phone
    number is never part of a payload handed to the other side of a deal:
    that is the difference between a marketplace and an introduction service.
    """
    if not influencer_user_ids:
        return {}
    rows = (
        db.query(
            InfluencerProfile.user_id,
            InfluencerProfile.display_name,
            InfluencerProfile.avatar_media_id,
        )
        .filter(InfluencerProfile.user_id.in_(set(influencer_user_ids)))
        .all()
    )
    return {
        user_id: {
            "display_name": display_name,
            # Same URL shape the profiles module builds its media links from,
            # so one media route serves the proposal list too.
            "avatar_url": f"/profiles/media/{avatar_media_id}" if avatar_media_id else None,
        }
        for user_id, display_name, avatar_media_id in rows
    }


def _proposal_out(p: models.Proposal, identity: dict | None = None) -> dict:
    identity = identity or {}
    return {
        "id": p.id,
        "campaign_id": p.campaign_id,
        "influencer_user_id": p.influencer_user_id,
        "version": p.version,
        "rate_amount": p.rate_amount,
        "rate_currency": p.rate_currency,
        "timeline_days": p.timeline_days,
        "status": p.status,
        "display_name": identity.get("display_name"),
        "avatar_url": identity.get("avatar_url"),
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
    # Looked up once for the whole page rather than per proposal row.
    identities = _proposer_identity(db, [p.influencer_user_id for p in proposals])
    out = _to_out(campaign)
    out["invitations"] = [_invitation_out(i) for i in invitations]
    out["proposals"] = [_proposal_out(p, identities.get(p.influencer_user_id)) for p in proposals]
    return out


def _company_name(db: Session, business_user_id: str) -> str | None:
    """The buyer's public name, or None.

    The business profile is the only place a buyer has a public identity. When
    there is no profile yet the answer is None and stays None: the users table
    holds nothing else to fall back on but a phone number, and a phone number
    is never part of a payload handed to the other side of a deal.
    """
    profile = (
        db.query(BusinessProfile)
        .filter(BusinessProfile.user_id == business_user_id)
        .first()
    )
    return profile.company_name if profile else None


def list_my_invitations(db: Session, influencer_user_id: str) -> list[dict]:
    """The creator's invitations, each carrying the whole brief.

    This list backs the invitation card, which is where a creator decides what
    to charge. Pricing a brief means seeing the brief: the deliverables as
    stored (platform, type, quantity), the budget, the deadline, the title —
    and who is asking, because the same deliverables are worth different money
    to different buyers.
    """
    invitations = (
        db.query(models.CampaignInvitation)
        .filter(models.CampaignInvitation.influencer_user_id == influencer_user_id)
        .order_by(models.CampaignInvitation.created_at.desc())
        .all()
    )
    result = []
    # One buyer usually sends several invitations, so their name is looked up
    # once rather than once per row.
    company_names: dict[str, str | None] = {}
    for inv in invitations:
        campaign = db.query(models.Campaign).filter(models.Campaign.id == inv.campaign_id).first()
        if campaign is None:
            continue
        item = _invitation_out(inv)
        item["campaign"] = _to_out(campaign)
        if campaign.business_user_id not in company_names:
            company_names[campaign.business_user_id] = _company_name(db, campaign.business_user_id)
        item["business_company_name"] = company_names[campaign.business_user_id]
        result.append(item)
    return result

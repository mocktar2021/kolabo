"""Epic D (KOL-11): Campaigns and Collaboration."""
from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.admin.router import get_current_admin
from app.modules.auth.deps import get_current_user_id
from app.modules.campaigns import orders, schemas, service

router = APIRouter()


@router.get("/mine", response_model=list[schemas.CampaignOut])
def my_campaigns(
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """List the campaigns owned by the current business."""
    return service.list_my_campaigns(db, business_user_id)


@router.get("/invitations/mine", response_model=list[schemas.InvitationWithCampaign])
def my_invitations(
    db: Session = Depends(get_db),
    influencer_user_id: str = Depends(get_current_user_id),
):
    """List the campaign invitations for the current influencer."""
    return service.list_my_invitations(db, influencer_user_id)


@router.get("/{campaign_id}", response_model=schemas.CampaignDetailOut)
def campaign_detail(
    campaign_id: str,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Full campaign view with its invitations and proposals (owner only)."""
    return service.get_campaign_detail(db, campaign_id, business_user_id)


@router.post("/", response_model=schemas.CampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(
    payload: schemas.CampaignCreate,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Create a campaign as draft, or published if publish is true. KOL-21."""
    return service.create_campaign(db, business_user_id, payload)


@router.post("/orders", response_model=schemas.OrderOut, status_code=status.HTTP_201_CREATED)
def create_direct_order(
    payload: schemas.OrderIn,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Order a creator's package directly, at the price they published.

    Lives under /campaigns because an order IS a campaign — a hidden one, with
    a single creator invited and the buyer's offer already on the table. No
    money moves here: the creator has 48 hours to accept, and escrow is funded
    only after they do.
    """
    return service.create_direct_order(db, business_user_id, payload.package_id, payload.note)


@router.post("/orders/expire")
def expire_stale_orders(
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """Close direct orders whose 48 hour window has passed unanswered.

    Admin-triggered and on demand, mirroring /payments/escrow/auto-release:
    there is no scheduler yet, and both of these become jobs on it the day
    there is one.
    """
    return {"expired": orders.expire_stale_orders(db)}


@router.post("/orders/{proposal_id}/accept", status_code=status.HTTP_201_CREATED)
def accept_direct_order(
    proposal_id: str,
    db: Session = Depends(get_db),
    influencer_user_id: str = Depends(get_current_user_id),
):
    """The invited creator accepts an order, which generates the contract.

    Returns the contract, not the proposal: signing it is the next thing both
    parties have to do, and the response is what the client routes to.
    """
    return orders.accept_direct_order(db, influencer_user_id, proposal_id)


@router.post("/orders/{proposal_id}/decline", response_model=schemas.ProposalOut)
def decline_direct_order(
    proposal_id: str,
    db: Session = Depends(get_db),
    influencer_user_id: str = Depends(get_current_user_id),
):
    """The invited creator turns an order down, closing it. Nobody is charged."""
    return orders.decline_direct_order(db, influencer_user_id, proposal_id)


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
    """Submit a proposal, with an optional note. Resubmitting creates a new version. KOL-23."""
    return service.submit_proposal(db, campaign_id, influencer_user_id, payload)


@router.post(
    "/{campaign_id}/proposals/{proposal_id}/reply",
    response_model=schemas.ProposalOut,
    status_code=status.HTTP_201_CREATED,
)
def reply_to_proposal(
    campaign_id: str,
    proposal_id: str,
    payload: schemas.ProposalReplyIn,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Answer a proposal as the campaign owner: a note, and optionally a
    counter on rate or timeline. The answer is the next version in the same
    chain, which is how the negotiation stays on the platform. KOL-23."""
    return service.reply_to_proposal(db, campaign_id, proposal_id, business_user_id, payload)

"""Epic D (KOL-11): Campaigns and Collaboration."""
from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.admin.router import get_current_admin
from app.modules.auth.deps import get_current_user_id
from app.modules.campaigns import cart, editing, orders, schemas, service

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


@router.patch("/{campaign_id}", response_model=schemas.CampaignOut)
def update_campaign(
    campaign_id: str,
    payload: schemas.CampaignPatch,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Correct a campaign (owner only). Partial: only the fields you send.

    A draft is fully editable. Once published, title and description stay
    editable, but budget, currency, deliverables and deadline lock as soon as
    a proposal exists — creators priced against those terms. A direct order is
    not editable here at all; counter it instead.
    """
    return editing.update_campaign(db, campaign_id, business_user_id, payload)


@router.delete("/{campaign_id}", response_model=schemas.CampaignDeletedOut)
def delete_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Erase a draft nobody has seen (owner only).

    Only a draft with no proposals, no invitations and no contract can go.
    Anything else is a 409 telling you to cancel it: proposals, contracts and
    the audit trail are the other party's record too.
    """
    return editing.delete_campaign(db, campaign_id, business_user_id)


@router.post("/", response_model=schemas.CampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(
    payload: schemas.CampaignCreate,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Create a campaign as draft, or published if publish is true. KOL-21."""
    return service.create_campaign(db, business_user_id, payload)


@router.post("/orders", response_model=schemas.OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: schemas.OrderIn,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Order from a creator: their package as listed, or terms you negotiated.

    Send package_id for the published price, or the full custom offer
    (creator_user_id, platform, deliverable_type, quantity, rate_amount,
    currency, timeline_days) to propose your own terms. Exactly one of the
    two; both or neither is a 400 that names the problem.

    One endpoint because there is one kind of order. Lives under /campaigns
    because an order IS a campaign — a hidden one, with a single creator
    invited and the buyer's offer already on the table. No money moves here:
    the creator has 48 hours to accept, and escrow is funded only after they
    do. Negotiating the terms changes none of that.
    """
    return service.create_order(db, business_user_id, payload)


@router.post(
    "/orders/checkout",
    response_model=schemas.CartCheckoutOut,
    status_code=status.HTTP_201_CREATED,
)
def checkout_cart(
    payload: schemas.CartCheckoutIn,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Check out a basket of 1-20 items as one direct order per creator.

    Each item is a package_id or a full custom offer, exactly as /orders takes
    them. Items are grouped by creator, so buying three packages from one
    person is ONE order with three deliverables and their summed budget, while
    two people are two independent orders — each answered, contracted and paid
    on its own.

    There is no cart on the server: send the whole basket. Every item is
    validated first and the whole checkout is one transaction, so a bad item
    creates nothing and answers 400 naming its position.
    """
    return cart.checkout(db, business_user_id, payload)


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


@router.post("/{campaign_id}/cancel", response_model=schemas.CampaignOut)
def cancel_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Call a campaign off (owner only), keeping everything attached to it.

    The invited creators are notified. Refused with a 409 once a contract
    exists: unwinding a signed agreement is the dispute and refund path, not
    something the buyer does alone.
    """
    return editing.cancel_campaign(db, campaign_id, business_user_id)


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
    """Submit a proposal, with an optional note. Resubmitting creates a new version.

    This is also how a creator COUNTERS a direct order: there is no separate
    counter endpoint on the creator side, the next version in the chain is the
    counter. It stays on the order's clock. KOL-23.
    """
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

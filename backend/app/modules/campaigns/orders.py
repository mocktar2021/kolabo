"""The second half of a direct order: the creator's answer, and the clock.

Placing an order lives in service.create_direct_order, next to the campaign it
creates. What happens to it afterwards — accept, decline, and the sweep that
retires orders nobody answered — lives here.

It is a separate module for a concrete reason rather than for tidiness:
accepting an order has to call the contracts module, and contracts already
imports campaigns.service (it re-reads the live version of a chain before
writing a contract from it). Putting that call in service.py would close the
import circle and force a function-local import to break it. From here the
dependency runs one way: router -> orders -> contracts -> campaigns.service.

Nothing in this file moves money, and that is the whole design. Escrow is
funded only AFTER acceptance, which is why a decline or a lapse needs no
refund path at all: there is nothing in the system to give back. The 48 hour
window is safe to enforce for exactly the same reason.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.campaigns import models
from app.modules.campaigns import service as campaigns_service
from app.modules.contracts import service as contracts_service
from app.modules.notifications.service import notify


def _load_order(db: Session, proposal_id: str, influencer_user_id: str):
    """The order behind a proposal id, checked to be one and to be theirs.

    Authorisation is by the proposal's creator rather than by the invitation
    row: a direct order has exactly one creator on it from the moment it is
    placed, and the proposal is the thing being answered.
    """
    proposal = db.query(models.Proposal).filter(models.Proposal.id == proposal_id).first()
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    campaign = db.query(models.Campaign).filter(models.Campaign.id == proposal.campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if not campaign.is_direct:
        # A brief's proposals are accepted by the BUSINESS, through the
        # contracts endpoint. Routing one through here would let a creator
        # sign their own offer.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This proposal is not a direct order",
        )
    if proposal.influencer_user_id != influencer_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This order is not yours")
    return proposal, campaign


def _set_invitation(db: Session, campaign_id: str, influencer_user_id: str, new_status: str) -> None:
    """Keep the invitation row honest.

    The creator's invitations list is where they see the order, so leaving it
    at 'invited' after they answered would show them a decision they already
    made as one still waiting for them.
    """
    invitation = (
        db.query(models.CampaignInvitation)
        .filter(
            models.CampaignInvitation.campaign_id == campaign_id,
            models.CampaignInvitation.influencer_user_id == influencer_user_id,
        )
        .first()
    )
    if invitation is not None:
        invitation.status = new_status


def accept_direct_order(db: Session, influencer_user_id: str, proposal_id: str) -> dict:
    """The creator takes the job, and only now does a contract exist.

    The contract is written by the EXISTING contracts path, not by a copy of
    it living here. Contract generation already snapshots the agreed terms,
    writes the audit row, marks the proposal accepted and notifies the other
    side; a second implementation would be a second set of those rules to keep
    in step, and the one that drifted would be the one nobody was reading.

    That path takes the buyer as the actor, and the buyer is the right actor:
    on a direct order the business authored the offer, so its consent to these
    exact terms is already on record as the proposal itself. What was missing
    was the creator's, which is this call.

    Escrow is still unfunded when this returns. Funding is the buyer's next
    step and it needs both signatures first — unchanged, and untouched here.
    """
    proposal, campaign = _load_order(db, proposal_id, influencer_user_id)
    if proposal.status != models.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This order is no longer open",
        )
    # Checked before anything is written. An expired order is not a slow yes:
    # the buyer has been told it lapsed and may well have ordered elsewhere.
    if proposal.expires_at is not None and proposal.expires_at <= models.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This order has expired.")

    _set_invitation(db, campaign.id, influencer_user_id, models.ACCEPTED)
    contract = contracts_service.generate_from_proposal(db, campaign.business_user_id, proposal.id)
    # Contract generation notifies the creator that a contract is ready, which
    # is the right message for a brief — there the business just accepted. On
    # an order it is the buyer who has been waiting on an answer, so they get
    # one too.
    notify(
        db,
        campaign.business_user_id,
        "direct_order",
        f"Your order {campaign.title} was accepted. The contract is ready to sign.",
    )
    db.commit()
    return contract


def decline_direct_order(db: Session, influencer_user_id: str, proposal_id: str) -> dict:
    """The creator passes, and the order closes.

    Nothing needs refunding. Escrow is funded only after acceptance, so at
    this point the buyer has not paid anything — no held funds, no provider
    call to reverse, no reconciliation. That is precisely why the flow was
    shaped as accept-then-fund rather than fund-then-accept.

    The campaign is cancelled with the proposal. A direct order is a campaign
    with one creator in it, so their no is the end of it; leaving it published
    would leave an order in the buyer's list looking live.
    """
    proposal, campaign = _load_order(db, proposal_id, influencer_user_id)
    if proposal.status != models.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This order is no longer open",
        )

    proposal.status = models.PROPOSAL_DECLINED
    campaign.status = models.CANCELLED
    _set_invitation(db, campaign.id, influencer_user_id, models.DECLINED)
    notify(
        db,
        campaign.business_user_id,
        "direct_order",
        f"Your order {campaign.title} was declined. You were not charged.",
    )
    db.commit()
    db.refresh(proposal)
    identity = campaigns_service._proposer_identity(db, [influencer_user_id]).get(influencer_user_id)
    return campaigns_service._proposal_out(proposal, identity)


def expire_stale_orders(db: Session, now=None) -> int:
    """Retire direct orders nobody answered in time.

    Runs on demand, triggered by an admin, for the same reason
    run_due_auto_releases does: there is no scheduler in this system yet, and
    inventing one for this would be a bigger decision than the feature. When a
    scheduler arrives both of these become jobs on it, unchanged.

    Only rows with an expires_at are ever touched, which is what keeps the
    brief flow out of this entirely: a brief's proposals carry NULL there and
    are meant to stay open until somebody acts on them. The NOT NULL test is
    redundant against SQL's comparison rules and is written out anyway,
    because it is the rule and not an optimisation.

    Both parties are notified. The creator is told what they lost by not
    answering, and the buyer is told to stop waiting — which is the whole
    reason the window exists.
    """
    now = now or models.utcnow()
    stale = (
        db.query(models.Proposal)
        .filter(
            models.Proposal.status == models.SUBMITTED,
            models.Proposal.expires_at.isnot(None),
            models.Proposal.expires_at <= now,
        )
        .all()
    )
    for proposal in stale:
        campaign = (
            db.query(models.Campaign).filter(models.Campaign.id == proposal.campaign_id).first()
        )
        proposal.status = models.PROPOSAL_DECLINED
        if campaign is None:
            continue
        campaign.status = models.CANCELLED
        _set_invitation(db, campaign.id, proposal.influencer_user_id, models.DECLINED)
        notify(
            db,
            proposal.influencer_user_id,
            "direct_order",
            f"The order {campaign.title} expired because it was not answered in time.",
        )
        notify(
            db,
            campaign.business_user_id,
            "direct_order",
            f"Your order {campaign.title} expired unanswered. You were not charged.",
        )
    db.commit()
    return len(stale)

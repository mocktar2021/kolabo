"""Taking back an offer nobody has answered yet.

Until now nothing on a campaign could be undone. A brand that invited the
wrong creator left the invitation sitting there; a creator who bid before
reading the brief properly, or who got booked elsewhere that week, could only
leave a live number on the table and hope nobody accepted it. Both are small
embarrassments that turn into real ones: an accepted proposal is a contract,
and a contract the creator cannot honour is a dispute.

THE LINE IS THE SAME IN BOTH DIRECTIONS — you may take back what you offered
until the other side has spent effort on it, and not afterwards.

  * An invitation may be withdrawn while it is still just an invitation. Once
    the creator has PROPOSED, they have priced the brief — read it, worked out
    what the shoot costs, decided what their audience is worth — and what is
    on the table is an offer that deserves an answer. Retracting the
    invitation from under it would let a buyer collect prices and then make
    the request disappear, leaving a bid addressed to nothing.

  * A proposal may be withdrawn while it is the live, unanswered version and
    no contract exists. After a contract there is a signed or half-signed
    agreement, which is contracts.cancellation's business, not this one's.

WITHDRAWN IS NOT DECLINED. See models.WITHDRAWN: declined and rejected both
record that somebody said no, and putting a refusal on a record that never
made one is the kind of small dishonesty that makes a reputation system
worthless.

NO AUDIT ROW, because this module has no audit table to write to. Contracts
keep ContractEvent and this commit uses it; campaigns have never had an
equivalent, and inventing one here for two operations would be a schema
decision made sideways. What both operations DO write is a notification to the
other party, which is the campaigns module's existing way of saying something
happened — the same thing cancel_campaign does.

A separate module from service.py for the reason editing.py is: service.py is
already long and is about creating campaigns and running the negotiation on
them. The dependency runs one way — router -> withdrawals -> service — and
contracts are read through contracts.models (models only, never
contracts.service, which imports campaigns.service and would close the circle).
"""
from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.identity import creator_identities
from app.modules.campaigns import models, service
from app.modules.contracts import models as contracts
from app.modules.notifications.service import notify

# Said in full because it has to teach as well as refuse: a buyer who reads
# only "400" learns nothing about what to do with the bid now sitting there.
PRICED_DETAIL = (
    "This creator has already sent a proposal, so there is an offer on the table "
    "to answer rather than an invitation to retract. Reply to it or reject it."
)

# A direct order already has a way for the creator to close it, and it does
# more than this endpoint could: it cancels the hidden campaign with the
# proposal and moves the invitation, so the buyer's list does not keep showing
# a live order. Routing here would leave an order half-closed.
DIRECT_ORDER_DETAIL = (
    "This is a direct order, not a bid on a brief. Decline it instead: "
    "POST /campaigns/orders/{proposal_id}/decline."
)


def _proposal_exists(db: Session, campaign_id: str, influencer_user_id: str) -> bool:
    """Has this creator priced this brief at all, in any version?

    Any version, including superseded ones, and including a status that has
    since moved on. The question is whether they did the work, and a chain
    that reached version four is four rounds of it. The invitation's own
    status cannot answer this: on a brief it stays 'invited' no matter how
    much negotiating happens underneath it.
    """
    return (
        db.query(models.Proposal)
        .filter(
            models.Proposal.campaign_id == campaign_id,
            models.Proposal.influencer_user_id == influencer_user_id,
        )
        .first()
        is not None
    )


def withdraw_invitation(
    db: Session, campaign_id: str, invitation_id: str, business_user_id: str
) -> dict:
    """The buyer takes an invitation back, while it is still only an invitation.

    The creator is told. A creator who was invited on Monday and finds the row
    quietly gone on Friday has no way to know whether they were dropped or
    whether something broke, and the ones who ask are the polite minority.
    """
    campaign = service._require_campaign_owner(db, campaign_id, business_user_id)

    invitation = (
        db.query(models.CampaignInvitation)
        .filter(
            models.CampaignInvitation.id == invitation_id,
            models.CampaignInvitation.campaign_id == campaign_id,
        )
        .first()
    )
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    if invitation.status != models.INVITED:
        # Already answered, already withdrawn, or already accepted. Refused
        # rather than treated as a no-op, so a double click does not send the
        # creator a second "this is off" for something that was already off.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation is no longer open and cannot be withdrawn.",
        )

    if _proposal_exists(db, campaign_id, invitation.influencer_user_id):
        # The creator has spent an evening pricing this. That work is now an
        # offer, and an offer gets an answer. This also catches every direct
        # order for free — an order always carries the buyer's own proposal —
        # which is correct: an order is closed by the creator's decline, not
        # by the buyer deleting the invitation out from under it.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=PRICED_DETAIL)

    invitation.status = models.WITHDRAWN
    notify(
        db,
        invitation.influencer_user_id,
        "campaign_invitation",
        f"The invitation to {campaign.title} was withdrawn by the business.",
        link="/invitations",
        params={"key": "invitation_withdrawn", "campaign": campaign.title},
    )
    db.commit()
    db.refresh(invitation)
    identity = creator_identities(db, [invitation.influencer_user_id]).get(
        invitation.influencer_user_id
    )
    return service._invitation_out(invitation, identity)


def withdraw_proposal(db: Session, proposal_id: str, influencer_user_id: str) -> dict:
    """The creator pulls their own live offer off the table.

    Only their own (403 otherwise), only while it is the live unanswered
    version, and only while nothing has been contracted from it.

    A DIRECT ORDER IS REFUSED HERE and sent to the decline endpoint instead.
    It would have been easy to quietly forward the call, and that is exactly
    the mistake: decline_direct_order does three things this endpoint does not
    — it cancels the hidden campaign, moves the invitation to declined and
    tells the buyer they were not charged. A withdraw that skipped those would
    leave the order looking live in the buyer's list with nothing behind it,
    which is a worse state than either endpoint produces on its own. Refusing
    with the path to use keeps one way to close an order.

    The superseded version underneath is NOT revived. Every earlier version
    was withdrawn by its own author when they wrote the next one, and putting
    terms back on the table that nobody has re-offered would be the platform
    making an offer on somebody's behalf.
    """
    proposal = (
        db.query(models.Proposal).filter(models.Proposal.id == proposal_id).first()
    )
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    if proposal.influencer_user_id != influencer_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This proposal is not yours"
        )

    campaign = (
        db.query(models.Campaign).filter(models.Campaign.id == proposal.campaign_id).first()
    )
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.is_direct:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=DIRECT_ORDER_DETAIL)

    if proposal.status != models.SUBMITTED:
        # Superseded, accepted, rejected: in every one of those the version
        # named here is no longer the offer on the table, so there is nothing
        # left on it to take back.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This proposal is not the live offer and cannot be withdrawn.",
        )

    contract = (
        db.query(contracts.Contract)
        .filter(
            contracts.Contract.campaign_id == proposal.campaign_id,
            or_(
                contracts.Contract.proposal_id == proposal.id,
                contracts.Contract.influencer_user_id == influencer_user_id,
            ),
        )
        .first()
    )
    if contract is not None:
        # A contract already exists between these two on this campaign, so the
        # terms have left the negotiation and become an agreement. Unwinding
        # that is contracts.cancellation's job, and it has the rules — not
        # least whether escrow has been funded against it.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A contract already exists for this proposal. Cancel the contract "
                "instead: POST /contracts/{contract_id}/cancel."
            ),
        )

    proposal.status = models.WITHDRAWN
    notify(
        db,
        campaign.business_user_id,
        "proposal_submitted",
        f"A creator withdrew their proposal for {campaign.title}.",
        # The brief, where the proposal list is — not /campaigns, which would
        # make the brand find the right one again.
        link=f"/campaigns/{campaign.id}",
        params={"key": "proposal_withdrawn", "campaign": campaign.title},
    )
    db.commit()
    db.refresh(proposal)
    identity = creator_identities(db, [influencer_user_id]).get(influencer_user_id)
    return service._proposal_out(proposal, identity)

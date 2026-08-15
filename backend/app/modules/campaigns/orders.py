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
from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.identity import creator_identities
from app.modules.campaigns import models
from app.modules.campaigns import service as campaigns_service
# MODELS as well as the service now. The sweep below has to ask whether a
# campaign already carries a contract, and that is a one-column read on a
# table this module is already downstream of — no new direction in the
# dependency chain the docstring above describes.
from app.modules.contracts import models as contracts_models
from app.modules.contracts import service as contracts_service
from app.modules.notifications.service import notify


def _load_order(db: Session, proposal_id: str, influencer_user_id: str):
    """The order behind a proposal id, checked to be one and to be theirs.

    TWO QUESTIONS, AND THE INVITATION IS THE ONE THAT AUTHORISES. A proposal's
    creator only ever answers "is this row on the caller's own chain", which is
    not the same question as "is the caller a party to this order": a chain
    belongs to whoever opened it, and anybody could open one. A direct order is
    a private transaction between two named parties, and the party it was
    addressed to is the creator service._place_order wrote the single
    invitation for. That row is the only thing on the campaign naming the
    creator the buyer chose, so it is what the authorisation asks about.

    Unasked, this let a stranger through on their own row. latest_in_chain is
    per creator, so a chain opened by somebody nobody invited started at
    version 1 without superseding the buyer's offer — two live v1 rows on one
    campaign — and decline_direct_order then passed every check and cancelled a
    live order between two other people, while _set_invitation silently did
    nothing because there was no row of theirs to move. The creator the order
    was actually addressed to lost it, and neither party was told why.

    submit_proposal now refuses to open that chain at all (service, PR #124),
    which shuts the way in. That is not what makes this redundant: an entry
    point is not an authorisation, this is the layer that should have said no
    in the first place, and the chains written before that guard landed are
    still in the database.

    BOTH HALVES ARE KEPT, because they refuse different callers. The invitation
    says the caller is a party to this order at all; the proposal's creator says
    this particular row is theirs to answer, which is what stops the BUYER
    answering on the creator's chain — the case
    test_only_the_invited_creator_can_accept has always pinned, and the buyer
    holds no invitation of its own to be caught by the other half.
    """
    proposal = db.query(models.Proposal).filter(models.Proposal.id == proposal_id).first()
    if proposal is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="order_not_found",
            detail="Order not found",
        )
    campaign = db.query(models.Campaign).filter(models.Campaign.id == proposal.campaign_id).first()
    if campaign is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="order_not_found",
            detail="Order not found",
        )
    if not campaign.is_direct:
        # A brief's proposals are accepted by the BUSINESS, through the
        # contracts endpoint. Routing one through here would let a creator
        # sign their own offer.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="order_not_direct",
            detail="This proposal is not a direct order",
        )
    # service._holds_invitation and not a second copy of the query: it is the
    # same question, and the import already runs this way — orders has imported
    # campaigns.service since it was written (see _proposal_out below), while
    # service imports nothing from here. The circle this module exists to avoid
    # is the contracts one, which this does not touch.
    #
    # ONE CODE FOR BOTH HALVES. order_not_yours already names this rule, and a
    # code names the rule rather than the module or the branch it fired in —
    # the convention profiles.service states where it reuses auth_user_not_found.
    # Splitting it would tell a caller WHICH half of the authorisation they
    # failed, which is of use to nobody except somebody probing the endpoint.
    if proposal.influencer_user_id != influencer_user_id or not campaigns_service._holds_invitation(
        db, campaign.id, influencer_user_id
    ):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="order_not_yours",
            detail="This order is not yours",
        )
    return proposal, campaign


def _require_business_offer(proposal) -> None:
    """Only the buyer's offer can be accepted here.

    Acceptance on a direct order is the creator supplying the consent the buyer
    already gave by making the offer. Once the creator counters, the live
    version is the creator's own — accepting it would write a priced contract
    carrying one signature, at a number the business has never agreed to. When
    the creator holds the live version it is the buyer's turn, and the buyer
    accepts through the contracts path exactly as they do on a brief.

    400 rather than 403: the caller does own this order. The offer on the table
    is simply not theirs to accept.
    """
    if proposal.author_role != models.AUTHOR_BUSINESS:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="order_own_counter",
            detail="This is your own counter-offer. The brand has to accept it.",
        )


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


def _campaign_has_contract(db: Session, campaign_id: str) -> bool:
    """Whether a contract has been written off this campaign. PENDING COUNTS.

    The same notion campaigns.editing._contract carries, and it is stated the
    same way for the same reason: a contract that exists was generated from
    agreed terms and is sitting in front of two people to sign, so the
    campaign behind it is no longer anybody's to close on their own.
    editing.cancel_campaign refuses the BUYER on exactly this test
    (campaign_has_contract), and a sweep has less standing than the buyer, not
    more.

    Restated here rather than imported: campaigns.editing is a router-facing
    module that pulls in campaigns.service, campaigns.schemas and
    campaigns.completion, and reaching into it for one private helper would
    widen this module's dependency chain to fetch a query that is four lines
    long. contracts.models imports nothing but Base.
    """
    return (
        db.query(contracts_models.Contract)
        .filter(contracts_models.Contract.campaign_id == campaign_id)
        .first()
        is not None
    )


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
    was the creator's, which is this call. That reasoning only holds while the
    live offer is the buyer's, which is what _require_business_offer enforces.

    Escrow is still unfunded when this returns. Funding is the buyer's next
    step and it needs both signatures first — unchanged, and untouched here.
    """
    proposal, campaign = _load_order(db, proposal_id, influencer_user_id)
    _require_business_offer(proposal)
    if proposal.status != models.SUBMITTED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="order_not_open",
            detail="This order is no longer open",
        )
    # Checked before anything is written. An expired order is not a slow yes:
    # the buyer has been told it lapsed and may well have ordered elsewhere.
    if proposal.expires_at is not None and proposal.expires_at <= models.utcnow():
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="order_expired",
            detail="This order has expired.",
        )

    _set_invitation(db, campaign.id, influencer_user_id, models.ACCEPTED)
    # allow_business_offer, because this is the one path where a
    # business-authored offer is legitimately being accepted: the actor passed
    # below is the buyer, but the person accepting is the CREATOR, and
    # _require_business_offer above has already established that the live
    # version is the buyer's. Contract generation otherwise refuses that shape
    # with contract_own_offer, which is what stops the buyer accepting its own
    # order through the contracts endpoint.
    contract = contracts_service.generate_from_proposal(
        db, campaign.business_user_id, proposal.id, allow_business_offer=True
    )
    # Contract generation notifies the creator that a contract is ready, which
    # is the right message for a brief — there the business just accepted. On
    # an order it is the buyer who has been waiting on an answer, so they get
    # one too.
    notify(
        db,
        campaign.business_user_id,
        "direct_order",
        f"Your order {campaign.title} was accepted. The contract is ready to sign.",
        # Straight to the contract, which is the thing the buyer now has to do
        # something about. routeForType would only manage /campaigns, and the
        # contract id is right here from the call above.
        link=f"/contracts/{contract['id']}",
        params={"key": "order_accepted", "campaign": campaign.title},
    )
    db.commit()
    return contract


def decline_direct_order(db: Session, influencer_user_id: str, proposal_id: str) -> dict:
    """The creator passes, and the order closes.

    Nothing needs refunding. Escrow is funded only after acceptance, so at
    this point the buyer has not paid anything — no held funds, no provider
    call to reverse, no reconciliation. That is precisely why the flow was
    shaped as accept-then-fund rather than fund-then-accept.

    Declining their own counter is allowed on purpose: withdrawing an offer you
    made is a different act from signing one, and a creator who changes their
    mind should be able to close the order rather than leave the buyer waiting
    on a number nobody intends to honour.

    The campaign is cancelled with the proposal. A direct order is a campaign
    with one creator in it, so their no is the end of it; leaving it published
    would leave an order in the buyer's list looking live.
    """
    proposal, campaign = _load_order(db, proposal_id, influencer_user_id)
    if proposal.status != models.SUBMITTED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="order_not_open",
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
        link=f"/campaigns/{campaign.id}",
        params={"key": "order_declined", "campaign": campaign.title},
    )
    db.commit()
    db.refresh(proposal)
    identity = creator_identities(db, [influencer_user_id]).get(influencer_user_id)
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

    TWO THINGS IT WILL NOT EXPIRE, and both come from the same mistake: the
    query finds a lapsed PROPOSAL, and a proposal is not the same thing as the
    order it hangs off.

      * A CHAIN THAT IS NOT THIS ORDER. This is _load_order's rule, one layer
        down. latest_in_chain is per creator, so a chain opened by somebody
        nobody invited started at version 1 without superseding the buyer's
        offer, and cancelling the campaign off that row cancels the real order
        — placed by a buyer, addressed to a different creator, and quite
        possibly already answered. submit_proposal shut the way in (service,
        PR #124) and _load_order stopped honouring those rows (PR #125), but
        this sweep needs no caller at all: it reads the table directly, so it
        went on acting on rows written before either guard landed.

      * A CAMPAIGN THAT HAS MOVED ON. Acceptance does NOT change the campaign's
        status — contracts.service.generate_from_proposal marks the accepted
        version and leaves the campaign PUBLISHED — so the status cannot tell a
        live order from one that is already contracted, and it is not the test
        to use here. A stranger's row meanwhile stays `submitted` forever,
        because accepting supersedes only the accepted chain's own earlier
        versions. Put together, that is a sweep cancelling a campaign carrying
        a signed contract and possibly a funded escrow.

    BOTH ARE SKIPS, NOT REFUSALS, and that is the difference between this and
    _load_order. There the caller asked for one order and gets told no; here
    there is no caller and no single order — a batch passes over the rows that
    are not its business and carries on, the same thing payments.service does
    when it narrows run_due_auto_releases to escrows awaiting review and
    _undelivered_escrows to contracts nobody submitted against. Those two
    express it in the query because their tests are plain columns; these two
    need a lookup per row, so they are written as a `continue` — same rule,
    same effect, nothing raised.

    A SKIPPED ROW IS NOT AN EXPIRED ROW, which is why the count below is kept
    by hand rather than taken from len(stale): the endpoint answers
    {"expired": n} and n has to mean orders that actually ended.

    NOT LOGGED, deliberately. Nothing in the campaigns package holds a logger
    and this change is not the place to introduce the first one; the skip is
    instead visible in the count, which no longer claims a row it passed over.
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
    expired = 0
    for proposal in stale:
        campaign = (
            db.query(models.Campaign).filter(models.Campaign.id == proposal.campaign_id).first()
        )
        if campaign is None:
            # Unreachable behind the foreign key, and left doing what it did:
            # the dangling row is closed. It is not counted, because nothing
            # was cancelled and nobody was told anything — there was no order
            # here to expire.
            proposal.status = models.PROPOSAL_DECLINED
            continue
        if not campaigns_service._holds_invitation(
            db, campaign.id, proposal.influencer_user_id
        ):
            # Somebody else's chain on this campaign. Not this order, so not
            # this order's clock, and cancelling on it would close a live
            # order out from under two people who never heard of this row.
            continue
        if _campaign_has_contract(db, campaign.id):
            # The order was answered. Whatever is still sitting `submitted`
            # here, the campaign is spoken for and a lapsed window is no
            # longer a reason to end it.
            continue
        proposal.status = models.PROPOSAL_DECLINED
        campaign.status = models.CANCELLED
        _set_invitation(db, campaign.id, proposal.influencer_user_id, models.DECLINED)
        notify(
            db,
            proposal.influencer_user_id,
            "direct_order",
            f"The order {campaign.title} expired because it was not answered in time.",
            # The creator's own list, where the lapsed order now sits. A
            # brand's /campaigns/{id} is not theirs to open.
            link="/invitations",
            params={"key": "order_expired_creator", "campaign": campaign.title},
        )
        notify(
            db,
            campaign.business_user_id,
            "direct_order",
            f"Your order {campaign.title} expired unanswered. You were not charged.",
            link=f"/campaigns/{campaign.id}",
            params={"key": "order_expired_brand", "campaign": campaign.title},
        )
        expired += 1
    db.commit()
    return expired

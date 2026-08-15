"""Epic D (KOL-11): Campaigns and Collaboration."""
from datetime import date

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.admin.router import get_current_admin
from app.modules.auth.deps import get_current_user_id
from app.modules.campaigns import board, cart, editing, orders, schemas, service, withdrawals

router = APIRouter()


@router.get("/mine", response_model=list[schemas.CampaignOut])
def my_campaigns(
    # `status` shadows the fastapi module of the same name imported above, but
    # only inside this function, and nothing in here needs it. The query
    # parameter is named for the field it filters, because that is the name
    # the client and the column already use.
    status: str | None = None,
    created_after: date | None = None,
    created_before: date | None = None,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """List the campaigns owned by the current business, newest first.

    Optionally narrowed by status (draft, published, completed, cancelled) and
    by the day the campaign was created. A buyer three months into using this
    has a list it has to scroll to find last week's brief in, and "which of
    these are still live" is the question it opens the page asking.

    An unrecognised status is a 400 naming the set, not an empty list. This is
    the buyer's own work: showing nothing would read as "you have no
    campaigns", which is the one answer that sends somebody to support.
    """
    return service.list_my_campaigns(
        db,
        business_user_id,
        status=status,
        created_after=created_after,
        created_before=created_before,
    )


@router.get("/invitations/mine", response_model=list[schemas.InvitationWithCampaign])
def my_invitations(
    db: Session = Depends(get_db),
    influencer_user_id: str = Depends(get_current_user_id),
):
    """List the campaign invitations for the current influencer."""
    return service.list_my_invitations(db, influencer_user_id)


# Declared before the /{campaign_id} routes below, with the other literal
# first segments. FastAPI matches in declaration order and "open" would
# otherwise be read as a campaign id.
@router.get("/open", response_model=list[schemas.OpenBriefOut])
def open_briefs(
    limit: int = board.BOARD_LIMIT,
    offset: int = 0,
    min_budget: int | None = None,
    max_budget: int | None = None,
    category: str | None = None,
    country: str | None = None,
    platform: str | None = None,
    deadline_before: date | None = None,
    db: Session = Depends(get_db),
    influencer_user_id: str = Depends(get_current_user_id),
):
    """The open board: published briefs any creator may apply to, best fit first.

    SIGNED-IN CREATORS ONLY. A business or agency gets a 403, not an empty
    list: a brief carries a budget, a deadline and the shape of a brand's
    plans for the quarter, so unlike discovery search — which is public
    because a creator's storefront is meant to be seen — the board stays
    behind a creator login. An empty list would also read as "there are no
    open briefs", which is a different and untrue answer.

    THE FILTERS NARROW, THE SCORE ORDERS, and they are two mechanisms rather
    than one. min_budget, max_budget, category, country, platform and
    deadline_before decide WHICH briefs come back; match_score decides what
    order they come back IN, exactly as it did before they existed. Every one
    of them is optional, so a client that sends none gets the whole board.

    THE SCORE STILL DOES NOT FILTER: with no filters set, every open brief
    appears on every creator's board, including the ones scoring zero. The
    brand's targeting never hides a brief from anybody — only the creator's
    own filters do, and only for as long as they leave them set.

    category and country match the brand's TARGET lists, so they mean "briefs
    aimed at this", which is why an untargeted brief does not answer them.
    platform matches any one of a brief's deliverables. deadline_before is
    inclusive. campaigns.board argues all of it.
    """
    return board.list_open_campaigns(
        db,
        influencer_user_id,
        limit,
        offset,
        min_budget=min_budget,
        max_budget=max_budget,
        category=category,
        country=country,
        platform=platform,
        deadline_before=deadline_before,
    )


@router.post("/proposals/{proposal_id}/withdraw", response_model=schemas.ProposalOut)
def withdraw_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    influencer_user_id: str = Depends(get_current_user_id),
):
    """The creator takes their own live offer back off the table.

    Only yours (403 otherwise), only while it is the live submitted version,
    and only while no contract has been generated from it (400 otherwise).

    Not available on a direct order: an order is closed by declining it, which
    also cancels the order and tells the buyer they were not charged. This
    endpoint answers 400 with that path rather than doing half the job.
    """
    return withdrawals.withdraw_proposal(db, proposal_id, influencer_user_id)


@router.get("/{campaign_id}", response_model=schemas.CampaignDetailOut)
def campaign_detail(
    campaign_id: str,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Full campaign view with its invitations and proposals (owner only).

    Applications from the open board arrive in the proposals list here, with
    no special casing: this view has always selected every proposal on the
    campaign and has never filtered by invitation, so a bid from a creator the
    brand never invited sits beside the ones it did — which is exactly where
    a brand expects to answer it.
    """
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

    is_open and the targeting fields stay editable throughout, including after
    a creator has bid. They are not terms: nobody prices a brief against who
    else the brand hoped to hear from, so widening the board or closing it to
    new applications takes nothing away from the offers already on the table.

    A description carrying a phone number, an email or a messaging handle is
    refused with a 400, the same as at creation — an open brief is read by
    every creator on the board.
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


@router.post("/{campaign_id}/apply", response_model=schemas.ProposalOut, status_code=status.HTTP_201_CREATED)
def apply_to_campaign(
    campaign_id: str,
    payload: schemas.ProposalIn,
    db: Session = Depends(get_db),
    influencer_user_id: str = Depends(get_current_user_id),
):
    """Apply to an open brief without an invitation, with your terms.

    The body is a proposal, because that is what an application IS: the same
    rate, currency, timeline and optional note an invited creator sends, and
    it becomes the same row on the same version chain. The brand answers it
    from its campaign page exactly as it answers any other proposal.

    Allowed only on a published, open, non-direct campaign (400 otherwise) and
    only while the caller has no live proposal on it already (409) — a second
    application would supersede terms the brand may be reading right now.

    The board's filters have no say here. They decided what the creator was
    shown; they never decide what the creator may bid on.
    """
    return board.apply_to_campaign(db, campaign_id, influencer_user_id, payload)


@router.post("/{campaign_id}/invitations", response_model=schemas.InvitationOut, status_code=status.HTTP_201_CREATED)
def invite_influencer(
    campaign_id: str,
    influencer_id: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Invite a verified influencer to a published campaign. KOL-22."""
    return service.invite_influencer(db, campaign_id, business_user_id, influencer_id)


@router.delete(
    "/{campaign_id}/invitations/{invitation_id}", response_model=schemas.InvitationOut
)
def withdraw_invitation(
    campaign_id: str,
    invitation_id: str,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """The owner takes an invitation back while it is still unanswered.

    Allowed only while the invitation is 'invited' AND the creator has not
    proposed. Once they have priced the brief there is an offer on the table
    to answer, not an invitation to retract, and the answer is 400 saying so.
    The creator is notified either way it goes.

    The row is kept with a 'withdrawn' status rather than deleted, and
    withdrawn is not declined: nobody said no here, and a creator's record
    should not carry a refusal they never made.
    """
    return withdrawals.withdraw_invitation(db, campaign_id, invitation_id, business_user_id)


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

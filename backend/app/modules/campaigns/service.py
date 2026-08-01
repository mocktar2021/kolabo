"""Campaigns and collaboration business logic (Epic D).

KOL-21: create a campaign brief. Draft save is allowed with any fields;
publishing requires budget, deliverables, and a deadline. Every deliverable a
brief does name is validated against the shared platform catalog, the same
source of truth packages sell from.
KOL-22: invite a specific influencer. Blocked if the influencer is not verified;
the influencer is notified.
KOL-23: submit a proposal. A proposal is locked once submitted, so an edit is a
new version and the previous one is superseded; the business is notified. Each
version may carry a note explaining its terms, and the business can answer with
a note of its own and an optional counter — which is another version in the
same chain, not a message. Terms that get argued over somewhere else end up
agreed somewhere else, and a deal agreed on WhatsApp is a deal we cannot
contract, escrow, or protect either side of.

Direct orders: a brand can also skip the brief entirely and buy a creator's
package at the published price. That order is created here, as a hidden
single-creator campaign, because the campaigns module owns the campaign — see
create_direct_order for why it is shaped that way.
"""
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.platforms import PLATFORM_DELIVERABLES, is_valid_pair
from app.modules.auth.models import User
from app.modules.campaigns import models, schemas
from app.modules.notifications.service import notify
from app.modules.profiles.models import BusinessProfile, InfluencerProfile, Package

# Nobody briefs a hundred-plus of anything in one campaign; past that the
# number is a typo (an amount pasted into the quantity box), so reject it
# instead of inviting creators to an impossible job.
MAX_DELIVERABLE_QUANTITY = 100

# The role that may not author a brief. Stated as who is excluded rather than
# who is allowed: a new buyer-side role should be able to brief on the day it
# is introduced, without anyone remembering to add it to a whitelist here.
AUTHOR_EXCLUDED_ROLE = "influencer"

# How many versions of a negotiation a campaign page carries. Twenty rounds is
# already far past the point where two people should have picked up the phone,
# and an unbounded chain would let one stubborn thread decide how long the
# whole page takes to load.
MAX_PROPOSAL_VERSIONS = 20

# How long a creator has to accept or decline a direct order.
#
# The window exists because the buyer is waiting on an answer they have
# already priced, and an offer nobody ever answers is worse for the brand than
# a no. Two days is long enough for a creator who is filming or travelling and
# short enough that a brand can plan around it. Letting it lapse costs nobody
# anything: escrow is funded only after acceptance, so there is never money
# sitting in the system waiting on this clock.
ORDER_ACCEPT_WINDOW_HOURS = 48

# The delivery timeline a direct order promises when the package does not say.
#
# A package's duration describes the deliverable ("30 seconds"), not how long
# the creator needs to produce it, and the catalog of duration units is
# seconds/minutes/hours — so in practice every order lands on this default.
# One week is the figure creators quote most often on briefs, and both sides
# can renegotiate it: an order is a proposal like any other.
DEFAULT_ORDER_TIMELINE_DAYS = 7


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
        "is_direct": campaign.is_direct,
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


def create_direct_order(db: Session, business_user_id: str, package_id: str, note: str | None = None) -> dict:
    """A brand buys a creator's package at the published price.

    Shape of the thing, and why. An order is a HIDDEN, single-creator campaign
    carrying exactly one invitation and one proposal — not a table of its own.
    Contracts, escrow, reviews and disputes all already hang off a campaign
    and a proposal, and giving orders their own model would mean a second
    parallel path into the money code: two ways to reach a payout, two places
    to get a refund wrong, every future change to escrow needing to be made
    twice. One payment path is worth the small strangeness of a campaign
    nobody can browse.

    Who is proposing, and why it is the business. The buyer picked a price the
    creator had already published and offered it back, so author_role is
    business — that is literally what happened, and it is what makes the
    creator's accept-or-decline an answer rather than a second offer.

    What does NOT happen here: no money moves. The creator has
    ORDER_ACCEPT_WINDOW_HOURS to accept, and escrow is funded only after they
    do. That ordering is the whole reason the flow is shaped this way — until
    both sides have agreed there is nothing in the system to refund, so a
    decline or a lapse is simply a closed order and never a payments problem.

    All of it in one transaction: a campaign with no invitation, or an
    invitation with no offer attached, is an order the creator can see and
    cannot answer.
    """
    package = db.query(Package).filter(Package.id == package_id).first()
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
    if not package.is_active:
        # A creator deactivates a package when they have stopped selling it —
        # out of season, fully booked, price out of date. Honouring the old
        # price would be selling something nobody is offering.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This package is not available at the moment.",
        )
    # Checked before the role guard so the message is the true one. A creator
    # buying their own package would also fail the role check, but "only
    # businesses can order" is not what went wrong.
    if package.user_id == business_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot order your own package.",
        )
    # Same guard, same rule, same wording as authoring a brief: an order IS a
    # campaign, and the buying side of the market is the side that may create
    # one. Reused rather than re-stated so the two can never drift apart.
    _require_campaign_author(db, business_user_id)

    campaign = models.Campaign(
        business_user_id=business_user_id,
        title=package.title,
        budget_amount=package.price_amount,
        budget_currency=package.currency,
        deliverables=[
            {"platform": package.platform, "type": package.deliverable_type, "quantity": package.quantity}
        ],
        # No deadline. A brief needs one because creators bid against it and
        # have to know what they are bidding on; an order has no bidding, and
        # the proposal's timeline_days is the commitment instead.
        deadline=None,
        # Published on creation, bypassing _publish_ready on purpose: that
        # gate exists so a half-written brief cannot go live in front of
        # creators. An order is complete the moment it is placed — the terms
        # are the package's — and it goes in front of exactly one person.
        status=models.PUBLISHED,
        is_direct=True,
    )
    db.add(campaign)
    # Flushed, not committed: the invitation and the proposal need the
    # campaign id, and all three land or none of them do.
    db.flush()

    invitation = models.CampaignInvitation(
        campaign_id=campaign.id, influencer_user_id=package.user_id, status=models.INVITED
    )
    db.add(invitation)

    timeline_days = DEFAULT_ORDER_TIMELINE_DAYS
    if package.duration_unit == "days" and package.duration_value:
        timeline_days = package.duration_value

    proposal = models.Proposal(
        campaign_id=campaign.id,
        influencer_user_id=package.user_id,
        version=1,
        rate_amount=package.price_amount,
        rate_currency=package.currency,
        timeline_days=timeline_days,
        note=note,
        author_role=models.AUTHOR_BUSINESS,
        status=models.SUBMITTED,
        # Only direct orders carry an expiry. A brief's proposals stay open
        # indefinitely because nobody promised anything by leaving one open;
        # here a buyer is waiting on an answer to a price they already named.
        expires_at=models.utcnow() + timedelta(hours=ORDER_ACCEPT_WINDOW_HOURS),
    )
    db.add(proposal)

    notify(
        db,
        package.user_id,
        "direct_order",
        f"A brand ordered your package {package.title}. You have "
        f"{ORDER_ACCEPT_WINDOW_HOURS} hours to accept or decline.",
    )
    db.commit()
    db.refresh(campaign)
    db.refresh(proposal)
    return {
        "campaign_id": campaign.id,
        "proposal_id": proposal.id,
        "expires_at": proposal.expires_at,
    }


def latest_in_chain(db: Session, campaign_id: str, influencer_user_id: str) -> models.Proposal | None:
    """The current state of one negotiation.

    A chain is every version exchanged between one creator and one campaign,
    whichever side wrote each one. The last version is the live offer: it is
    what a reply answers, what a new version supersedes, and — the part that
    matters most — what an acceptance signs. Everything before it has already
    been withdrawn by somebody.
    """
    return (
        db.query(models.Proposal)
        .filter(
            models.Proposal.campaign_id == campaign_id,
            models.Proposal.influencer_user_id == influencer_user_id,
        )
        .order_by(models.Proposal.version.desc())
        .first()
    )


def submit_proposal(db: Session, campaign_id: str, influencer_user_id: str, payload: schemas.ProposalIn) -> dict:
    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.status != models.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign is not open for proposals")

    latest = latest_in_chain(db, campaign_id, influencer_user_id)
    next_version = 1
    if latest is not None:
        # Numbered off the whole chain, business replies included. Two rows
        # sharing a version number would make "the latest terms" ambiguous,
        # and the latest terms are the ones that get signed.
        next_version = latest.version + 1
        if latest.status == models.SUBMITTED:
            latest.status = models.SUPERSEDED

    proposal = models.Proposal(
        campaign_id=campaign_id,
        influencer_user_id=influencer_user_id,
        version=next_version,
        rate_amount=payload.rate_amount,
        rate_currency=payload.rate_currency.upper(),
        timeline_days=payload.timeline_days,
        note=payload.note,
        author_role=models.AUTHOR_INFLUENCER,
        status=models.SUBMITTED,
    )
    db.add(proposal)
    notify(db, campaign.business_user_id, "proposal_submitted", f"A new proposal was submitted for {campaign.title}")
    db.commit()
    db.refresh(proposal)
    identity = _proposer_identity(db, [influencer_user_id]).get(influencer_user_id)
    return _proposal_out(proposal, identity)


def reply_to_proposal(
    db: Session,
    campaign_id: str,
    proposal_id: str,
    business_user_id: str,
    payload: schemas.ProposalReplyIn,
) -> dict:
    """The business answers an offer, on the platform.

    Until now the only reply available to a business was accept or silence, so
    every "could you do 40k" went to WhatsApp — and a deal agreed there is a
    deal with no contract, no escrow and no recourse for either side. A reply
    is therefore a proposal version like any other, authored by the business:
    same chain, next number, and the offer on the table is still whatever the
    last version says.

    A reply with no counter repeats the previous terms rather than leaving them
    blank. Every row in a chain is then a complete offer, and answering "what
    are we agreed on" never means reading backwards through the thread
    reassembling terms from four different rows.

    The proposal id only has to name the negotiation, not its newest version:
    the business's page may be a round or two behind, and being out of date is
    not a reason to reject a reply.
    """
    campaign = _require_campaign_owner(db, campaign_id, business_user_id)
    proposal = (
        db.query(models.Proposal)
        .filter(models.Proposal.id == proposal_id, models.Proposal.campaign_id == campaign_id)
        .first()
    )
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    latest = latest_in_chain(db, campaign_id, proposal.influencer_user_id)
    if latest.status != models.SUBMITTED:
        # Accepted or rejected: the negotiation is over. Reopening it by reply
        # would let terms drift after a contract was written from them.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This proposal is closed and cannot be answered",
        )

    reply = models.Proposal(
        campaign_id=campaign_id,
        influencer_user_id=latest.influencer_user_id,
        version=latest.version + 1,
        rate_amount=payload.rate_amount if payload.rate_amount is not None else latest.rate_amount,
        # Never counter-able: the chain is priced in the currency the creator
        # quoted in, and a version that silently changed it would be a
        # different deal wearing the same version number.
        rate_currency=latest.rate_currency,
        timeline_days=payload.timeline_days if payload.timeline_days is not None else latest.timeline_days,
        note=payload.note,
        author_role=models.AUTHOR_BUSINESS,
        status=models.SUBMITTED,
        # Carried forward, not restarted. A direct order that is being
        # negotiated is still the same order on the same clock; resetting the
        # window on every counter would let a chain run forever.
        expires_at=latest.expires_at,
    )
    latest.status = models.SUPERSEDED
    db.add(reply)
    notify(
        db,
        latest.influencer_user_id,
        "proposal_reply",
        f"The business replied to your proposal for {campaign.title}",
    )
    db.commit()
    db.refresh(reply)
    identity = _proposer_identity(db, [reply.influencer_user_id]).get(reply.influencer_user_id)
    return _proposal_out(reply, identity)


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

    A chain names the creator on every row, business replies included: the
    thread belongs to that creator, and author_role is what says who wrote
    which version.
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
        "note": p.note,
        "author_role": p.author_role,
        "expires_at": p.expires_at,
        "display_name": identity.get("display_name"),
        "avatar_url": identity.get("avatar_url"),
    }


def list_my_campaigns(db: Session, business_user_id: str) -> list[dict]:
    """The buyer's own campaigns, briefs and direct orders alike.

    Deliberately NOT filtered on is_direct. Hiding direct orders is about
    keeping a private transaction off a public board; this list is scoped to
    the one person who placed them, and an order they cannot find is an order
    they cannot chase.
    """
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
    # Read as a conversation: oldest first, so an offer sits above the answer
    # it produced. The cap takes the most recent MAX_PROPOSAL_VERSIONS rather
    # than the first ones — the last version is the live offer and the only
    # one that can be accepted, so truncating from that end would hide the
    # single row the page exists to act on. Queried newest-first with a limit
    # (the database does the cutting, not us) and then flipped.
    proposals = (
        db.query(models.Proposal)
        .filter(models.Proposal.campaign_id == campaign_id)
        .order_by(models.Proposal.created_at.desc(), models.Proposal.version.desc())
        .limit(MAX_PROPOSAL_VERSIONS)
        .all()
    )
    proposals.reverse()
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

    Direct orders appear here too, and must: the creator is the invited party,
    and this is the surface where they find out somebody bought their package.
    is_direct on the nested campaign is what lets the client render it as an
    order with a clock rather than as a brief to price.
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

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

Which is also why the free text this module writes is guarded: see
_checked_note for a proposal's reasoning, _checked_description for the brief
itself, and app.core.contact_guard for the rule and for the honest limits of
it. The two are the same rule at different blast radii — a note is read by one
counterparty, while an open brief is readable by every signed-in creator on
the board.

Direct orders: a brand can also skip the brief entirely and buy a creator's
package at the published price — or offer terms of its own when no listed
package fits. Both are created here, as hidden single-creator campaigns,
because the campaigns module owns the campaign. They are built by one function
(_place_order) on purpose: downstream there is exactly one accept path, one
contract path and one escrow path, and nothing after creation can tell the two
kinds of order apart.

An order is built in two halves, and the split is what lets a cart exist.
resolve_package_terms and resolve_negotiated_terms answer "what are the terms,
and may this buyer have them" without writing anything; _place_order turns
terms into rows. campaigns.cart calls the resolvers for every item in a basket
before it writes a single row, which is how a checkout can be all-or-nothing
without a second copy of the package and offer checks living inside it.

Editing, deleting and cancelling a campaign live next door in
campaigns.editing, which is where the rules about what a buyer may still
change once other people are looking are written down. The open board — the
brief a creator can find without being invited, and applying to one — lives in
campaigns.board, which calls submit_proposal below rather than writing a
proposal of its own.

Who the people on these rows are is not decided here: identity comes from
app.core.identity, shared with discovery, so an invitation, a proposal and a
favourite all name a creator the same way. The notifications this module
raises spend that same identity, because a notification that does not name the
person it is about is one the reader has to open the app to understand.
"""
from datetime import datetime, time, timedelta

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.contact_guard import check_no_contact_details
from app.core.identity import blank_identity, creator_identities
from app.core.platforms import PLATFORM_DELIVERABLES, is_valid_pair
from app.modules.auth.models import User
from app.modules.campaigns import models, negotiated, schemas
from app.modules.notifications.service import notify
from app.modules.profiles.models import BusinessProfile, Package

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

# The statuses a buyer may filter its own campaign list by — which is every
# status a campaign can hold. Named off models rather than spelled out again,
# so a fourth status becomes filterable the day it exists instead of silently
# becoming a 400 for anybody who asks about it.
MY_CAMPAIGN_STATUSES = (models.DRAFT, models.PUBLISHED, models.CANCELLED)

# What a notification calls somebody who has not written a profile yet.
#
# Both sides of the market can be live before they have a profile: a creator
# can bid on the board the day they sign up, and a brand can order before it
# has filled in a company name. The alternative to a placeholder is putting a
# user id in the sentence, which turns "Ama K. applied to your open brief"
# into a line nobody can read — and these strings go out by email, where the
# reader has no screen to cross-reference it against.
UNNAMED_CREATOR = "A creator"
UNNAMED_BUYER = "A business"

# An absent name picks a DIFFERENT body key rather than interpolating the
# English placeholder above, because a name interpolated into a French
# sentence stays in the language it was written in: "A creator a postulé à
# votre brief" is worse than either language on its own. admin.decide_social
# does the same for a rejection that has no reason.
#
# Written out at each call site as a pair of literal dicts rather than built
# by a helper, and that is deliberate: web/src/lib/notificationBodies.test.ts
# reads THIS FILE to check every key it emits has a French and an English
# body, and a key assembled from an f-string is a key that test cannot see.
# The stored `message` keeps the English placeholder — the stored message is
# English by definition, it is what goes out by email.

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
# seconds/minutes/hours — so in practice every package order lands on this
# default. One week is the figure creators quote most often on briefs, and
# both sides can renegotiate it: an order is a proposal like any other. A
# negotiated order never uses it — there the buyer states the timeline.
DEFAULT_ORDER_TIMELINE_DAYS = 7


def _require_campaign_owner(db: Session, campaign_id: str, business_user_id: str) -> models.Campaign:
    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if campaign is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="campaign_not_found",
            detail="Campaign not found",
        )
    if campaign.business_user_id != business_user_id:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="campaign_not_yours",
            detail="Not your campaign",
        )
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
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="auth_user_not_found",
            detail="User not found",
        )
    if user.role == AUTHOR_EXCLUDED_ROLE:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="campaign_author_only",
            detail="Only businesses and agencies can create campaigns.",
        )
    return user


def _checked_note(note: str | None) -> str | None:
    """A proposal note, refused if it carries contact details.

    THE PRODUCT RULE, AND THE HONEST CLAIM ABOUT IT. Swapping a phone number
    or an email is how a deal leaves Kolabo, and it takes the contract, the
    escrow and the fee with it — what the two of them agree afterwards has
    nothing behind it when it goes wrong. The note is where that is most
    tempting, because it is the first free-text field either side gets and it
    arrives before there is any contract to open a thread with. It is FRICTION,
    NOT PREVENTION: a determined sender can spell a number out in words. It
    stops the habit, which is most of them.

    APPLIED AT EVERY WRITER OF Proposal.note, not just the obvious one. A
    creator's bid, the business's counter, and the note on either kind of
    direct order are four different functions writing the same column, and a
    guard on one of them is worse than no guard — it looks finished. The two
    order paths are checked in the RESOLVERS rather than in _place_order,
    which keeps the property campaigns.cart depends on: every item in a basket
    is held to the rule before a single row is written.

    Never redacted. An altered note is worse than a refused one — these are
    the terms of a deal, and a sentence quietly edited by the platform is a
    term nobody agreed to.
    """
    check_no_contact_details(note, "proposal note")
    return note


def _checked_description(description: str | None) -> str | None:
    """A brief in prose, refused if it carries contact details.

    THE WIDEST-READ TEXT ON THE PLATFORM, which is why it is guarded even
    though it is the brand's own words about the brand's own campaign. The
    note above is read by ONE counterparty. An open brief is readable by every
    signed-in creator on the board, so a number in a description is not one
    leak that might cost one deal: it is the buyer's phone number placed in
    front of the entire supply side in a single post, and every creator who
    takes it off the board is a deal with no contract, no escrow and no
    recourse for either side. A brand doing it does not even have to intend
    anything — "des questions ? appelez-nous" is a habit, not a scheme, which
    is exactly the case app.core.contact_guard is built to catch.

    APPLIED AT BOTH WRITERS OF Campaign.description, for the reason
    _checked_note gives about its own four: half a rule looks finished and is
    not. Description is deliberately NOT in campaigns.editing.LOCKED_FIELDS —
    it is description and not terms, so it stays editable from draft to
    cancellation — and a guard that only ran at create would therefore be one
    a brand clears by saving the brief a second time.

    Same 400 and the same sentence as every other surface, naming the field so
    the author knows which box to fix. Never redacted: a brief quietly edited
    by the platform is a brief creators are pricing against words the brand
    never wrote.

    A closed brief is guarded too, and that is not overreach. is_open is one
    PATCH away at any time, and a description written while nobody could read
    it does not become safe the moment the brand opens the board.
    """
    check_no_contact_details(description, "brief description")
    return description


def _checked_campaign_status(value: str | None) -> str | None:
    """A status a buyer may filter its own list by, or a 400 naming the set.

    Refused rather than answered with an empty list, which is the opposite of
    what discovery search does with an unknown platform — and the difference
    is whose data is being asked about. An empty search result is a true
    answer about strangers. An empty list of YOUR OWN campaigns reads as "you
    have none", which is the single most alarming thing this endpoint could
    say to somebody with a quarter of live briefs, and it sends them to
    support rather than to the fix.

    A module-level helper rather than an inline check because the parameter it
    validates is called `status`, which shadows the fastapi module of the same
    name inside list_my_campaigns. Here the name is free.
    """
    if value is None or value in MY_CAMPAIGN_STATUSES:
        return value
    raise AppError(
        status.HTTP_400_BAD_REQUEST,
        code="campaign_status_unknown",
        values={"statuses": ", ".join(MY_CAMPAIGN_STATUSES)},
        detail=f"status must be one of: {', '.join(MY_CAMPAIGN_STATUSES)}",
    )


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
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                code="campaign_platform_unsupported",
                values={"platform": platform, "allowed": ", ".join(sorted(PLATFORM_DELIVERABLES))},
                detail=f"{platform} is not a supported platform. Allowed: {', '.join(sorted(PLATFORM_DELIVERABLES))}",
            )
        if not is_valid_pair(platform, deliverable_type):
            allowed = ", ".join(PLATFORM_DELIVERABLES.get(platform, [])) or "none"
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                code="deliverable_not_on_platform",
                values={"type": deliverable_type, "platform": platform, "allowed": allowed},
                detail=f"{deliverable_type} is not available on {platform}. Allowed: {allowed}",
            )
        quantity = d.get("quantity")
        # bool is an int subclass in Python, so `true` would otherwise slip
        # through as a quantity of 1.
        if not isinstance(quantity, int) or isinstance(quantity, bool) or not (
            1 <= quantity <= MAX_DELIVERABLE_QUANTITY
        ):
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                code="campaign_quantity_range",
                values={"min": 1, "max": MAX_DELIVERABLE_QUANTITY},
                detail=f"Deliverable quantity must be a whole number between 1 and {MAX_DELIVERABLE_QUANTITY}",
            )


def _publish_ready(campaign: models.Campaign) -> bool:
    return bool(campaign.budget_amount) and bool(campaign.deliverables) and campaign.deadline is not None


def _to_out(campaign: models.Campaign) -> dict:
    return {
        "id": campaign.id,
        "business_user_id": campaign.business_user_id,
        "title": campaign.title,
        "description": campaign.description,
        "budget_amount": campaign.budget_amount,
        "budget_currency": campaign.budget_currency,
        "deliverables": campaign.deliverables,
        "deadline": campaign.deadline,
        "status": campaign.status,
        "is_direct": campaign.is_direct,
        # The open-board fields travel on every campaign payload, not only on
        # the board's own row. The buyer's list of its campaigns has to be
        # able to say which briefs strangers can apply to — that is the
        # difference between a brief with three invited creators and one that
        # may collect thirty applications overnight — and a PATCH that
        # changed the targeting has to echo back what it changed. Left off,
        # the schema defaults would fill in False and empty lists, which is
        # worse than absent: it would report a targeted, open brief as a
        # closed one that targets nobody.
        #
        # `or []` because the columns are NOT NULL but rows written before
        # b5d2e9f31a04 ran through a create_all schema may still hold null.
        "is_open": campaign.is_open,
        "target_categories": campaign.target_categories or [],
        "target_countries": campaign.target_countries or [],
        "target_min_followers": campaign.target_min_followers,
        "target_max_followers": campaign.target_max_followers,
    }


def create_campaign(db: Session, business_user_id: str, payload: schemas.CampaignCreate) -> dict:
    # Checked before anything is validated or written: who may author a brief
    # is a question about the caller, not about the payload, and answering it
    # first keeps a creator from getting field-level errors on a request that
    # was never going to be accepted.
    _require_campaign_author(db, business_user_id)
    # Before the catalog check and before any row is built. A brief whose
    # prose cannot be published should hear about the prose, not first be
    # marched through a deliverables error it would have hit anyway.
    description = _checked_description(payload.description)
    deliverables = [d.model_dump() for d in payload.deliverables]
    # Validated even for drafts: a draft with deliverables the catalog does
    # not recognise would only blow up later, at publish, when the fix is no
    # longer fresh in the author's mind.
    _validate_deliverables(deliverables)
    campaign = models.Campaign(
        business_user_id=business_user_id,
        title=payload.title,
        description=description,
        budget_amount=payload.budget_amount,
        budget_currency=payload.budget_currency,
        deliverables=deliverables,
        deadline=payload.deadline,
        status=models.DRAFT,
        # Taken at creation as well as on a PATCH, because deciding who a
        # brief is for is part of writing it: making a brand save the brief
        # and then open it in a second request would be two calls for one
        # decision. The schema still defaults is_open to False, so a client
        # that has never heard of the board cannot open a brief by accident.
        is_open=payload.is_open,
        # Coerced to a list because the schema's null-clears rule hands back
        # [] for an explicit null but None for a field nobody sent, and the
        # column is NOT NULL either way.
        target_categories=list(payload.target_categories or []),
        target_countries=list(payload.target_countries or []),
        target_min_followers=payload.target_min_followers,
        target_max_followers=payload.target_max_followers,
    )
    if payload.publish:
        if not _publish_ready(campaign):
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                code="campaign_publish_incomplete",
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
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="campaign_publish_incomplete",
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
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="campaign_publish_before_inviting",
            detail="Publish the campaign before inviting",
        )
    influencer = db.query(User).filter(User.id == influencer_user_id).first()
    if influencer is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="campaign_influencer_not_found",
            detail="Influencer not found",
        )
    if not influencer.is_verified:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="campaign_influencer_not_verified",
            detail="This influencer is not verified yet and cannot be invited",
        )
    invitation = models.CampaignInvitation(
        campaign_id=campaign_id, influencer_user_id=influencer_user_id, status=models.INVITED
    )
    db.add(invitation)
    notify(
        db,
        influencer_user_id,
        "campaign_invitation",
        f"You were invited to the campaign {campaign.title}",
        # NO LINK, and it is not an omission. A creator answers an invitation
        # on /invitations, which is a flat list with no id in the URL and no
        # anchor to scroll to, and routeForType already sends this type there.
        # A link that only repeats the fallback is a second copy of the same
        # fact to keep correct.
        params={"key": "invitation_received", "campaign": campaign.title},
    )
    db.commit()
    db.refresh(invitation)
    # The row the client just created renders as a person straight away,
    # rather than as a user id until the campaign page is reloaded.
    identity = creator_identities(db, [influencer_user_id]).get(influencer_user_id)
    return _invitation_out(invitation, identity)


def _place_order(
    db: Session,
    business_user_id: str,
    creator_user_id: str,
    title: str,
    deliverables: list[dict],
    rate_amount: int,
    currency: str,
    timeline_days: int,
    note: str | None,
    notice: str,
    notice_key: str,
    commit: bool = True,
) -> dict:
    """Build the order itself: a hidden campaign, one invitation, one offer.

    Shape of the thing, and why. An order is a HIDDEN, single-creator campaign
    carrying exactly one invitation and one proposal — not a table of its own.
    Contracts, escrow, reviews and disputes all already hang off a campaign
    and a proposal, and giving orders their own model would mean a second
    parallel path into the money code: two ways to reach a payout, two places
    to get a refund wrong, every future change to escrow needing to be made
    twice. One payment path is worth the small strangeness of a campaign
    nobody can browse.

    Every form of order comes through here, and that is deliberate rather than
    convenient. A package order, a negotiated order and one creator's share of
    a cart checkout are the SAME object downstream — one accept path, one
    contract path, one escrow path — and the only way that stays true is for
    one function to build all of them. Two builders would drift, and where
    they drifted is the code that decides what a contract says.

    Why deliverables is a LIST. A single order has exactly one, and for most
    of this file's life the parameter was one dict. A cart checkout is where
    that stops holding: three packages bought from the same creator are one
    order — one invitation, one answer, one contract, one escrow — carrying
    three deliverables, and the campaign model already stored a list because a
    brief always could. Widening the parameter was cheaper and safer than a
    second builder for multi-deliverable orders. rate_amount is the whole
    order's price, so for a cart it is the sum the caller worked out.

    The note arrives already checked for contact details — both resolvers run
    _checked_note before returning terms, which is what lets a cart refuse a
    basket before it has written half of it. Nothing is re-checked here; one
    answer to "may this note be written" is enough.

    Who is proposing, and why it is the business. Either the buyer picked a
    price the creator had already published and offered it back, or it named
    terms of its own; both are the brand making an offer, so author_role is
    business. That is what makes the creator's accept-or-decline an answer
    rather than a second offer.

    commit=False is for callers placing several orders that must land
    together. It flushes instead, so the ids in the returned dict are real,
    and leaves the transaction open for the caller to close once. Nothing else
    about the order changes: a cart's orders are ordinary orders that happened
    to be written in the same breath.

    What does NOT happen here: no money moves. The creator has
    ORDER_ACCEPT_WINDOW_HOURS to accept, and escrow is funded only after they
    do. That ordering is the whole reason the flow is shaped this way — until
    both sides have agreed there is nothing in the system to refund, so a
    decline or a lapse is simply a closed order and never a payments problem.

    All of it in one transaction: a campaign with no invitation, or an
    invitation with no offer attached, is an order the creator can see and
    cannot answer.
    """
    campaign = models.Campaign(
        business_user_id=business_user_id,
        title=title,
        budget_amount=rate_amount,
        budget_currency=currency,
        deliverables=list(deliverables),
        # No deadline. A brief needs one because creators bid against it and
        # have to know what they are bidding on; an order has no bidding, and
        # the proposal's timeline_days is the commitment instead.
        deadline=None,
        # Published on creation, bypassing _publish_ready on purpose: that
        # gate exists so a half-written brief cannot go live in front of
        # creators. An order is complete the moment it is placed — the terms
        # are already agreed on one side — and it goes in front of exactly one
        # person.
        status=models.PUBLISHED,
        is_direct=True,
    )
    db.add(campaign)
    # Flushed, not committed: the invitation and the proposal need the
    # campaign id, and all three land or none of them do.
    db.flush()

    invitation = models.CampaignInvitation(
        campaign_id=campaign.id, influencer_user_id=creator_user_id, status=models.INVITED
    )
    db.add(invitation)

    proposal = models.Proposal(
        campaign_id=campaign.id,
        influencer_user_id=creator_user_id,
        version=1,
        rate_amount=rate_amount,
        rate_currency=currency,
        timeline_days=timeline_days,
        note=note,
        author_role=models.AUTHOR_BUSINESS,
        status=models.SUBMITTED,
        # Only direct orders carry an expiry. A brief's proposals stay open
        # indefinitely because nobody promised anything by leaving one open;
        # here a buyer is waiting on an answer to terms it already named.
        expires_at=models.utcnow() + timedelta(hours=ORDER_ACCEPT_WINDOW_HOURS),
    )
    db.add(proposal)

    notify(
        db,
        creator_user_id,
        "direct_order",
        notice,
        # No link, for the same reason as an invitation: the creator answers an
        # order from /invitations, which takes no id, and routeForType goes
        # there already.
        #
        # The KEY comes from the caller and the VALUES do not. The three ways
        # to place an order say three different sentences — a custom offer, a
        # package bought at its published price, a basket — but every one of
        # them names the order and the window, and both are already arguments
        # here. Threading two values through three call sites to say the same
        # thing three times is how they drift apart.
        params={"key": notice_key, "title": title, "hours": ORDER_ACCEPT_WINDOW_HOURS},
    )
    if commit:
        db.commit()
        db.refresh(campaign)
        db.refresh(proposal)
    else:
        # The caller is placing more than one and will commit them together.
        # Flushing is enough to hand back real ids.
        db.flush()
    return {
        "campaign_id": campaign.id,
        "proposal_id": proposal.id,
        "expires_at": proposal.expires_at,
    }


def create_order(db: Session, business_user_id: str, payload: schemas.OrderIn) -> dict:
    """Place an order: a package at its listed price, or negotiated terms.

    One endpoint, two forms, exactly one of them per request. A body carrying
    both is not a preference to resolve — it is two different orders in one
    envelope, and guessing which one the buyer meant is how somebody ends up
    charged for the wrong thing. A body carrying neither is a client bug, and
    the error names the two shapes rather than the missing field, because the
    caller has to pick a form before it can pick fields.

    A half-filled custom offer is rejected the same way. There is no sensible
    default for a rate or a deliverable: an order with a blank in it is an
    order the creator cannot answer.
    """
    check_order_form(payload)
    if payload.package_id is not None:
        return create_direct_order(db, business_user_id, payload.package_id, payload.note)
    return create_negotiated_order(db, business_user_id, payload)


def check_order_form(payload) -> None:
    """Exactly one of the two shapes, completely filled in.

    Split out of create_order so a cart can hold each of its items to the same
    rule before anything is written. The rule is about the SHAPE of a request
    and nothing else — no database, no side effects — which is what makes it
    safe to run over twenty items in a loop.
    """
    supplied = [f for f in schemas.CUSTOM_OFFER_FIELDS if getattr(payload, f) is not None]

    if payload.package_id is not None and supplied:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="order_terms_both",
            values={"supplied": ", ".join(supplied)},
            detail=(
                "Send either package_id or custom terms, not both. "
                f"Custom terms received: {', '.join(supplied)}"
            ),
        )
    if payload.package_id is not None:
        return
    if not supplied:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="order_terms_missing",
            values={"fields": ", ".join(schemas.CUSTOM_OFFER_FIELDS)},
            detail=(
                "An order needs either package_id or a full custom offer ("
                f"{', '.join(schemas.CUSTOM_OFFER_FIELDS)})."
            ),
        )

    missing = [f for f in schemas.CUSTOM_OFFER_FIELDS if getattr(payload, f) is None]
    if missing:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="order_terms_incomplete",
            values={"missing": ", ".join(missing)},
            detail=f"A custom offer is incomplete. Missing: {', '.join(missing)}",
        )


def resolve_negotiated_terms(db: Session, business_user_id: str, offer) -> dict:
    """Check terms a brand typed, and hand back what an order would be made of.

    Everything here is a question, never a write. That is the point of the
    split: a cart has to be able to ask "is every one of these twenty items
    orderable" before it creates the first row, and the only way to do that
    without a second copy of these rules is for the rules to live somewhere
    that does not build anything.

    The order of the checks is load-bearing and unchanged. Ordering yourself
    is answered before the target's role, because a creator offering to
    themselves would fail both and "you cannot send an offer to yourself" is
    the true reason.
    """
    negotiated.validate_offer(offer)

    if offer.creator_user_id == business_user_id:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="order_to_self",
            detail="You cannot send an offer to yourself.",
        )
    creator = db.query(User).filter(User.id == offer.creator_user_id).first()
    if creator is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="campaign_influencer_not_found",
            detail="Influencer not found",
        )
    if creator.role != AUTHOR_EXCLUDED_ROLE:
        # AUTHOR_EXCLUDED_ROLE is the selling side of the market: the role
        # that may not author a brief is precisely the role that can be sent
        # one. Reused rather than re-stated so a new buyer-side role cannot
        # accidentally become orderable.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="order_target_not_creator",
            detail="You can only send an offer to a creator.",
        )

    return {
        "creator_user_id": offer.creator_user_id,
        "title": negotiated.order_title(offer.platform, offer.deliverable_type, offer.quantity),
        "deliverable": {
            "platform": offer.platform,
            "type": offer.deliverable_type,
            "quantity": offer.quantity,
        },
        "rate_amount": offer.rate_amount,
        "currency": offer.currency.upper(),
        "timeline_days": offer.timeline_days,
        # Checked HERE rather than in _place_order so that a cart is refused
        # before it has written any of its rows, which is the whole reason
        # this function exists apart from the builder.
        "note": _checked_note(offer.note),
    }


def resolve_package_terms(
    db: Session, business_user_id: str, package_id: str, note: str | None = None
) -> dict:
    """Read a package's terms off the live row, and check it can be bought.

    None of the terms are re-entered by the buyer: that is the whole promise
    of a package, that the creator already decided all of it and published a
    price. Read at order time rather than trusted from the client, which is
    also why a cart needs no stored prices — whatever the package says at
    checkout is what the order says.

    Like resolve_negotiated_terms this only asks questions, so a cart can
    validate every item before writing anything.
    """
    package = db.query(Package).filter(Package.id == package_id).first()
    if package is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="package_not_found",
            detail="Package not found",
        )
    if not package.is_active:
        # A creator deactivates a package when they have stopped selling it —
        # out of season, fully booked, price out of date. Honouring the old
        # price would be selling something nobody is offering.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="order_package_inactive",
            detail="This package is not available at the moment.",
        )
    # Checked before the role guard so the message is the true one. A creator
    # buying their own package would also fail the role check, but "only
    # businesses can order" is not what went wrong.
    if package.user_id == business_user_id:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="order_own_package",
            detail="You cannot order your own package.",
        )

    timeline_days = DEFAULT_ORDER_TIMELINE_DAYS
    if package.duration_unit == "days" and package.duration_value:
        timeline_days = package.duration_value

    return {
        "creator_user_id": package.user_id,
        "title": package.title,
        "deliverable": {
            "platform": package.platform,
            "type": package.deliverable_type,
            "quantity": package.quantity,
        },
        "rate_amount": package.price_amount,
        "currency": package.currency,
        "timeline_days": timeline_days,
        # The buyer's own words, and the only free text on a package order —
        # so the only place contact details could ride in. Same rule, same
        # helper, same reason as everywhere else this column is written.
        "note": _checked_note(note),
    }


def create_negotiated_order(db: Session, business_user_id: str, payload: schemas.OrderIn) -> dict:
    """A brand offers its own terms instead of taking a package as listed.

    Plenty of work does not fit a listed bundle — a different quantity, a
    tighter timeline, a rate the two sides talked about — and those were
    exactly the deals that left the platform to be agreed somewhere we cannot
    contract or escrow them. So the terms are negotiable and nothing else is:
    the same 48 hour window, the same hidden campaign, the same accept and
    decline endpoints.

    What is different is only that nobody validated these terms before. A
    package was checked when it was published; typed-in terms are checked in
    resolve_negotiated_terms (campaigns.negotiated), price floor included.
    """
    terms = resolve_negotiated_terms(db, business_user_id, payload)
    # Same guard, same rule, same wording as authoring a brief and as ordering
    # a package: an order IS a campaign, and the buying side of the market is
    # the side that may create one. After the terms, so a creator offering to
    # themselves still hears the true reason first.
    _require_campaign_author(db, business_user_id)

    return _place_order(
        db,
        business_user_id=business_user_id,
        creator_user_id=terms["creator_user_id"],
        title=terms["title"],
        deliverables=[terms["deliverable"]],
        rate_amount=terms["rate_amount"],
        currency=terms["currency"],
        timeline_days=terms["timeline_days"],
        note=terms["note"],
        notice=(
            f"A brand sent you a custom offer: {terms['title']}. You have "
            f"{ORDER_ACCEPT_WINDOW_HOURS} hours to accept or decline."
        ),
        notice_key="order_custom_offer",
    )


def create_direct_order(db: Session, business_user_id: str, package_id: str, note: str | None = None) -> dict:
    """A brand buys a creator's package at the published price.

    The terms are the package's, none of them re-entered, and they are read by
    resolve_package_terms. The order this produces is built by _place_order
    like every other, which is where the shape of an order and the reasons for
    it are written down.
    """
    terms = resolve_package_terms(db, business_user_id, package_id, note)
    # Same guard, same rule, same wording as authoring a brief: an order IS a
    # campaign, and the buying side of the market is the side that may create
    # one. Reused rather than re-stated so the two can never drift apart.
    _require_campaign_author(db, business_user_id)

    return _place_order(
        db,
        business_user_id=business_user_id,
        creator_user_id=terms["creator_user_id"],
        title=terms["title"],
        deliverables=[terms["deliverable"]],
        rate_amount=terms["rate_amount"],
        currency=terms["currency"],
        timeline_days=terms["timeline_days"],
        note=terms["note"],
        notice=(
            f"A brand ordered your package {terms['title']}. You have "
            f"{ORDER_ACCEPT_WINDOW_HOURS} hours to accept or decline."
        ),
        notice_key="order_package",
    )


def chain_versions(db: Session, campaign_id: str, influencer_user_id: str) -> list[models.Proposal]:
    """Every version exchanged between one creator and one campaign, oldest first.

    THE CREATOR COULD NOT SEE THIS. A brand opening a brief has always got the
    whole thread — campaign_detail sends every proposal row and the page
    reassembles them per creator — while the creator's own invitations list
    carried only the LIVE version. So from version two onwards the person
    being negotiated with was reading a number with no idea what it was
    answering: their own last offer, the counter before it, and what actually
    moved between them were all on the other side of a screen they cannot
    open. The invitations page even said so out loud, in a hint apologising
    for it.

    Same cap and same reasoning as the brand's list (MAX_PROPOSAL_VERSIONS,
    taken from the RECENT end): the last version is the live offer and the
    only one that can be accepted, so truncating from that end would hide the
    one row the page exists to act on. Queried newest-first with a limit so
    the database does the cutting, then flipped to read as a conversation.
    """
    versions = (
        db.query(models.Proposal)
        .filter(
            models.Proposal.campaign_id == campaign_id,
            models.Proposal.influencer_user_id == influencer_user_id,
        )
        .order_by(models.Proposal.created_at.desc(), models.Proposal.version.desc())
        .limit(MAX_PROPOSAL_VERSIONS)
        .all()
    )
    versions.reverse()
    return versions


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


def submit_proposal(
    db: Session,
    campaign_id: str,
    influencer_user_id: str,
    payload: schemas.ProposalIn,
    is_application: bool = False,
) -> dict:
    """Write the next version of one creator's offer on one campaign.

    THE ONE PLACE A PROPOSAL ROW IS WRITTEN. An invited creator pricing a
    brief, a creator countering a direct order, and a creator applying to an
    open brief off the board all land here — campaigns.board.apply_to_campaign
    checks whether an application is allowed and then calls this rather than
    building a proposal of its own. A second writer would be a second place
    for the version numbering to drift, and the version chain is what a
    contract gets written from.

    is_application changes THE NOTIFICATION AND NOTHING ELSE. The row, the
    version chain, the supersede rule and the brand's proposals list are
    identical either way, and they must stay identical — that sameness is the
    entire reason the board delegates here. But they are not the same news to
    wake up to: a bid from an invited creator is an answer the brand was
    waiting for, while an application is a stranger the brand now has to
    decide whether to look at. One line of a bell menu has to tell them apart,
    because that is where the brand decides which one to open.

    Both messages NAME THE CREATOR. These strings go out by email as well as
    into the bell, where the reader has no screen to cross-reference against,
    and "a new proposal was submitted" left them with neither who nor which
    brief — two questions that can only be answered by opening the app.
    """
    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if campaign is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="campaign_not_found",
            detail="Campaign not found",
        )
    if campaign.status != models.PUBLISHED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="campaign_not_open",
            detail="Campaign is not open for proposals",
        )

    # Before the chain is touched, so a refused note leaves the previous
    # version live rather than superseded by something that was never written.
    note = _checked_note(payload.note)

    latest = latest_in_chain(db, campaign_id, influencer_user_id)
    # A settled negotiation takes no new versions. The campaign-status guard
    # above only catches a CANCELLED brief; a brief whose deal is DONE stays
    # published, because generate_from_proposal marks the accepted version and
    # never touches the campaign. Without this a creator could counter a signed
    # contract into drifting out from under itself, or a bidder the brand
    # already rejected could re-open the chain — the submit side of the hole
    # reply_to_proposal closes on the business side.
    #
    # Only the three TERMINAL resolutions are closed. withdrawn and superseded
    # are re-biddable on purpose: a creator who pulled their offer, or whose
    # version was superseded, is meant to be able to bid again (board.apply
    # only refuses while the latest is still submitted). So this is NOT
    # reply_to_proposal's blanket "!= submitted", which would wrongly block
    # them too.
    if latest is not None and latest.status in (
        models.PROPOSAL_ACCEPTED,
        models.PROPOSAL_REJECTED,
        models.PROPOSAL_DECLINED,
    ):
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="proposal_negotiation_closed",
            detail="This negotiation is closed and cannot be answered",
        )

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
        note=note,
        author_role=models.AUTHOR_INFLUENCER,
        status=models.SUBMITTED,
        # Carried forward from whatever this version answers, exactly as
        # reply_to_proposal carries it the other way. This is how a creator
        # counters a direct order — there is no creator-side counter endpoint,
        # the next version IS the counter — and a counter is still the same
        # order on the same clock. Left to default it went to NULL, which took
        # the order off the clock entirely: the expiry sweep only touches rows
        # with an expires_at, so a countered order would have sat open
        # forever. Null stays null for a brief, which is what a brief wants.
        expires_at=latest.expires_at if latest is not None else None,
    )
    db.add(proposal)
    # Resolved before the notification rather than after the commit, because
    # the notification spends it. It is the same single lookup the response
    # needs either way, moved rather than added.
    identity = creator_identities(db, [influencer_user_id]).get(influencer_user_id) or blank_identity()
    named = identity["display_name"]
    actor = named or UNNAMED_CREATOR
    # THE BRIEF, not /campaigns. Both of these are read and answered in one
    # place — the proposal list on the campaign page — and the buyer may have
    # several briefs open. For an application the link does not merely beat
    # the fallback, it replaces nothing at all: routeForType has no entry for
    # "brief_application", so until now an application was a row that opened
    # nowhere. campaign.id is already real here (the campaign was read from
    # the database), so no flush is needed to build the path.
    where = f"/campaigns/{campaign.id}"
    if is_application:
        notify(
            db,
            campaign.business_user_id,
            "brief_application",
            f"{actor} applied to your open brief {campaign.title}",
            link=where,
            params=(
                {"key": "brief_application", "name": named, "campaign": campaign.title}
                if named
                else {"key": "brief_application_anon", "campaign": campaign.title}
            ),
        )
    else:
        notify(
            db,
            campaign.business_user_id,
            "proposal_submitted",
            f"{actor} sent a proposal for {campaign.title}",
            link=where,
            params=(
                {"key": "proposal_submitted", "name": named, "campaign": campaign.title}
                if named
                else {"key": "proposal_submitted_anon", "campaign": campaign.title}
            ),
        )
    db.commit()
    db.refresh(proposal)
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

    Which is exactly why the note is guarded on THIS side too. A rule that
    stopped a creator writing a phone number and let the brand write one back
    would not be a rule, it would be a formality — and this is the reply that
    was going to WhatsApp in the first place.

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
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="proposal_not_found",
            detail="Proposal not found",
        )

    latest = latest_in_chain(db, campaign_id, proposal.influencer_user_id)
    if latest.status != models.SUBMITTED:
        # Accepted or rejected: the negotiation is over. Reopening it by reply
        # would let terms drift after a contract was written from them.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="proposal_closed",
            detail="This proposal is closed and cannot be answered",
        )

    # Before the supersede below, for the same reason as in submit_proposal: a
    # refused reply must leave the creator's offer standing.
    note = _checked_note(payload.note)

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
        note=note,
        author_role=models.AUTHOR_BUSINESS,
        status=models.SUBMITTED,
        # Carried forward, not restarted. A direct order that is being
        # negotiated is still the same order on the same clock; resetting the
        # window on every counter would let a chain run forever.
        expires_at=latest.expires_at,
    )
    latest.status = models.SUPERSEDED
    db.add(reply)
    # Named, and distinguished. "The business replied to your proposal" told a
    # creator neither who was asking nor whether anything had moved — and a
    # counter changes the money or the date, which is the only one of the two
    # that needs an answer. A creator with several live briefs cannot triage
    # a bell where every row says the same sentence.
    countered = payload.rate_amount is not None or payload.timeline_days is not None
    company = _company_name(db, business_user_id)
    buyer = company or UNNAMED_BUYER
    if countered:
        reply_params = (
            {"key": "proposal_countered", "name": company, "campaign": campaign.title}
            if company
            else {"key": "proposal_countered_anon", "campaign": campaign.title}
        )
    else:
        reply_params = (
            {"key": "proposal_replied", "name": company, "campaign": campaign.title}
            if company
            else {"key": "proposal_replied_anon", "campaign": campaign.title}
        )
    notify(
        db,
        latest.influencer_user_id,
        "proposal_reply",
        (
            f"{buyer} countered your proposal for {campaign.title}"
            if countered
            else f"{buyer} replied to your proposal for {campaign.title}"
        ),
        # No link: a creator reads a negotiation inside /invitations, which
        # takes no id and has no per-card anchor, and routeForType sends any
        # proposal_* type there already. The asymmetry is real and worth
        # naming — the brand gets a link to the full thread, the creator gets
        # a list showing only the live version — but it is a screen that does
        # not exist yet, not a link this line is withholding.
        params=reply_params,
    )
    db.commit()
    db.refresh(reply)
    identity = creator_identities(db, [reply.influencer_user_id]).get(reply.influencer_user_id)
    return _proposal_out(reply, identity)


def _invitation_out(inv: models.CampaignInvitation, identity: dict | None = None) -> dict:
    """An invitation row, saying who was invited.

    The identity is optional because the creator's own invitations list has no
    use for it — every row there is them, and looking it up would cost a query
    to tell somebody their own name. On the business's campaign page it is the
    entire point: this list used to render a bare user id beside a proposals
    list that rendered names, so one screen showed the same person two
    different ways.
    """
    return {
        "id": inv.id,
        "campaign_id": inv.campaign_id,
        "influencer_user_id": inv.influencer_user_id,
        "status": inv.status,
        **(identity or blank_identity()),
    }


def _proposal_out(p: models.Proposal, identity: dict | None = None) -> dict:
    """A proposal row, with the creator behind it named the shared way.

    A business choosing between proposals is choosing between people, and a
    list of ids gives it nothing to choose with. The audience number arrives
    with the name because that is the other half of the decision — and it is
    the biggest single platform, never a sum, for the reason spelled out in
    app.core.identity.
    """
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
        # When this version was sent. A chain without timestamps is a list of
        # numbers; with them it is a conversation, and "they countered four
        # days ago" is most of what somebody needs to decide whether to chase.
        # Added for the creator's history and inherited by the brand's list,
        # which is reading the same rows through the same serialiser.
        "created_at": p.created_at,
        **(identity or blank_identity()),
    }


def list_my_campaigns(
    db: Session,
    business_user_id: str,
    status: str | None = None,
    created_after=None,
    created_before=None,
) -> list[dict]:
    """The buyer's own campaigns, briefs and direct orders alike, newest first.

    Deliberately NOT filtered on is_direct. Hiding direct orders is about
    keeping a private transaction off a public board; this list is scoped to
    the one person who placed them, and an order they cannot find is an order
    they cannot chase.

    THE FILTERS ARE THE BUYER'S OWN VIEW, exactly as the open board's are the
    creator's: they narrow what comes back and change nothing about the rows
    or the order (still newest first). A brand three months into using this
    has a list it scrolls to find last week's brief in, and "which of these
    are still live" is the question it opens the page asking. Both default to
    None, so a client that sends neither gets the whole list it always got.

    THE DATE RANGE IS ON created_at AND IS IN UTC, because created_at is
    stored as naive UTC (models.utcnow). A buyer in Cotonou asking for "today"
    gets the UTC day, which is an hour off theirs and is the honest thing to
    do until the client sends a timezone: guessing one here would put a brief
    in the wrong day silently, where being an hour wide is at least uniform.

    created_before is INCLUSIVE OF THE WHOLE DAY. Somebody picking a date on a
    calendar means "up to and including that day", and a naive `created_at <=
    midnight` would drop everything written after midnight on the day they
    picked — which is all of it.

    `status` shadows the fastapi module imported at the top of this file, but
    only inside this function, and nothing in here needs it: the one refusal
    it can raise lives in _checked_campaign_status, where the name is free.
    The parameter keeps the field's name because that is what the client and
    the column already call it.
    """
    query = db.query(models.Campaign).filter(
        models.Campaign.business_user_id == business_user_id
    )
    checked = _checked_campaign_status(status)
    if checked is not None:
        query = query.filter(models.Campaign.status == checked)
    if created_after is not None:
        query = query.filter(
            models.Campaign.created_at >= datetime.combine(created_after, time.min)
        )
    if created_before is not None:
        # The start of the NEXT day, strictly greater-than, which is how a
        # whole inclusive day is expressed against a timestamp column.
        query = query.filter(
            models.Campaign.created_at
            < datetime.combine(created_before, time.min) + timedelta(days=1)
        )
    rows = query.order_by(models.Campaign.created_at.desc()).all()
    return [_to_out(c) for c in rows]


def get_campaign_detail(db: Session, campaign_id: str, business_user_id: str) -> dict:
    """The owner's view of one campaign: every invitation and every proposal.

    Applications from the open board need nothing special here and get
    nothing: this has always selected EVERY proposal on the campaign and has
    never filtered by invitation, so a bid from a creator the brand never
    invited sits in the same list as the ones it did — which is where the
    brand answers, counters or rejects it with the endpoints it already has.
    """
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
    # One lookup for the whole page, covering both lists. They name the same
    # handful of creators — usually literally the same people, since an
    # invitation is what produces a proposal — and they now render them
    # identically, which is the point: a business should not have to work out
    # that the id in one list is the name in the other.
    identities = creator_identities(
        db,
        [i.influencer_user_id for i in invitations] + [p.influencer_user_id for p in proposals],
    )
    out = _to_out(campaign)
    out["invitations"] = [_invitation_out(i, identities.get(i.influencer_user_id)) for i in invitations]
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
    and this is the surface where they find out somebody bought their package
    or sent them terms of their own. is_direct on the nested campaign is what
    lets the client render it as an order with a clock rather than as a brief
    to price.

    Each row carries its negotiation TWICE, and the two are not redundant.
    `proposal` is the live version: for a brief that is context, for an order
    it is the thing itself — accept and decline are addressed by proposal id,
    and this is the only creator-facing list an order appears in (campaign
    detail is owner-only), so without it the creator would see an order they
    had no way to answer. `proposal_history` is every version, oldest first,
    which is what the brand has always had and the creator never did.
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
        # Identity is deliberately left blank here. It exists so a BUSINESS
        # can tell one creator from another; every row in this list belongs to
        # the creator reading it, so the lookup would buy nothing.
        # The whole thread, and the live version separately.
        #
        # `proposal` stays exactly what it was — the live version, which is
        # what accept and decline are addressed to and what every existing
        # client reads. `proposal_history` is additive: a client that has not
        # been taught about it behaves as it did, and the one that has can
        # show the creator the rounds that were previously invisible to them.
        item["proposal_history"] = [
            _proposal_out(v) for v in chain_versions(db, campaign.id, influencer_user_id)
        ]
        # Still latest_in_chain, deliberately, rather than the last element of
        # the list above. The two agree — a higher version is always the newer
        # row — but this field is what accept and decline are addressed to,
        # and recomputing it a second way for the sake of saving a query is
        # risk taken for nothing. The history is additive; this line is not
        # touched.
        latest = latest_in_chain(db, campaign.id, influencer_user_id)
        item["proposal"] = _proposal_out(latest) if latest is not None else None
        result.append(item)

    # THE APPLICATIONS, which have no invitation row at all. A creator who
    # bids off the board writes a proposal chain and nothing else — that is
    # apply_to_campaign's deliberate design — but this list used to iterate
    # invitation rows only, so the brand's counter on an application reached
    # the creator as a notification with no surface behind it: the offer was
    # on the table and invisible. Each such chain becomes a synthetic row with
    # status "applied" and a stable synthetic id; there is no invitation to
    # accept or decline, and the clients act on the proposal, exactly as they
    # do for a brief's negotiation.
    invited_campaign_ids = {inv.campaign_id for inv in invitations}
    applied_campaign_ids = [
        row[0]
        for row in db.query(models.Proposal.campaign_id)
        .filter(models.Proposal.influencer_user_id == influencer_user_id)
        .distinct()
        .all()
        if row[0] not in invited_campaign_ids
    ]
    for campaign_id in applied_campaign_ids:
        campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
        if campaign is None:
            continue
        if campaign.business_user_id not in company_names:
            company_names[campaign.business_user_id] = _company_name(db, campaign.business_user_id)
        latest = latest_in_chain(db, campaign_id, influencer_user_id)
        result.append(
            {
                "id": f"applied-{campaign_id}",
                "campaign_id": campaign_id,
                "influencer_user_id": influencer_user_id,
                "status": "applied",
                "campaign": _to_out(campaign),
                "business_company_name": company_names[campaign.business_user_id],
                "proposal_history": [
                    _proposal_out(v) for v in chain_versions(db, campaign_id, influencer_user_id)
                ],
                "proposal": _proposal_out(latest) if latest is not None else None,
            }
        )
    return result

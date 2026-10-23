"""Correcting a brief, and closing one without erasing it.

Three operations that all answer the same question — what may a buyer still
change once other people are looking at the campaign — and the answers are the
product rules, written down once here:

  * A DRAFT is nobody's business but its author's. Nothing has been shown to
    anyone, nothing hangs off it, so everything is editable and the row can
    simply go.

  * Once PUBLISHED, title and description stay editable: they are
    description, not terms. Change them and the bid on the table still means
    what it meant. Budget, currency, deliverables, deadline and the content
    licence are the terms creators price AGAINST, and they lock the moment a
    proposal exists. A creator who bid 40k to make three posts against a 500k
    budget did not bid to make six against 200k, and silently rewriting that
    turns a submitted bid into a bid for different work — which nobody agreed
    to and which the contract would then be written from.

  * Once a CONTRACT EXISTS, the title locks too, and for a different reason
    than the terms above. It is still description and no creator priced
    against it. What changes is that contract generation COPIES it into the
    document: contracts/service.py writes "Contract for campaign: {title}"
    into the body, the body is hashed at generation and is never amended, and
    the contract card then joins the live title back on beside it. Rename the
    brief afterwards and the card and the signed text say two different things
    about one agreement, with only one of them changeable.

  * A campaign with anything attached to it is never deleted. Proposals,
    contracts and the audit trail behind them are the record of what two
    parties said to each other; the buyer losing interest is not a reason to
    erase the other side's half of it. Cancel is the exit: it closes the
    campaign, tells the people who were invited, and leaves the history where
    it is.

Description staying editable forever is exactly why the contact guard has to
run HERE as well as at create: see service._checked_description. A rule that
only held the first time a brief was saved would be a rule a brand clears by
saving it a second time.

A separate module from service.py, which is already long and is about
creating campaigns and running the negotiation on them. The dependency runs
one way — router -> editing -> service — and contracts are read through
contracts.models (models only, never contracts.service, which imports
campaigns.service and would close the circle).
"""
from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.campaigns import completion, licence, models, schemas, service
from app.modules.contracts import models as contracts
from app.modules.notifications.service import notify

# The terms a creator prices against, and therefore the fields that stop being
# the buyer's alone once somebody has priced against them. Everything else on
# a campaign is description: rewrite it and the bid still means what it meant.
#
# licence_terms IS ONE OF THEM, and it is the entry most likely to be read as
# an odd fit, so: a creator who bid on a brief saying the brand would not
# redistribute the content did not bid on one saying the brand may run it in
# paid advertising for a year. The licence decides what the brand GETS, the
# budget decides what it pays, and a bid is a price for the pair of them.
# Clearing it is a change too, which falls out of the comparison below rather
# than needing a rule of its own.
LOCKED_FIELDS = ("budget_amount", "budget_currency", "deliverables", "deadline", "licence_terms")

# And the field that stops being the buyer's alone once a CONTRACT exists.
#
# A SEPARATE TUPLE BECAUSE IT IS A SEPARATE TRIGGER, not because the refusal
# differs. `title` is not a term and nobody priced against it, which is why it
# has to stay editable while a proposal is the only thing attached: a brand
# fixing a typo in the headline of a live brief is the ordinary case and
# breaking it would push people back to deleting and re-posting, which loses
# the proposals.
#
# What changes once a contract exists is that the title has been copied
# somewhere that can never be corrected. contracts/service.py::_build_body
# writes "Contract for campaign: {title}" into the body, contracts.body_sha256
# is a hash of that body taken at generation and never recomputed, and
# contracts/service.py::list_my_contracts joins the LIVE title onto every
# card. So a rename leaves the card and the document disagreeing about the
# same agreement, the document is the half that cannot move, and nothing
# anywhere records that the two were ever the same string.
#
# ANY contract counts, including a cancelled one. _contract below filters on
# the campaign alone, deliberately: a cancelled contract keeps its row and its
# body, that body still quotes the title it was generated with, and a creator
# who signed before the brand walked away is entitled to have it keep saying
# what it said.
#
# licence_terms is NOT repeated here, and does not need to be: it is locked by
# the proposal trigger above, which fires strictly earlier — a contract cannot
# exist without a proposal to generate it from.
#
# Locking rather than making the card stop joining the title. Both fix the
# disagreement; this one is smaller, needs nothing from either client, and
# matches what the rest of this flow already does with anything a contract has
# copied.
CONTRACT_LOCKED_FIELDS = ("title",)

# Why a field is locked, said once per group. The field name is prefixed by
# _refuse_locked, so one sentence serves every field in its tuple.
#
# Neither sentence suggests cancelling for the contract case, because
# cancel_campaign refuses outright once a contract exists (campaign_has_contract
# below): telling somebody to take an exit that is closed is worse than telling
# them nothing.
PRICED_AGAINST_REASON = (
    "a creator has already priced against it. Cancel this campaign and publish "
    "the new terms as a new brief."
)
IN_CONTRACT_REASON = (
    "a contract has been generated from this campaign and carries this title in "
    "its signed text. Agree new terms and generate a new contract."
)

# Said the same way by every entry point here, because it is one rule.
DIRECT_ORDER_DETAIL = (
    "A direct order cannot be edited. Its terms are a negotiation: counter it "
    "with a reply, or let the creator decline it."
)
ACTIVITY_DETAIL = "This campaign has activity; cancel it instead."
CONTRACT_DETAIL = (
    "This campaign has a contract. Unwinding a signed agreement is the dispute "
    "and refund path, not a cancellation."
)


def _reject_direct(campaign: models.Campaign) -> None:
    """A direct order is not a document one side edits.

    An order is a transaction between two parties: the buyer named terms, the
    creator is answering them, and the answer is priced against exactly what
    was offered. Letting the buyer edit it in place would let it move the
    price under a creator who is halfway through deciding — and there is
    already a way to change an order's terms that both sides can see, which is
    to counter it (another version in the chain). Deleting or cancelling one
    is the creator's decline, or the 48 hour window closing.
    """
    if campaign.is_direct:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="campaign_is_direct_order",
            detail=DIRECT_ORDER_DETAIL,
        )


def _refuse_locked(
    campaign: models.Campaign, data: dict, fields: tuple[str, ...], reason: str
) -> None:
    """Refuse any of `fields` that this patch is genuinely trying to change.

    ONE CODE FOR BOTH GROUPS, `campaign_field_locked`, with the field name
    travelling as a value. From the reader's side it is one rule — this field
    is not yours to change any more — and both clients render their own
    translated sentence from the code plus the field, so a second code would
    be two more sentences to keep in step in two languages for a difference
    nobody can see. `reason` is only the tail of the English fallback, which
    is what an API consumer and a log line get.

    Extracted from the loop that used to sit inline in update_campaign, so
    that the second group did not arrive as a second copy of it.
    """
    for field in fields:
        if field not in data:
            continue
        if data[field] == getattr(campaign, field):
            # Sending a field back unchanged is not a change. Clients post
            # whole forms, and failing a PATCH that asked for nothing would
            # make everything else on the form uneditable in every UI that
            # does.
            #
            # THIS IS WHY licence_terms IS CONVERTED TO ITS STORED SHAPE
            # BEFORE THIS RUNS (see update_campaign). The comparison is
            # against the column, and the column holds a validated block
            # carrying only the keys its option needs; a raw payload dump
            # would differ from it on every save and make the field
            # permanently locked for any client that posts its whole form.
            continue
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="campaign_field_locked",
            values={"field": field},
            detail=f"{field} cannot be changed: {reason}",
        )


def _proposal_count(db: Session, campaign_id: str) -> int:
    return (
        db.query(models.Proposal)
        .filter(models.Proposal.campaign_id == campaign_id)
        .count()
    )


def _invitations(db: Session, campaign_id: str) -> list[models.CampaignInvitation]:
    return (
        db.query(models.CampaignInvitation)
        .filter(models.CampaignInvitation.campaign_id == campaign_id)
        .all()
    )


def _contract(db: Session, campaign_id: str) -> contracts.Contract | None:
    """Any contract on this campaign, signed or still waiting on signatures.

    Pending counts. A contract that exists has already been generated from
    agreed terms and is sitting in front of two people to sign; the campaign
    behind it is no longer the buyer's to withdraw.

    So does cancelled, and that matters now that this result also locks the
    title: a cancelled contract keeps its row and its body, and that body
    still quotes the title it was written with.
    """
    return (
        db.query(contracts.Contract)
        .filter(contracts.Contract.campaign_id == campaign_id)
        .first()
    )


def update_campaign(
    db: Session, campaign_id: str, business_user_id: str, payload: schemas.CampaignPatch
) -> dict:
    """Correct a campaign, within what the people looking at it allow.

    Typos happen, and a brief nobody can fix is a brief that gets deleted and
    re-posted — which loses the proposals already on it. So editing is allowed
    and it is the SCOPE that narrows as the campaign acquires an audience.

    The one thing that never widens is what the text may CONTAIN. Description
    is editable from draft to cancellation, so it is the obvious way round a
    guard that only ran at create, and it is checked here with the same helper
    and the same sentence.
    """
    campaign = service._require_campaign_owner(db, campaign_id, business_user_id)
    _reject_direct(campaign)
    if campaign.status == models.CANCELLED:
        # Cancelling is how a campaign ends. Editing one afterwards would let
        # the terms of a closed brief drift away from what the people who bid
        # on it were shown.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="campaign_cancelled_immutable",
            detail="This campaign is cancelled and cannot be edited.",
        )

    # exclude_unset, the same semantics as the profile upsert: a field the
    # client did not send is untouched, and a nullable field it explicitly
    # sent as null IS cleared. The distinction matters because a form that
    # only edits the title posts only the title, and must not blank the rest.
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return service._to_out(campaign)

    if "title" in data and data["title"] is None:
        # The column is NOT NULL. Refused with a sentence rather than left to
        # fail on the insert.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="campaign_needs_title",
            detail="A campaign needs a title."
        )

    if "description" in data:
        # Same rule, same helper and same wording as authoring the brief. It
        # runs on the key being PRESENT rather than on the value being truthy,
        # so clearing the description to null still goes through the one
        # function that decides what a description may say — and an explicit
        # null is simply nothing to find.
        #
        # Order does not matter for the row: nothing below is written until
        # the setattr loop at the end, so a refused description leaves the
        # brief exactly as the creators reading it last saw it.
        service._checked_description(data["description"])

    if "licence_terms" in data:
        # THE STORED SHAPE, AND IT HAS TO BE COMPUTED BEFORE THE LOCK BELOW.
        #
        # model_dump turned the nested LicenceTermsIn into a dict carrying all
        # five keys, nulls included, while the column holds a validated block
        # with only the keys its option requires. Two different shapes of the
        # same statement, and _refuse_locked compares them for equality to
        # decide whether this patch is really changing anything — so a client
        # posting its whole form back unchanged would be refused with
        # campaign_field_locked for a field it never touched. Converting here
        # makes the two comparable and is also the only place the brand's
        # licence is validated on an edit.
        #
        # The validated block is taken from the PAYLOAD object rather than
        # from `data`, because licence.validated_block reads attributes and a
        # dict would need a second code path to cope with. An explicit null
        # clears the licence and validates to None, which is what a form
        # taking the clause back out sends.
        #
        # Refused before anything is written, like the description above, so a
        # half-stated licence leaves the brief exactly as the creators reading
        # it last saw it.
        data["licence_terms"] = licence.validated_block(payload.licence_terms)

    # THE CONTRACT LOCK FIRST, because it is the stronger statement and the
    # more useful sentence. A campaign carrying a contract almost always
    # carries a proposal as well, so a patch touching both groups could be
    # refused by either, and "this title is in a signed document" tells the
    # buyer something they cannot work out for themselves, while "a creator
    # priced against the budget" is about a different field entirely.
    #
    # The query runs only when the patch actually touches one of these fields,
    # so a budget or description edit still costs exactly the queries it did
    # before this lock existed. _contract is not free: it is a lookup on
    # contracts.campaign_id, which is indexed, but on a PATCH that could not
    # possibly be refused by it there is no reason to ask at all.
    if any(field in data for field in CONTRACT_LOCKED_FIELDS):
        if _contract(db, campaign_id) is not None:
            _refuse_locked(campaign, data, CONTRACT_LOCKED_FIELDS, IN_CONTRACT_REASON)

    if campaign.status == models.PUBLISHED and _proposal_count(db, campaign_id) > 0:
        _refuse_locked(campaign, data, LOCKED_FIELDS, PRICED_AGAINST_REASON)
    # A published campaign with NO proposals may still change everything, and
    # that is not an oversight. Nobody has relied on those terms yet: the
    # brief is live but no creator has spent an evening pricing it, so fixing
    # a budget with a missing zero costs nobody anything. The lock is about
    # protecting work already done, not about the publish button.

    if data.get("deliverables") is not None:
        # Same catalog check create and publish run: an edit must not be the
        # way a brief ends up asking for something no platform sells.
        service._validate_deliverables(data["deliverables"])

    for field, value in data.items():
        setattr(campaign, field, value)
    db.commit()
    db.refresh(campaign)
    return service._to_out(campaign)


def delete_campaign(db: Session, campaign_id: str, business_user_id: str) -> dict:
    """Erase a draft nobody has seen. Anything else is a cancellation.

    A hard delete is only ever right when there is nothing to lose: a draft
    with no proposals, no invitations and no contract is one person's notes.
    The moment somebody else is attached, deleting would take their proposal,
    their contract or their side of the audit trail with it, and a marketplace
    where one party can erase the record is a marketplace with nothing to
    settle a dispute from.
    """
    campaign = service._require_campaign_owner(db, campaign_id, business_user_id)
    _reject_direct(campaign)

    invitations = _invitations(db, campaign_id)
    if (
        campaign.status != models.DRAFT
        or _proposal_count(db, campaign_id) > 0
        or invitations
        or _contract(db, campaign_id) is not None
    ):
        raise AppError(
            status.HTTP_409_CONFLICT,
            code="campaign_has_activity",
            detail=ACTIVITY_DETAIL,
        )

    # The invitation rows go with it. In practice this set is empty — the
    # guard above refuses a campaign that has any, and inviting requires a
    # published campaign anyway — but the foreign key is real, so a row
    # written by a fixture or a backfill would otherwise turn a clean 409 into
    # an integrity error from the database.
    db.query(models.CampaignInvitation).filter(
        models.CampaignInvitation.campaign_id == campaign_id
    ).delete(synchronize_session=False)
    db.delete(campaign)
    db.commit()
    return {"id": campaign_id, "deleted": True}


def cancel_campaign(db: Session, campaign_id: str, business_user_id: str) -> dict:
    """Call the brief off, and tell the people who were waiting on it.

    Cancelling is the exit that keeps the record. The status changes, nothing
    is removed, and every creator who was invited hears about it — a creator
    holding a brief they are pricing deserves to be told it is dead rather
    than to work out from silence that nobody is coming back.

    IT ALSO CLOSES WHAT WAS OPEN, which it did not before. The status moved and
    the rows underneath it did not: live proposals stayed `submitted` and
    invitations stayed `invited` on a brief that no longer existed, so
    withdraw_invitation refused ("this creator has already sent a proposal")
    against a proposal nobody could ever answer, and contract generation had to
    grow a campaign-status guard of its own to stop a cancelled brief's bids
    being turned into contracts. Ending a campaign now ends what hangs off it,
    through the same code completion uses — one definition of what a terminal
    state closes, rather than two that drift.

    Silently, though. The loop below has just told every invited creator the
    brief is off; the filled-brief notification would be the same news twice.
    """
    campaign = service._require_campaign_owner(db, campaign_id, business_user_id)
    _reject_direct(campaign)

    if _contract(db, campaign_id) is not None:
        # A signed contract is not the campaign's to unwind. Two parties
        # agreed terms, escrow may already be funded against them, and ending
        # that is a question about who is owed what — which is exactly what
        # the dispute and refund path is for, and it has the rules. Cancelling
        # here would leave a live contract hanging off a dead campaign and no
        # record of who decided the work was over.
        raise AppError(
            status.HTTP_409_CONFLICT,
            code="campaign_has_contract",
            detail=CONTRACT_DETAIL,
        )

    if campaign.status == models.CANCELLED:
        # Refused rather than treated as a no-op: cancelling twice would send
        # every invited creator a second "this is off" for something that was
        # already off.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="campaign_already_cancelled",
            detail="This campaign is already cancelled.",
        )

    campaign.status = models.CANCELLED
    # Everyone who was ever invited, including creators who already declined:
    # the notification is about the brief ending, and a creator who said no
    # still asked around and still blocked out a date.
    for invitation in _invitations(db, campaign_id):
        notify(
            db,
            invitation.influencer_user_id,
            "campaign_cancelled",
            f"The campaign {campaign.title} was cancelled by the business.",
            # The creator's invitations list. The brief itself is a brand-side
            # screen, and /campaigns/{id} would be a 403 for the person being
            # told about it.
            link="/invitations",
            params={"key": "campaign_cancelled", "campaign": campaign.title},
        )
    completion.close_open_offers(db, campaign, tell_creators=False)
    db.commit()
    db.refresh(campaign)
    return service._to_out(campaign)

"""The brand's answer that is a no.

`rejected` has been one of a proposal's statuses since the table was written
(models.PROPOSAL_REJECTED) and until recently NOTHING EVER WROTE IT. The
completion cascade closes the chains still open on a brief that filled
(campaigns.completion.close_open_offers) and that was the only path to the
status at all — a side effect of somebody else's deal being paid, never a
decision a buyer made about this bid.

The absence was not neutral, because the rest of the system had already been
built as though the decision existed. submit_proposal refuses to reopen a
rejected chain. The invitation refusal tells a buyer, in as many words, to
"reply to it or reject it" (withdrawals.PRICED_DETAIL). Neither sentence was
true: a brand's only exits from an unwanted bid were countering it forever, or
cancelling the whole brief — and cancelling used to leave every chain under it
live, which was a bug of its own. The workaround for a missing feature was
itself the defect.

REJECTED, NOT WITHDRAWN AND NOT DECLINED. models.py draws the three apart and
this module is the one it defines: rejected is the buyer walking away from a
bid it invited. Withdrawn is the author taking their own offer back before
anybody answered, so no refusal lands on anybody's record; declined is a
creator turning down a purchase. Which of the three a row carries decides
whose record reads as somebody who says no, so they are not interchangeable
even though all three mean "no deal".

ONE VERSION, NOT THE CHAIN. Only the live version's status moves. Every
version above it was already superseded by whoever wrote the row underneath
it, and rewriting those would erase who ended what — the same reasoning
withdraw_proposal gives for not reviving the version below.

NOTHING IS REFUNDED AND NOTHING IS UNWOUND, which is what makes this safe to
do at all: a proposal is an offer, escrow is funded only from a signed
contract, and a chain that has reached a contract is refused below rather than
rejected. There is no money in the system behind the row this closes.

A SEPARATE MODULE from service.py for the reason withdrawals.py and editing.py
are: service.py is already long and is about creating campaigns and running the
negotiation on them, and this has to read contracts — through contracts.models
ONLY, never contracts.service, which imports campaigns.service and would close
the circle. The dependency runs one way: router -> rejections -> service.
"""
from fastapi import status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.identity import creator_identities
from app.modules.campaigns import models, service
from app.modules.contracts import models as contracts
from app.modules.notifications.service import notify

# Where the creator reads this. campaigns.completion sends the other kind of
# bad news to the same place and gives the reason: a creator answers a brief
# from /invitations, and /campaigns/{id} is the brand's screen and a 403 for
# them. Mobile has no route for the path and falls back to the notification
# TYPE, which is why the type below starts with "proposal".
CREATOR_LINK = "/invitations"

# The stored English, which is also what goes out by email.
#
# KIND, AND WITHOUT BLAME. Somebody reading this has just lost work they spent
# an evening pricing, and there is nothing to be gained by telling them why in
# a sentence the brand did not write. It names no campaign for the reason
# `brief_filled` names none: the link opens the creator's own invitations, and
# the row they are looking for is in there.
REJECTED_MESSAGE = "Your proposal was not selected."

# An order is not a brief, and this endpoint would only half-close one.
#
# A direct order is a private transaction between two named parties: the buyer
# already made the offer, so the only answer outstanding is the creator's, and
# decline_direct_order is what gives it — it cancels the hidden campaign, moves
# the invitation and tells the buyer they were not charged. Rejecting the
# creator's counter from here would do none of that: the campaign would stay
# published, the invitation would stay `invited`, and the expiry sweep would
# stop touching the row (it only looks at `submitted` proposals), so an order
# nobody can answer any more would sit in the buyer's list looking live and
# never lapse. Refusing keeps one way to close an order.
DIRECT_ORDER_DETAIL = (
    "This is a direct order, not a bid on a brief. An order ends with the "
    "creator accepting or declining it, not with the buyer rejecting a version "
    "of it."
)

# Said the same way withdraw_proposal says it, because it is the same rule
# reached from the other side of the table.
CONTRACT_DETAIL = (
    "A contract already exists for this proposal. Cancel the contract "
    "instead: POST /contracts/{contract_id}/cancel."
)


def _contract(db: Session, proposal: models.Proposal) -> contracts.Contract | None:
    """Any contract this chain has already produced, signed or not.

    The query withdraw_proposal runs, restated for the other party: a contract
    on this campaign that names either this exact proposal or this creator.
    Both halves are the same fact on a well-formed chain — a contract names the
    accepted version, and a creator has one chain per campaign — and the second
    is what still finds it when the contract was written from an earlier
    version than the one being named here.

    PENDING COUNTS, exactly as it does in editing._contract and
    orders._campaign_has_contract: a contract that exists was generated from
    agreed terms and is sitting in front of two people to sign, so what is on
    the table is no longer a bid anybody may reject.
    """
    return (
        db.query(contracts.Contract)
        .filter(
            contracts.Contract.campaign_id == proposal.campaign_id,
            or_(
                contracts.Contract.proposal_id == proposal.id,
                contracts.Contract.influencer_user_id == proposal.influencer_user_id,
            ),
        )
        .first()
    )


def reject_proposal(
    db: Session, campaign_id: str, proposal_id: str, business_user_id: str
) -> dict:
    """The brand turns down the live offer in one creator's chain.

    The campaign's author and nobody else, on a published brief, against the
    live submitted version, and only while nothing has been contracted from it.
    The creator is told.

    IRREVERSIBLE FOR THAT CHAIN, which is why the client confirms first.
    `rejected` is one of the three terminal resolutions submit_proposal already
    refuses to reopen, so this creator cannot come back with a new version on
    this brief. That is the intended shape — a rejection the bidder can simply
    undo by bidding again is not a decision — and it is the reason the
    contract guard below matters more than it looks: this is a door that does
    not open again.

    WHY THE STATUS TEST IS THE WHOLE OF "THE LATEST VERSION, AND SUBMITTED".
    Only one row in a chain is ever `submitted`, and it is always the highest
    version: both writers of a proposal row supersede what they answer
    (service.submit_proposal and service.reply_to_proposal each set the version
    they are answering to SUPERSEDED before adding their own, numbered off it).
    So `proposal.status == SUBMITTED` and `proposal is latest_in_chain(...)`
    are the same question asked twice, and asking it once is not a shortcut
    past the rule — it is the rule, written where it can be read.

    ONE CODE FOR EVERY WAY THAT TEST CAN FAIL. `proposal_closed` is the code
    reply_to_proposal already refuses a settled chain with, and its sentence —
    "this proposal is closed and cannot be answered" — is true of every case
    that lands here: a superseded version, a chain that was accepted,
    withdrawn, declined, or rejected once already. Rejecting IS answering, so
    it is the same rule and it keeps the same name. Splitting it would tell a
    caller which of the five it hit, which is of use to nobody.

    NOT `proposal_not_live`, which names the same test on the creator's side:
    its French and English sentences both end by saying there is nothing left
    to WITHDRAW, and shipping that to a brand pressing Reject would be a
    refusal that describes somebody else's action.
    """
    campaign = service._require_campaign_owner(db, campaign_id, business_user_id)
    if campaign.status != models.PUBLISHED:
        # campaign_not_open, the code submit_proposal and reply_to_proposal
        # both refuse with: one rule — this campaign is not in a state that
        # takes decisions on proposals — and a rejection is one. A cancelled
        # or completed brief has already had its open chains closed by
        # completion.close_open_offers, so there is nothing left here to
        # reject and a second closing would notify the creator twice.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="campaign_not_open",
            detail="Campaign is not open for proposals",
        )
    if campaign.is_direct:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="proposal_is_direct_order",
            detail=DIRECT_ORDER_DETAIL,
        )

    proposal = (
        db.query(models.Proposal)
        .filter(
            models.Proposal.id == proposal_id,
            models.Proposal.campaign_id == campaign_id,
        )
        .first()
    )
    if proposal is None:
        # Scoped to the campaign in the path, so a proposal id lifted from
        # somebody else's brief is not found rather than found and refused.
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="proposal_not_found",
            detail="Proposal not found",
        )

    # Before the live check, and deliberately in that order. A chain that
    # reached a contract also has an accepted version, so both guards would
    # refuse it — but only one of them says what actually happened. "There is a
    # contract, cancel that instead" is somewhere to go; "this is not the live
    # offer" is a true sentence that leaves the buyer looking for the reason.
    if _contract(db, proposal) is not None:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="proposal_has_contract",
            detail=CONTRACT_DETAIL,
        )

    if proposal.status != models.SUBMITTED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="proposal_closed",
            detail="This proposal is closed and cannot be answered",
        )

    proposal.status = models.PROPOSAL_REJECTED
    notify(
        db,
        proposal.influencer_user_id,
        # The same type completion.close_open_offers writes for the other way
        # a creator's live proposal ends, and for the same two reasons: it
        # starts with "proposal", which is what routes the row to the
        # creator's invitations on a client that cannot parse the link, and a
        # creator who has muted one kind of "your proposal is closed" has
        # muted the other on purpose.
        "proposal_closed",
        REJECTED_MESSAGE,
        link=CREATOR_LINK,
        params={"key": "proposal_rejected"},
    )
    db.commit()
    db.refresh(proposal)
    identity = creator_identities(db, [proposal.influencer_user_id]).get(
        proposal.influencer_user_id
    )
    return service._proposal_out(proposal, identity)

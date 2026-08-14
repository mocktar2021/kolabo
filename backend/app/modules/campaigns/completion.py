"""When a brief is over, and what being over closes.

A campaign used to have no ending. It was published, and it stayed published:
the money underneath it finished, the contracts settled, and the brief went on
looking live — still on the board, still taking proposals, still inviting
creators to price work that had already been done and paid for. The web client
papered over it by DERIVING an ending for its Active/Completed shelves
(web/src/lib/lifecycle.ts), which is right for a shelf and cannot be right for
a rule: a shelf decides what a list looks like, and the things that were still
wrong here — a bid arriving on a filled brief, an invitation going out from
one — are decisions the server makes.

So `completed` is a real status now, and THE RULE IS THE CLIENT'S RULE, moved
rather than reinvented. lifecycle.ts is the source; the constants and the two
halves of the predicate below are its ENDED_CONTRACT_STATUSES,
SETTLED_ESCROW_STATUSES and campaignIsCompleted, reproduced condition for
condition so the two cannot answer differently about the same campaign.

ONE THING IS DELIBERATELY NOT REPRODUCED. campaignIsCompleted's first line is
`if (campaign.status === CANCELLED) return true` — a cancelled brief is filed
on the Completed shelf, because a creator looking for it will not look under
Active. That is a statement about which tab a row is drawn in, not about what
the row IS, and applying it here would rewrite `cancelled` to `completed` and
destroy the difference between a brief that finished and one that was called
off. The stored status stays what it was; only a PUBLISHED campaign is ever
moved, and only by the second half of the client's rule.

WHY ITS OWN MODULE. It reads contracts and escrows, which campaigns.service
may not: contracts.service imports campaigns.service (it re-reads the live
version of a chain before writing a contract), so a function in
campaigns.service that reached for contracts would close that circle. The same
reasoning already split orders.py, editing.py, board.py and withdrawals.py off
this module. Everything here goes through contracts.models and payments.models
— MODELS ONLY, never either service — so the graph stays one-way and this file
can be called from inside both of them.
"""
from sqlalchemy.orm import Session

from app.modules.campaigns import models
from app.modules.contracts import models as contracts
from app.modules.notifications.service import notify
from app.modules.payments import models as payments

# An ending the CONTRACT itself reached, from lifecycle.ts. `void` has never
# been written by any code path; it is listed for the reason the client lists
# it — it means a contract that was never valid, which is an ending, and it is
# better named here than silently treated as live if it ever starts being used.
ENDED_CONTRACT_STATUSES = (contracts.CANCELLED, contracts.VOID)

# An ending the MONEY reached. `held` and `disputed` are deliberately absent:
# held money is a job still running and disputed money is a job actively going
# wrong, and a brief whose only escrow is frozen has not finished.
SETTLED_ESCROW_STATUSES = (payments.RELEASED, payments.REFUNDED)

# Where the creator reads this. The same destination cancel_campaign sends its
# own bad news to, and for the same reason: a creator answers a brief from
# /invitations, and /campaigns/{id} is the brand's screen and a 403 for them.
# Mobile has no route for the path and falls back to the type, which is why the
# type starts with "proposal" — see notifications.ts on both clients.
CREATOR_LINK = "/invitations"


def _contract_endings(db: Session, campaign_id: str) -> list[tuple[str, str | None]]:
    """Every contract on the campaign as (contract status, escrow status).

    The escrow status is the field the client's rule is written against —
    contracts.service.list_my_contracts hands it to the browser the same way —
    and it is NULL when nobody has funded the contract yet, which is a live
    state and not an ending. One outer join rather than a query per contract:
    Escrow.contract_id is unique, so a contract has at most one escrow and the
    join cannot multiply the rows.
    """
    return (
        db.query(contracts.Contract.status, payments.Escrow.status)
        .outerjoin(payments.Escrow, payments.Escrow.contract_id == contracts.Contract.id)
        .filter(contracts.Contract.campaign_id == campaign_id)
        .all()
    )


def _contract_is_completed(contract_status: str, escrow_status: str | None) -> bool:
    """lifecycle.ts's contractIsCompleted, over the same two facts."""
    if contract_status in ENDED_CONTRACT_STATUSES:
        return True
    return escrow_status is not None and escrow_status in SETTLED_ESCROW_STATUSES


def campaign_is_completed(db: Session, campaign_id: str) -> bool:
    """lifecycle.ts's campaignIsCompleted, minus the cancelled shelf rule.

    BOTH HALVES ARE NEEDED, and the second is the one that is easy to drop.
    Every contract on the brief must have reached an ending — one creator still
    delivering keeps the whole thing live — AND at least one of those endings
    must have been a MONEY ending. Without the second half a brief whose only
    deal fell through before anyone funded it would be filed as finished, when
    what it actually is is an open brief still taking proposals: nothing was
    completed there, something was abandoned, and the brand can still work it.

    A campaign with no contracts at all is never complete, which is right for a
    published brief nobody has bid on yet as well as for a draft: in both cases
    the brand still has something to do.
    """
    endings = _contract_endings(db, campaign_id)
    if not endings:
        return False
    if not all(_contract_is_completed(c, e) for c, e in endings):
        return False
    return any(e is not None and e in SETTLED_ESCROW_STATUSES for _c, e in endings)


def _live_versions(db: Session, campaign_id: str) -> list[models.Proposal]:
    """The current offer in each negotiation on this campaign, one per creator.

    The same row service.latest_in_chain returns, for every chain at once
    rather than one at a time: highest version wins, whichever side authored
    it. Read ascending so the last row seen per creator is the live one. A
    campaign's chains are a handful of rows and are already read whole
    elsewhere in this module, so this is a list rather than a correlated
    subquery.
    """
    live: dict[str, models.Proposal] = {}
    rows = (
        db.query(models.Proposal)
        .filter(models.Proposal.campaign_id == campaign_id)
        .order_by(models.Proposal.version)
        .all()
    )
    for proposal in rows:
        live[proposal.influencer_user_id] = proposal
    return list(live.values())


def close_open_offers(db: Session, campaign: models.Campaign, *, tell_creators: bool) -> None:
    """Everything still waiting on a decision this campaign will never make.

    Called when a campaign enters EITHER terminal state, because the data
    problem is the same one in both: a brief that ended with live chains and
    open invitations hanging off it leaves creators holding offers that can no
    longer be accepted, and leaves rows the rest of the system reads as live —
    withdraw_invitation refuses because a proposal exists, submit_proposal is
    the only thing standing between a dead brief and a new bid.

    REJECTED, NOT WITHDRAWN, for a closed chain. models.WITHDRAWN means the
    author took their own offer back, and the creator did no such thing —
    recording it that way would put an act on their record they never
    performed. Rejected is the buyer walking away from a bid it invited, which
    is what completing a brief with somebody else is, and it is one of the
    three terminal resolutions submit_proposal already refuses to reopen. The
    invitation goes the other way for the mirror-image reason: nobody declined
    it, so it is withdrawn exactly as withdraw_invitation would have written it.

    tell_creators is FALSE on the cancellation path, and that is not an
    oversight. cancel_campaign has already told every invited creator the brief
    is off; a second message saying their proposal is closed is the same news
    twice from a system that just sent it. Completion has said nothing yet, so
    there it is the only message the creator gets.
    """
    for proposal in _live_versions(db, campaign.id):
        if proposal.status != models.SUBMITTED:
            continue
        proposal.status = models.PROPOSAL_REJECTED
        if tell_creators:
            notify(
                db,
                proposal.influencer_user_id,
                # Starts with "proposal" on purpose: it is what routes this row
                # to the creator's invitations on mobile, which reads the type
                # when it cannot parse the link.
                "proposal_closed",
                "This brief has been filled, so your proposal is now closed.",
                link=CREATOR_LINK,
                params={"key": "brief_filled"},
            )
    for invitation in (
        db.query(models.CampaignInvitation)
        .filter(
            models.CampaignInvitation.campaign_id == campaign.id,
            models.CampaignInvitation.status == models.INVITED,
        )
        .all()
    ):
        invitation.status = models.WITHDRAWN


def maybe_complete_campaign(db: Session, campaign_id: str) -> bool:
    """Finish the campaign if the work under it has finished. Idempotent.

    Called from every place a contract or its escrow reaches an ending, AFTER
    that ending has been committed — never before. The order is the whole
    safety property: if the ending rolls back this was never called, and if
    this call fails the ending still stands and the next ending (or the next
    call from the same place) completes the campaign instead. A campaign that
    is late to be marked complete is a display fault; a campaign marked
    complete off a payment that rolled back is a brief closed for nothing.
    Returns whether it moved, which the tests read and no caller needs.

    Silent on a campaign that is not there. Contracts carry a campaign_id and
    nothing enforces that a row exists behind it, so a caller deep in the
    payment path must not turn a successful release into a 500 over a brief
    that was never written.

    PUBLISHED ONLY. A campaign already `completed` is done (this is what makes
    the call safe to repeat), a `cancelled` one ended a different way and must
    keep saying so, and a draft has shown nobody anything — none of the three
    is a state this should move.
    """
    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if campaign is None or campaign.status != models.PUBLISHED:
        return False
    if not campaign_is_completed(db, campaign_id):
        return False

    campaign.status = models.COMPLETED
    close_open_offers(db, campaign, tell_creators=True)
    # Its own commit, because its callers have already made theirs: this runs
    # after the ending is durable, so there is nothing of theirs left in the
    # session for this to sweep up.
    db.commit()
    return True

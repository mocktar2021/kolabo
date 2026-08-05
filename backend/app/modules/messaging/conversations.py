"""One conversation per person, however many jobs you have done together.

THE PROBLEM THIS FIXES. Threads were keyed by CONTRACT, because that is what
unlocks messaging and it was the obvious key at the time. It is the wrong one.
A creator who works with the same brand three times got three inboxes: three
rows in the list with the same name on them, three places to look for "what
did they say about the deadline last time", and a history that fragments
further with every job. That is exactly backwards — the relationship gets more
valuable each time it repeats, and the product was chopping it up in response.
It also makes the good case look like the confusing case, so the creators
with the strongest repeat business had the worst inbox.

So the row is a PERSON, and the contracts are an attribute of it. A thread
carries contract_ids (newest first) and contract_count, because "we have done
four jobs together" is a fact about a relationship worth showing, and because
a client that wants to link to a specific job still can.

WHAT DOES NOT CHANGE, AND WHY.

  * THE GATE. A conversation still requires at least one contract between the
    two people. Everything in service.py's docstring about why still holds:
    open messaging is a lead channel people mine and abandon, and a
    conversation that starts before a deal is a conversation that leaves for
    WhatsApp, where there is no contract, no escrow and no recourse. The only
    change is that the gate now asks "is there a contract between us" instead
    of "is there a contract between us ON THIS CAMPAIGN", which is the same
    question one scope wider.

  * THE CONTACT GUARD. Addressing a person rather than a campaign changes
    nothing about what may travel: send_to runs the same
    app.core.contact_guard check as the per-campaign send, for the same
    reason. Two ways to write a message must not mean one way to write a
    phone number — a guard with a hole in it is worse than none, because it
    looks finished.

  * campaign_id STAYS ON THE MESSAGE ROW. It would have been tidy to drop it
    now that messages are addressed by person, and it would have thrown away
    history: every message ever sent knows which job it was about, and that
    provenance is what a dispute reads when the argument is about when a
    revision was asked for. A message sent through the counterparty endpoint
    is stamped with the MOST RECENT shared contract's campaign, which is the
    honest guess — people talk about the job they are currently doing — and it
    is a record of context, not an authorisation. Nothing reads it to decide
    who may see what; the contract does that.

  * THE PER-CAMPAIGN ENDPOINTS KEEP WORKING. They are what the web app calls
    today, they are still the precise way to address one job's thread, and
    breaking them to prove a point about grouping would be a migration for no
    user's benefit. The thread row also still carries campaign_id,
    campaign_title and contract_id for the newest shared contract, so a client
    written against the old shape keeps rendering.

A separate module from service.py, which keeps the per-campaign send and read
and the gate helpers both of them use. The dependency runs one way — router ->
conversations -> service — and there is still exactly one answer to "may these
two people talk", which is what service._contract_between asks.
"""
from fastapi import status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.contact_guard import check_no_contact_details
from app.core.identity import creator_identities
from app.modules.campaigns import models as campaigns
from app.modules.contracts import models as contracts
from app.modules.messaging.models import Message, utcnow
from app.modules.messaging.service import _out
from app.modules.notifications.service import notify
from app.modules.profiles.models import BusinessProfile

# The counterparty-scoped version of service.GATE_DETAIL. Worded for the wider
# question this gate asks: not "not on this campaign" but "not with this
# person, on anything".
GATE_DETAIL = (
    "Messaging opens when a contract does. There is no contract between you and "
    "this person."
)


def contracts_between(db: Session, user_id: str, other_user_id: str) -> list:
    """Every contract that puts these two people on a job, newest first.

    Matched in either direction because the PAIR is what matters, not which of
    them is buying — the same reason service._contract_between does. The
    difference is that this returns all of them rather than the first one
    found, which is the whole change: one contract answers "may they talk",
    all of them answer "what have they done together".
    """
    return (
        db.query(contracts.Contract)
        .filter(
            or_(
                and_(
                    contracts.Contract.business_user_id == user_id,
                    contracts.Contract.influencer_user_id == other_user_id,
                ),
                and_(
                    contracts.Contract.business_user_id == other_user_id,
                    contracts.Contract.influencer_user_id == user_id,
                ),
            )
        )
        .order_by(contracts.Contract.created_at.desc())
        .all()
    )


def _require_contracts(db: Session, user_id: str, other_user_id: str) -> list:
    shared = contracts_between(db, user_id, other_user_id)
    if not shared:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="message_gate",
            detail=GATE_DETAIL,
        )
    return shared


def _pair_messages(db: Session, campaign_ids, user_id: str, other_user_id: str) -> list[Message]:
    """The two people's messages across a set of campaigns, oldest first.

    Filtered to the PAIR after the campaign filter, not instead of it. A brief
    with three accepted creators carries three conversations on one campaign,
    and without the pair test a brand's message to one of them would appear in
    another's thread.
    """
    if not campaign_ids:
        return []
    pair = {user_id, other_user_id}
    rows = (
        db.query(Message)
        .filter(Message.campaign_id.in_(campaign_ids))
        .order_by(Message.created_at.asc())
        .all()
    )
    return [m for m in rows if {m.sender_user_id, m.recipient_user_id} == pair]


def list_threads(db: Session, user_id: str) -> list[dict]:
    """The caller's inbox: one row per PERSON they have a contract with.

    Built from contracts rather than from messages, unchanged and for the
    unchanged reason: a thread nobody has written in yet still has to appear,
    because it is the one somebody needs to start.

    What changed is the grouping. Contracts are collapsed by counterparty, so
    a brand and a creator on their fourth job together have ONE row with four
    contract ids on it instead of four rows with the same name. Ordered by the
    newest contract in each relationship, so somebody just signed with appears
    at the top even with an empty thread — which is exactly when it is empty.

    Identity is resolved in bulk and from the shared sources: creators through
    app.core.identity so the inbox names a creator exactly as their proposal
    did, businesses through their company name, which is the only public
    identity a buyer has.
    """
    my_contracts = (
        db.query(contracts.Contract)
        .filter(
            or_(
                contracts.Contract.business_user_id == user_id,
                contracts.Contract.influencer_user_id == user_id,
            )
        )
        .order_by(contracts.Contract.created_at.desc())
        .all()
    )
    if not my_contracts:
        return []

    # Insertion order is contract order, which is already newest first, so the
    # dict preserves both the row order and each relationship's contract order
    # without a second sort.
    by_counterparty: dict[str, list] = {}
    for contract in my_contracts:
        counterparty = (
            contract.influencer_user_id
            if contract.business_user_id == user_id
            else contract.business_user_id
        )
        by_counterparty.setdefault(counterparty, []).append(contract)

    campaign_ids = {c.campaign_id for c in my_contracts}
    titles = {
        c.id: c.title
        for c in db.query(campaigns.Campaign)
        .filter(campaigns.Campaign.id.in_(campaign_ids))
        .all()
    }
    # Every message on every campaign the caller has a contract on, in one
    # query rather than one per thread: an inbox with twenty conversations is
    # otherwise twenty extra round trips before the screen can render.
    messages = (
        db.query(Message)
        .filter(Message.campaign_id.in_(campaign_ids))
        .order_by(Message.created_at.asc())
        .all()
    )

    creator_counterparties = [
        c.influencer_user_id for c in my_contracts if c.business_user_id == user_id
    ]
    identities = creator_identities(db, creator_counterparties)
    business_counterparties = {
        c.business_user_id for c in my_contracts if c.influencer_user_id == user_id
    }
    company_names: dict[str, str] = {}
    if business_counterparties:
        company_names = {
            p.user_id: p.company_name
            for p in db.query(BusinessProfile)
            .filter(BusinessProfile.user_id.in_(business_counterparties))
            .all()
        }

    threads = []
    for counterparty, shared in by_counterparty.items():
        pair = {user_id, counterparty}
        shared_campaigns = {c.campaign_id for c in shared}
        conversation = [
            m
            for m in messages
            if m.campaign_id in shared_campaigns
            and {m.sender_user_id, m.recipient_user_id} == pair
        ]
        last = conversation[-1] if conversation else None
        identity = identities.get(counterparty)
        newest = shared[0]
        threads.append(
            {
                "counterparty_user_id": counterparty,
                "counterparty_name": (
                    identity["display_name"] if identity else company_names.get(counterparty)
                ),
                "counterparty_avatar_url": identity["avatar_url"] if identity else None,
                # Every job with this person, newest first, and how many.
                # "We have done four together" is a fact about a relationship
                # worth putting on the row.
                "contract_ids": [c.id for c in shared],
                "contract_count": len(shared),
                # The newest shared contract, spelled out. Kept so a client
                # written against the old per-contract shape keeps rendering,
                # and because "the job we are currently on" is what a header
                # wants to name anyway.
                "contract_id": newest.id,
                "campaign_id": newest.campaign_id,
                "campaign_title": titles.get(newest.campaign_id),
                "last_message": last.body if last else None,
                "last_message_at": last.created_at if last else None,
                # Unread is always about what was sent TO the caller, and now
                # across the whole relationship rather than one job: an
                # unanswered question is unanswered whichever contract it was
                # asked under.
                "unread_count": sum(
                    1
                    for m in conversation
                    if m.recipient_user_id == user_id and m.read_at is None
                ),
            }
        )
    return threads


def get_conversation(db: Session, user_id: str, other_user_id: str) -> list[dict]:
    """Everything the two of them have said, across every job, oldest first.

    One conversation rather than one per contract, which is the point: a
    question asked during the second job and answered during the third reads
    as a conversation here and read as two disconnected threads before.

    Opening it IS reading it, exactly as the per-campaign endpoint works and
    for the same reason — there is no moment a user has the thread on screen
    and has not read it. Only INCOMING messages are stamped; stamping their
    own would make read_at meaningless in a dispute, where the question is
    always when the OTHER person saw something.
    """
    shared = _require_contracts(db, user_id, other_user_id)
    thread = _pair_messages(db, {c.campaign_id for c in shared}, user_id, other_user_id)

    now = utcnow()
    for m in thread:
        if m.recipient_user_id == user_id and m.read_at is None:
            m.read_at = now
    # Built before the commit so the response carries the stamp that was just
    # written, without a second round trip to reload the rows.
    out = [_out(m) for m in thread]
    db.commit()
    return out


def send_to(db: Session, sender_id: str, to_user_id: str, body: str) -> dict:
    """Write to a person rather than to a campaign.

    The gate is the only authorisation, as it is on the per-campaign endpoint:
    a contract names exactly two people, so "is there a contract between us"
    answers who the parties are as well as whether they may talk.

    The message is stamped with the NEWEST shared contract's campaign. It has
    to be stamped with something — campaign_id is NOT NULL and, more to the
    point, is worth keeping — and the newest job is the honest guess about
    what two people are discussing right now. Nothing authorises off that
    value; it is provenance, and the contract is what decides access. The
    alternative, making the column nullable, would have traded a slightly
    wrong answer for no answer at all on every message sent from here.
    """
    if sender_id == to_user_id:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="message_self",
            detail="Choose a different recipient"
        )

    shared = _require_contracts(db, sender_id, to_user_id)

    # The same rule as the per-campaign send, deliberately not a different
    # one: swapping contact details is how a deal leaves Kolabo with the
    # escrow and the fee, and two endpoints that write the same table must not
    # disagree about what may go into it. A guard wired to one of two send
    # paths is worse than no guard, because it looks finished. See
    # service.send_message for the rule in full, including why it is friction
    # rather than prevention and why nothing is ever silently redacted.
    check_no_contact_details(body, "message")

    newest = shared[0]

    message = Message(
        campaign_id=newest.campaign_id,
        sender_user_id=sender_id,
        recipient_user_id=to_user_id,
        body=body,
    )
    db.add(message)
    campaign = (
        db.query(campaigns.Campaign)
        .filter(campaigns.Campaign.id == newest.campaign_id)
        .first()
    )
    title = campaign.title if campaign is not None else None
    notify(
        db,
        to_user_id,
        "message",
        f"New message about the campaign {title}" if title else "You have a new message",
        link=f"/messages?campaign={newest.campaign_id}&with={sender_id}",
        params=({"key": "message_campaign", "campaign": title} if title else {"key": "message_generic"}),
    )
    db.commit()
    db.refresh(message)
    return _out(message)

"""Messaging business logic (Epic F, KOL-26).

WHEN A THREAD OPENS, AND WHY NOT SOONER.

A thread exists on a campaign ONLY once a contract exists on that campaign
between the two people in it. Not an invitation. Not a proposal. A contract.

Open messaging between any brand and any creator is a lead channel, and a lead
channel is a thing people mine: a hundred identical "hi, what are your rates"
messages, most of them answered by nobody, until both sides learn that the
inbox is noise and stop opening it. The creators who suffer most are the ones
with the biggest audiences, which is to say the ones the marketplace most
needs to keep. And a conversation that starts before there is a deal is a
conversation that leaves for WhatsApp the moment it gets specific — a deal
agreed there has no contract, no escrow and no recourse for either side, which
is the single failure this whole codebase is arranged to prevent.

Messaging AFTER a contract is a different product. Two people have agreed
terms and now have work to do together: shot lists, delivery dates, revisions,
"the light was wrong, can I reshoot Thursday". That conversation has to happen
somewhere, and by then the platform has taken its fee, so it can afford to
carry it. The thread also becomes the evidence trail a dispute needs — when a
delivery was promised, when a revision was asked for, when it went quiet —
which is why read_at is a timestamp and not a flag.

WHO MAY READ. Both parties to the contract, and nobody else. That includes an
admin: there is deliberately no admin path into a thread in this module.
Reading two parties' private working conversation is a real privacy cost, and
the dispute flow already gets what it needs by asking the parties to submit
it. If moderation ever genuinely needs access it should arrive as an explicit,
audited endpoint in trust_safety — something a user could be told about — and
not as a quiet exception inside this gate.

The gate replaces the old invitation-or-proposal rule, which is why the
relationship helper that backed it is gone rather than kept alongside: two
answers to "may these people talk" is one answer too many.
"""
from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.identity import creator_identities
from app.modules.campaigns import models as campaigns
from app.modules.contracts import models as contracts
from app.modules.messaging.models import Message, utcnow
from app.modules.notifications.service import notify
from app.modules.profiles.models import BusinessProfile

# Said the same way whether somebody tried to write or to read: the reason is
# identical, and it names the thing that would unlock it.
GATE_DETAIL = (
    "Messaging opens when a contract does. There is no contract on this campaign "
    "between you and this person."
)


def _contract_between(db: Session, campaign_id: str, user_id: str, other_user_id: str):
    """The contract that puts these two people on the same job, if there is one.

    Matched in either direction because the pair is what matters, not which of
    them is buying. A campaign can carry several contracts — a brief with three
    accepted creators has three — and each one opens exactly one thread, so the
    creators on one brief still cannot read each other.

    A pending contract counts. It has already been generated from agreed terms
    and both parties are looking at it; making them wait for the second
    signature to ask a question about the thing they are signing would push
    that question straight to WhatsApp.
    """
    return (
        db.query(contracts.Contract)
        .filter(
            contracts.Contract.campaign_id == campaign_id,
            or_(
                and_(
                    contracts.Contract.business_user_id == user_id,
                    contracts.Contract.influencer_user_id == other_user_id,
                ),
                and_(
                    contracts.Contract.business_user_id == other_user_id,
                    contracts.Contract.influencer_user_id == user_id,
                ),
            ),
        )
        .first()
    )


def _require_contract(db: Session, campaign_id: str, user_id: str, other_user_id: str):
    contract = _contract_between(db, campaign_id, user_id, other_user_id)
    if contract is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=GATE_DETAIL)
    return contract


def _out(m: Message) -> dict:
    return {
        "id": m.id,
        "campaign_id": m.campaign_id,
        "sender_user_id": m.sender_user_id,
        "recipient_user_id": m.recipient_user_id,
        "body": m.body,
        "created_at": m.created_at,
        "read_at": m.read_at,
    }


def send_message(db: Session, campaign_id: str, sender_id: str, to_user_id: str, body: str) -> dict:
    campaign = db.query(campaigns.Campaign).filter(campaigns.Campaign.id == campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if sender_id == to_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Choose a different recipient"
        )

    # The only authorisation there is. It answers who the parties are as well
    # as whether they may talk, so no separate owner-or-influencer check is
    # needed: a contract names exactly two people.
    _require_contract(db, campaign_id, sender_id, to_user_id)

    message = Message(
        campaign_id=campaign_id, sender_user_id=sender_id, recipient_user_id=to_user_id, body=body
    )
    db.add(message)
    notify(db, to_user_id, "message", f"New message about the campaign {campaign.title}")
    db.commit()
    db.refresh(message)
    return _out(message)


def get_thread(db: Session, campaign_id: str, user_id: str, with_user_id: str) -> list[dict]:
    """Read one conversation, and mark what it contained as read.

    Opening the thread IS reading it. There is no separate mark-as-read call
    because there is no moment a user has the thread on screen and has not
    read it — unlike a notification, which can sit in a bell menu unopened.

    Only the caller's INCOMING messages are stamped. Stamping their own would
    make read_at meaningless in a dispute, where the question is always when
    the other person saw something.
    """
    _require_contract(db, campaign_id, user_id, with_user_id)

    pair = {user_id, with_user_id}
    rows = (
        db.query(Message)
        .filter(Message.campaign_id == campaign_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    thread = [m for m in rows if {m.sender_user_id, m.recipient_user_id} == pair]

    now = utcnow()
    for m in thread:
        if m.recipient_user_id == user_id and m.read_at is None:
            m.read_at = now
    # Built before the commit so the response carries the stamp that was just
    # written, without a second round trip to reload the rows.
    out = [_out(m) for m in thread]
    db.commit()
    return out


def list_threads(db: Session, user_id: str) -> list[dict]:
    """The caller's inbox: one row per conversation they are allowed to have.

    Built from CONTRACTS rather than from messages, which is the point. A
    thread that nobody has written in yet still has to appear — it is the one
    somebody needs to start — and a thread exists exactly when a contract
    does, so the contracts are the list.

    One row per contract, not strictly per campaign: a brief with three
    accepted creators is three conversations, and collapsing them into one row
    would lose the only thing that tells them apart, which is who is in them.
    For the ordinary case (an order, a brief with one creator) the two are the
    same thing.

    Ordered by contract, newest first, rather than by last message. A brand
    that just signed with somebody should find that conversation at the top
    even though it is empty, which is precisely when it is empty.

    Identity is resolved in bulk and from the shared source: creators through
    app.core.identity.creator_identities so the inbox names a creator exactly
    as their proposal did, and businesses through their company name, which is
    the only public identity a buyer has.
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

    campaign_ids = {c.campaign_id for c in my_contracts}
    titles = {
        c.id: c.title
        for c in db.query(campaigns.Campaign)
        .filter(campaigns.Campaign.id.in_(campaign_ids))
        .all()
    }
    # Every message on every one of those campaigns, in one query rather than
    # one per thread: an inbox with twenty conversations is otherwise twenty
    # extra round trips before the screen can render.
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
    for contract in my_contracts:
        counterparty = (
            contract.influencer_user_id
            if contract.business_user_id == user_id
            else contract.business_user_id
        )
        pair = {user_id, counterparty}
        conversation = [
            m
            for m in messages
            if m.campaign_id == contract.campaign_id
            and {m.sender_user_id, m.recipient_user_id} == pair
        ]
        last = conversation[-1] if conversation else None
        identity = identities.get(counterparty)
        threads.append(
            {
                "campaign_id": contract.campaign_id,
                "campaign_title": titles.get(contract.campaign_id),
                "contract_id": contract.id,
                "counterparty_user_id": counterparty,
                "counterparty_name": (
                    identity["display_name"] if identity else company_names.get(counterparty)
                ),
                "counterparty_avatar_url": identity["avatar_url"] if identity else None,
                "last_message": last.body if last else None,
                "last_message_at": last.created_at if last else None,
                # Unread is always about what was sent TO the caller. Their own
                # outgoing messages are never unread to them.
                "unread_count": sum(
                    1
                    for m in conversation
                    if m.recipient_user_id == user_id and m.read_at is None
                ),
            }
        )
    return threads

"""Messaging business logic (Epic F, KOL-26).

WHEN A THREAD OPENS, AND WHY NOT SOONER.

A thread exists between two people ONLY once a contract exists between them.
Not an invitation. Not a proposal. A contract.

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

AND WHAT MAY NOT TRAVEL THROUGH IT. The gate keeps the conversation from
starting too early; app.core.contact_guard keeps it from being moved somewhere
else once it has. A message carrying a phone number, an email address or a
handle is refused rather than edited — see the comment at the check in
send_message for the rule and for the honest limits of it.

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

WHAT LIVES HERE AND WHAT LIVES NEXT DOOR. This file owns the PER-CAMPAIGN
send and read — one job's thread, addressed by the campaign it hangs off — and
the gate helpers. Addressing a COUNTERPARTY instead, and the inbox that groups
by person rather than by contract, live in messaging.conversations, which
calls the same gate and the same contact guard. Both are kept: the
per-campaign pair is what the web app calls and is still the precise way to
reach one job's thread.
"""
from fastapi import status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.contact_guard import check_no_contact_details
from app.modules.campaigns import models as campaigns
from app.modules.contracts import models as contracts
from app.modules.messaging.models import Message, utcnow
from app.modules.notifications.service import notify

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
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="message_gate",
            detail=GATE_DETAIL,
        )
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
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="campaign_not_found",
            detail="Campaign not found",
        )
    if sender_id == to_user_id:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="message_self",
            detail="Choose a different recipient"
        )

    # The only authorisation there is. It answers who the parties are as well
    # as whether they may talk, so no separate owner-or-influencer check is
    # needed: a contract names exactly two people.
    _require_contract(db, campaign_id, sender_id, to_user_id)

    # THE PRODUCT RULE. Swapping a phone number or an email is how a deal
    # leaves Kolabo, and it takes the contract, the escrow and the fee with it:
    # what the two of them agree afterwards has nothing behind it if it goes
    # wrong. This is the last free-text field in the flow, so it is the last
    # place to say so.
    #
    # It is FRICTION, NOT PREVENTION, and that is the honest claim. Anyone set
    # on passing a number can spell it out in words or split it over two
    # messages. What this stops is the habit — "here's my number, call me" —
    # which is most of them.
    #
    # After the gate, so authorisation still answers first and a stranger
    # learns nothing about a thread they cannot see. Before the row is
    # written, so a refusal saves nothing. Never a redaction: an altered
    # message is worse than a refused one, because the sender believes they
    # said something they did not say.
    check_no_contact_details(body, "message")

    message = Message(
        campaign_id=campaign_id, sender_user_id=sender_id, recipient_user_id=to_user_id, body=body
    )
    db.add(message)
    notify(db, to_user_id, "message", f"New message about the campaign {campaign.title}",
           link=f"/messages?campaign={campaign_id}&with={sender_id}",
           params={"key": "message_campaign", "campaign": campaign.title})
    db.commit()
    db.refresh(message)
    return _out(message)


def get_thread(db: Session, campaign_id: str, user_id: str, with_user_id: str) -> list[dict]:
    """Read one campaign's conversation, and mark what it contained as read.

    Opening the thread IS reading it. There is no separate mark-as-read call
    because there is no moment a user has the thread on screen and has not
    read it — unlike a notification, which can sit in a bell menu unopened.

    Only the caller's INCOMING messages are stamped. Stamping their own would
    make read_at meaningless in a dispute, where the question is always when
    the other person saw something.

    Scoped to one campaign, deliberately. The whole relationship reads through
    messaging.conversations.get_conversation; this stays the way to look at
    one job on its own, which is what a contract page wants.
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

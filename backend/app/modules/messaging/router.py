"""Epic F (KOL-6): Messaging and Notifications."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import get_current_user_id
from app.modules.messaging import conversations, schemas, service

router = APIRouter()


@router.get("/threads", response_model=list[schemas.ThreadOut])
def my_threads(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """The caller's inbox: ONE row per counterparty, newest relationship first.

    Each row names the OTHER party — a creator by display name, a business by
    company name — with the last message, when it arrived, how many are still
    unread, and every contract between the two (newest first) plus a count.

    One row per person rather than per contract: three jobs with the same
    brand used to be three inboxes, which fractures a relationship exactly
    when it is going well. A thread with no messages yet still appears — a
    contract just signed is exactly when somebody needs to start one.
    """
    return conversations.list_threads(db, user_id)


@router.get("/with/{user_id}", response_model=list[schemas.MessageOut])
def conversation_with(
    user_id: str,
    db: Session = Depends(get_db),
    me: str = Depends(get_current_user_id),
):
    """Everything you and this person have said, across every job you share.

    Requires at least one contract between the two of you (403 otherwise) —
    the same gate as everywhere else in this module, asked one scope wider.
    Reading is what marks the incoming messages read.
    """
    return conversations.get_conversation(db, me, user_id)


@router.post(
    "/with/{user_id}",
    response_model=schemas.MessageOut,
    status_code=status.HTTP_201_CREATED,
)
def send_to_counterparty(
    user_id: str,
    payload: schemas.DirectMessageIn,
    db: Session = Depends(get_db),
    me: str = Depends(get_current_user_id),
):
    """Write to a person rather than to a campaign.

    Requires at least one contract between the two of you (403 otherwise). The
    message is stamped with the most recent shared contract's campaign, which
    keeps every message's provenance intact — it is a record of which job the
    conversation was about, never an authorisation.
    """
    return conversations.send_to(db, me, user_id, payload.body)


@router.post("/campaigns/{campaign_id}/messages", response_model=schemas.MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(
    campaign_id: str,
    payload: schemas.MessageIn,
    db: Session = Depends(get_db),
    sender_id: str = Depends(get_current_user_id),
):
    """Send a message on a campaign. Requires a contract with the recipient.

    Locked with a 403 until a contract exists between the two of you on this
    campaign: before that a message is a cold lead, after it a message is work.
    Kept alongside the counterparty endpoint above — this is the precise way
    to address one job's thread, and it is what the web app calls. KOL-26.
    """
    return service.send_message(db, campaign_id, sender_id, payload.to_user_id, payload.body)


@router.get("/campaigns/{campaign_id}/messages", response_model=list[schemas.MessageOut])
def get_thread(
    campaign_id: str,
    with_user_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Read the thread on a campaign between you and the other party.

    Same contract gate as sending, and reading is what marks the incoming
    messages read. Scoped to one job; the whole relationship reads through
    GET /messaging/with/{user_id}.
    """
    return service.get_thread(db, campaign_id, user_id, with_user_id)

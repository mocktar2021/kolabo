"""Epic F (KOL-6): Messaging and Notifications."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import get_current_user_id
from app.modules.messaging import schemas, service

router = APIRouter()


@router.get("/threads", response_model=list[schemas.ThreadOut])
def my_threads(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """The caller's inbox: one row per conversation, newest contract first.

    Each row names the OTHER party — a creator by display name, a business by
    company name — with the last message, when it arrived, and how many are
    still unread. A thread with no messages yet still appears: a contract just
    signed is exactly when somebody needs to start one.
    """
    return service.list_threads(db, user_id)


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
    KOL-26.
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
    messages read.
    """
    return service.get_thread(db, campaign_id, user_id, with_user_id)

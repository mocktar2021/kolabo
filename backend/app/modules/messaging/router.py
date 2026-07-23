"""Epic F (KOL-6): Messaging and Notifications."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import get_current_user_id
from app.modules.messaging import schemas, service

router = APIRouter()


@router.post("/campaigns/{campaign_id}/messages", response_model=schemas.MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(
    campaign_id: str,
    payload: schemas.MessageIn,
    db: Session = Depends(get_db),
    sender_id: str = Depends(get_current_user_id),
):
    """Send a message tied to a campaign. Locked until an invitation or proposal exists. KOL-26."""
    return service.send_message(db, campaign_id, sender_id, payload.to_user_id, payload.body)


@router.get("/campaigns/{campaign_id}/messages", response_model=list[schemas.MessageOut])
def get_thread(
    campaign_id: str,
    with_user_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Read the thread on a campaign between you and another party."""
    return service.get_thread(db, campaign_id, user_id, with_user_id)

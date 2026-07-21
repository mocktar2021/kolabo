"""Epic F (KOL-6): Messaging & Notifications."""
from fastapi import APIRouter

router = APIRouter()


@router.post("/threads/{campaign_id}/messages")
def send_message(campaign_id: str):
    """See KOL-26. Locked until an invitation/application exists."""
    raise NotImplementedError

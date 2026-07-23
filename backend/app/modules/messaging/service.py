"""Messaging business logic (Epic F, KOL-26).

A message thread is tied to a specific campaign and is only unlocked once a
relationship exists between the two parties: the campaign owner (business) and
an influencer who has either been invited to the campaign or has submitted a
proposal for it. This prevents cold contact between strangers and doubles as a
fraud reduction control.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.campaigns import models as campaigns
from app.modules.messaging.models import Message
from app.modules.notifications.service import notify


def _relationship_exists(db: Session, campaign_id: str, influencer_id: str) -> bool:
    invited = (
        db.query(campaigns.CampaignInvitation)
        .filter(
            campaigns.CampaignInvitation.campaign_id == campaign_id,
            campaigns.CampaignInvitation.influencer_user_id == influencer_id,
        )
        .first()
    )
    if invited is not None:
        return True
    proposed = (
        db.query(campaigns.Proposal)
        .filter(
            campaigns.Proposal.campaign_id == campaign_id,
            campaigns.Proposal.influencer_user_id == influencer_id,
        )
        .first()
    )
    return proposed is not None


def send_message(db: Session, campaign_id: str, sender_id: str, to_user_id: str, body: str) -> dict:
    campaign = db.query(campaigns.Campaign).filter(campaigns.Campaign.id == campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    parties = {sender_id, to_user_id}
    business_id = campaign.business_user_id
    if business_id not in parties:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Messages must be between the campaign owner and an influencer")
    if len(parties) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose a different recipient")
    influencer_id = (parties - {business_id}).pop()

    if not _relationship_exists(db, campaign_id, influencer_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Messaging is locked until an invitation or a proposal exists on this campaign",
        )

    message = Message(campaign_id=campaign_id, sender_user_id=sender_id, recipient_user_id=to_user_id, body=body)
    db.add(message)
    notify(db, to_user_id, "message", f"New message about the campaign {campaign.title}")
    db.commit()
    db.refresh(message)
    return {
        "id": message.id,
        "campaign_id": message.campaign_id,
        "sender_user_id": message.sender_user_id,
        "recipient_user_id": message.recipient_user_id,
        "body": message.body,
    }


def get_thread(db: Session, campaign_id: str, user_id: str, with_user_id: str) -> list[dict]:
    pair = {user_id, with_user_id}
    rows = (
        db.query(Message)
        .filter(Message.campaign_id == campaign_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    thread = [m for m in rows if {m.sender_user_id, m.recipient_user_id} == pair]
    return [
        {
            "id": m.id,
            "campaign_id": m.campaign_id,
            "sender_user_id": m.sender_user_id,
            "recipient_user_id": m.recipient_user_id,
            "body": m.body,
        }
        for m in thread
    ]

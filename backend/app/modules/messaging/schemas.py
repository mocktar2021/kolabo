"""Schemas for the messaging module."""
from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    to_user_id: str
    body: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    id: str
    campaign_id: str
    sender_user_id: str
    recipient_user_id: str
    body: str

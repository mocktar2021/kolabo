"""Schemas for the notifications module."""
from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: str
    type: str
    message: str
    is_read: bool


class SubscriptionIn(BaseModel):
    type: str
    email_enabled: bool

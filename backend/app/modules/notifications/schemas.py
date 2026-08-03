"""Schemas for the notifications module."""
from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: str
    type: str
    # The English prose: the email body, and the client's fallback for any row
    # written before params existed.
    message: str
    # Where clicking goes (null → the client falls back to routeForType(type)),
    # and the localised-body source: {"key": ..., ...interpolation}. Null params
    # means the client renders `message` verbatim.
    link: str | None = None
    params: dict | None = None
    is_read: bool
    # A bell menu is read newest first and every row in it is dated — "2h"
    # beside a line is most of what tells a reader whether it still matters.
    # The field was absent for as long as nothing consumed these endpoints,
    # which made the service's newest-first ordering a promise no client could
    # restate or check.
    created_at: datetime


class UnreadCountOut(BaseModel):
    """What the bell draws while it is closed.

    Its own endpoint rather than a number the client derives from the list,
    because the two questions are different sizes. The badge is asked for on
    every page and stays one cheap COUNT; the list is capped, so a length
    taken from it would report at most a page — a badge reading "50" for
    somebody with two hundred unread notifications is a badge that lies, and
    lifting the cap to fix that would mean shipping a user's entire history
    to render a number.
    """

    unread: int


class MarkAllReadOut(BaseModel):
    # How many rows the sweep actually touched, so a client can settle its
    # badge to zero and know it was not racing another tab.
    marked: int


class SubscriptionIn(BaseModel):
    type: str
    email_enabled: bool

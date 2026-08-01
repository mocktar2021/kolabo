"""Schemas for the messaging module."""
from datetime import datetime

from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    to_user_id: str
    body: str = Field(min_length=1, max_length=4000)


class DirectMessageIn(BaseModel):
    """A message addressed to a person, on the counterparty endpoint.

    No to_user_id: the recipient is in the path. Carrying it in the body as
    well would create two places to say who this is for and one of them would
    eventually be wrong.
    """

    body: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    id: str
    # Which job this message was about. Kept on every message, including ones
    # sent through the counterparty endpoint, because provenance is what a
    # dispute reads: "when was the revision asked for, and on which job".
    campaign_id: str
    sender_user_id: str
    recipient_user_id: str
    body: str
    created_at: datetime
    # Null until the recipient opens the thread. Carried on the row rather
    # than summarised, because in a dispute the useful fact is when a specific
    # message was seen, not how many are outstanding.
    read_at: datetime | None = None


class ThreadOut(BaseModel):
    """One conversation on the inbox screen: one row per PERSON.

    It used to be one row per CONTRACT, which meant a creator who worked with
    the same brand three times had three inboxes with the same name on them.
    The relationship gets more valuable each time it repeats and the product
    was chopping it up in response, so the row is now the counterparty and the
    contracts are an attribute of it.

    counterparty_name is null when the other side has written no profile — the
    same rule identity follows everywhere else, and for the same reason: the
    users table holds only a phone number, and a phone number is never handed
    to the other side of a deal.
    """

    counterparty_user_id: str
    counterparty_name: str | None = None
    # Only ever set for a creator counterparty. A business has a company name
    # and no avatar in this system.
    counterparty_avatar_url: str | None = None
    # Every contract between the two, newest first, and how many there are.
    # "We have done four jobs together" is a fact about a relationship worth
    # showing, and a client that wants to link to one job still can.
    contract_ids: list[str] = Field(default_factory=list)
    contract_count: int = 0
    # The newest shared contract and its campaign, spelled out on their own.
    # Kept so a client written against the per-contract shape keeps rendering,
    # and because "the job we are currently on" is what a thread header wants
    # to name anyway.
    contract_id: str
    campaign_id: str
    campaign_title: str | None = None
    last_message: str | None = None
    last_message_at: datetime | None = None
    # Across the whole relationship, not one job: an unanswered question is
    # unanswered whichever contract it was asked under.
    unread_count: int = 0

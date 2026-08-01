"""Schemas for the messaging module."""
from datetime import datetime

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
    created_at: datetime
    # Null until the recipient opens the thread. Carried on the row rather
    # than summarised, because in a dispute the useful fact is when a specific
    # message was seen, not how many are outstanding.
    read_at: datetime | None = None


class ThreadOut(BaseModel):
    """One conversation on the inbox screen.

    A row per campaign the caller has a contract on, named by the OTHER
    person: a creator's inbox says "Maison Kola", a brand's says "Ama K.".
    Naming it by campaign title alone would give a brand working with six
    creators on one campaign six identical rows.

    counterparty_name is null when the other side has written no profile — the
    same rule identity follows everywhere else, and for the same reason: the
    users table holds only a phone number, and a phone number is never handed
    to the other side of a deal.
    """

    campaign_id: str
    campaign_title: str | None = None
    # The contract that opened this thread. The client links straight to it,
    # and it is also the answer to "why am I allowed in here".
    contract_id: str
    counterparty_user_id: str
    counterparty_name: str | None = None
    # Only ever set for a creator counterparty. A business has a company name
    # and no avatar in this system.
    counterparty_avatar_url: str | None = None
    last_message: str | None = None
    last_message_at: datetime | None = None
    unread_count: int = 0

"""Schemas for the campaigns module."""
from datetime import date

from pydantic import BaseModel, Field

# A note is a sentence or two explaining an offer, not a chat window. Past a
# couple of thousand characters somebody is holding a conversation in a text
# box, and conversations belong in messaging — the note exists so the terms
# can carry their own reasoning, not so the negotiation can become a thread.
MAX_NOTE_LENGTH = 2000


class Deliverable(BaseModel):
    platform: str
    type: str
    quantity: int = Field(ge=1)


class CampaignCreate(BaseModel):
    title: str = Field(min_length=1)
    budget_amount: int | None = Field(default=None, ge=1)
    budget_currency: str | None = None
    deliverables: list[Deliverable] = Field(default_factory=list)
    deadline: date | None = None
    publish: bool = False


class CampaignOut(BaseModel):
    id: str
    business_user_id: str
    title: str
    budget_amount: int | None
    budget_currency: str | None
    deliverables: list[Deliverable]
    deadline: date | None
    status: str


class InvitationOut(BaseModel):
    id: str
    campaign_id: str
    influencer_user_id: str
    status: str


class ProposalIn(BaseModel):
    rate_amount: int = Field(ge=1)
    rate_currency: str = Field(min_length=3, max_length=3)
    timeline_days: int = Field(ge=1)
    # Optional: a creator who wants to send bare numbers still can. It is only
    # there for the ones who have something to say about them.
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)


class ProposalReplyIn(BaseModel):
    """The business answering an offer.

    The note is required and the terms are optional, which is the entire point
    of the endpoint. A reply always says something — "the budget stops at
    40k", "can you do it in five days" — and it counters only when the business
    actually wants different numbers. A note with no terms is a message, and
    messages leaving for WhatsApp is what this whole feature is here to stop.

    Currency is not on this schema: a chain is priced in one currency or it is
    two negotiations pretending to be one.
    """

    note: str = Field(min_length=1, max_length=MAX_NOTE_LENGTH)
    rate_amount: int | None = Field(default=None, ge=1)
    timeline_days: int | None = Field(default=None, ge=1)


class ProposalOut(BaseModel):
    id: str
    campaign_id: str
    influencer_user_id: str
    version: int
    rate_amount: int
    rate_currency: str
    timeline_days: int
    status: str
    note: str | None = None
    # Which side wrote this version. Defaults to the creator: every proposal
    # that predates the business reply came from one.
    author_role: str = "influencer"
    # Who the offer is from, in a form the business can act on. A proposals
    # list of bare user ids is unusable: nobody picks "Créateur 424275c0".
    # Null until the creator has a profile, and it stays null — the users
    # table has only a phone number to offer, and a phone number is never
    # handed to the other side of a deal.
    display_name: str | None = None
    avatar_url: str | None = None


class CampaignDetailOut(CampaignOut):
    invitations: list[InvitationOut] = Field(default_factory=list)
    proposals: list[ProposalOut] = Field(default_factory=list)


class InvitationWithCampaign(BaseModel):
    id: str
    campaign_id: str
    influencer_user_id: str
    status: str
    # The whole brief, not a summary of it: the creator prices from this card,
    # and deliverables, budget and deadline are exactly what they price
    # against. CampaignOut already carries all of it, so it is nested rather
    # than copied field by field onto the row.
    campaign: CampaignOut
    # Who is asking. Null while the business has not filled in a profile — the
    # users table has only a phone number to offer, and that is never exposed.
    business_company_name: str | None = None

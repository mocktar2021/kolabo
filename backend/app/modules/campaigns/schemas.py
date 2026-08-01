"""Schemas for the campaigns module."""
from datetime import date, datetime

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
    # True when this campaign is really a direct order. The client needs it to
    # label the card as an order rather than a brief, and to know there is
    # nobody else bidding.
    is_direct: bool = False


class CreatorIdentity(BaseModel):
    """How a creator appears on any row a business reads.

    One shape everywhere, filled by app.core.identity.creator_identities:
    favourites, campaign invitations, proposals. A business comparing an
    invitation against a proposal is looking at the same person, and used to
    be shown a raw user id on one and a name on the other.

    Every field is optional — somebody can be invited the day they sign up,
    before they have written a profile. Nothing here is ever filled in from
    the users table: the only identifier it holds is a phone number, and a
    phone number is never handed to the other side of a deal.
    """

    display_name: str | None = None
    avatar_url: str | None = None
    # The single biggest connected platform, never a sum across platforms:
    # somebody following on two networks would otherwise be counted twice.
    top_platform: str | None = None
    top_follower_count: int | None = None


class InvitationOut(CreatorIdentity):
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


class OrderIn(BaseModel):
    """A brand buying a creator's package outright.

    Only the package id and an optional word to the creator. Everything a
    campaign normally asks for — title, budget, deliverables, currency — is
    read off the package, because the whole promise of a package is that the
    creator already decided all of it and published a price.
    """

    package_id: str
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)


class OrderOut(BaseModel):
    """What the buyer needs after placing an order.

    Deliberately not the whole campaign: the interesting facts are where the
    order lives, which offer the creator is answering, and the deadline they
    are answering by. The campaign detail endpoint serves the rest.
    """

    campaign_id: str
    proposal_id: str
    expires_at: datetime | None


class ProposalOut(CreatorIdentity):
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
    # When a direct order stops being answerable. Null on everything else —
    # only direct orders run on a clock.
    expires_at: datetime | None = None


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
    # The live version of the negotiation, or None when nothing has been
    # offered yet. A brief's invitation normally arrives before any proposal
    # exists; a direct order always carries one, because the buyer's offer IS
    # the order.
    #
    # It is here because this is the ONLY creator-facing list an order appears
    # in, and accepting or declining one is addressed by proposal id. Campaign
    # detail is owner-only, so without this the creator could see an order and
    # have nothing to answer it with. expires_at on it is also what tells the
    # two kinds of row apart client-side: only a direct order runs on a clock.
    proposal: ProposalOut | None = None

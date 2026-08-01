"""Schemas for the campaigns module."""
from datetime import date, datetime

from pydantic import BaseModel, Field

# A note is a sentence or two explaining an offer, not a chat window. Past a
# couple of thousand characters somebody is holding a conversation in a text
# box, and conversations belong in messaging — the note exists so the terms
# can carry their own reasoning, not so the negotiation can become a thread.
MAX_NOTE_LENGTH = 2000

# The fields that together make up a negotiated offer. Named as a group
# because the rule about them is a group rule: all of them or none of them,
# and never alongside a package_id.
CUSTOM_OFFER_FIELDS = (
    "creator_user_id",
    "platform",
    "deliverable_type",
    "quantity",
    "rate_amount",
    "currency",
    "timeline_days",
)


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
    """A brand ordering from a creator, in one of two forms.

        {"package_id": "..."}
            The package exactly as listed. Title, budget, deliverable and
            currency are read off it, because the whole promise of a package
            is that the creator already decided all of it and published a
            price.

        {"creator_user_id": ..., "platform": ..., "deliverable_type": ...,
         "quantity": ..., "rate_amount": ..., "currency": ...,
         "timeline_days": ...}
            Terms the brand negotiated instead. Everything a package would
            have decided, decided by the buyer — because plenty of deals do
            not fit a listed bundle, and the ones that do not were the deals
            leaving for WhatsApp.

    Exactly one form per request. A body carrying both is not a preference to
    resolve, it is two different orders in one envelope.

    The bounds on the custom fields (quantity, floor price, timeline) are NOT
    declared here. They are checked in campaigns.negotiated so the answer is a
    400 naming the rule and what is allowed, in the same words the packages
    module uses — a 422 field-error would tell a brand that its price is
    invalid without ever mentioning the floor.
    """

    # Shared by both forms: a word to the creator about the offer.
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)

    package_id: str | None = None

    creator_user_id: str | None = None
    platform: str | None = None
    deliverable_type: str | None = None
    quantity: int | None = None
    rate_amount: int | None = None
    currency: str | None = None
    timeline_days: int | None = None


class OrderOut(BaseModel):
    """What the buyer needs after placing an order.

    Deliberately not the whole campaign: the interesting facts are where the
    order lives, which offer the creator is answering, and the deadline they
    are answering by. The campaign detail endpoint serves the rest. The same
    for both forms of order, because from here on there is only one kind of
    thing.
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

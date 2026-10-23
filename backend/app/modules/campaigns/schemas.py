"""Schemas for the campaigns module."""
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

# A note is a sentence or two explaining an offer, not a chat window. Past a
# couple of thousand characters somebody is holding a conversation in a text
# box, and conversations belong in messaging — the note exists so the terms
# can carry their own reasoning, not so the negotiation can become a thread.
MAX_NOTE_LENGTH = 2000

# A brief in prose. Longer than a note because this one IS the document: the
# brand explaining context, tone and what it is trying to say. The cap is here
# so a paste of an entire deck cannot become a campaign row.
MAX_DESCRIPTION_LENGTH = 5000

# The licence sub-fields are one line each of a contract clause, not prose.
#
# "douze (12) mois a compter de la premiere publication" is a duration.
# "Benin, Togo, Cote d'Ivoire et Ghana" is a territory list. "les reseaux
# sociaux de la marque, son site web et la publicite payante en ligne" is a
# media list. The caps are generous enough for a wordy legal formulation in
# French — which runs longer than its English equivalent — and small enough
# that nobody pastes a brief into the field a contract quotes verbatim.
#
# Duration is the shortest of the three because it is one span of time however
# carefully it is phrased, while territories and media are lists that grow with
# the deal.
MAX_LICENCE_DURATION_LENGTH = 120
MAX_LICENCE_TERRITORIES_LENGTH = 200
MAX_LICENCE_MEDIA_LENGTH = 200
MAX_LICENCE_CONSIDERATION_LENGTH = 200

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

# The list-valued targeting columns, named as a group because one rule covers
# both of them: they are NOT NULL, so an explicit null has to mean the empty
# list rather than reaching the database.
TARGET_LIST_FIELDS = ("target_categories", "target_countries")


class Deliverable(BaseModel):
    platform: str
    type: str
    quantity: int = Field(ge=1)


class LicenceTermsIn(BaseModel):
    """How the brand says it may use the content, on the way in.

    Article 10 of the model counsel approved
    (claude/kolabo-contrat-collaboration-modele-fr.md) makes the Parties retain
    one of three options and leaves "Option retenue : [ 1 / 2 / 3 ]" to be
    filled in per contract. This is the shape a brand states it in, and the
    same shape on a brief (CampaignCreate, CampaignPatch) and on a direct order
    (OrderIn), because it is one statement about one thing however the deal was
    reached.

    A NESTED OBJECT AND NOT FIVE FLAT FIELDS, which is the one shape decision
    here. The block is read and written whole everywhere it goes: it is stored
    as a single JSON column, snapshotted as a single value onto the contract,
    and campaigns.editing compares what a patch sends against what the column
    holds to decide whether this term is locked. Flat fields would make that
    comparison five against five and would put the brand's licence in a
    different shape on the way in from the one it has everywhere else.

    EVERY FIELD IS OPTIONAL HERE AND THAT IS NOT THE RULE. What each option
    requires is answered in campaigns/licence.py, with a 400 naming the fields
    that are missing, because the requirement depends on licence_option: a 422
    saying licence_duration is invalid would never mention that option 2 is
    what asks for it. This schema's job is the shape and the length caps.

    licence_option IS A STRING, "1", "2" or "3", because it is the label
    Article 10 prints and not a quantity anybody does arithmetic on. A client
    sending the number 1 gets a 422 from pydantic rather than a
    licence_terms_invalid, which is worth knowing when reading a client bug
    report.

    THE VALUES ARE QUOTED INTO A CONTRACT VERBATIM. A duration stated in French
    stays French; nothing on the way in or the way out normalises, translates or
    maps them onto a vocabulary. campaigns/licence.py strips the edges and that
    is all.
    """

    licence_option: str | None = None
    licence_duration: str | None = Field(default=None, max_length=MAX_LICENCE_DURATION_LENGTH)
    licence_territories: str | None = Field(
        default=None, max_length=MAX_LICENCE_TERRITORIES_LENGTH
    )
    licence_media: str | None = Field(default=None, max_length=MAX_LICENCE_MEDIA_LENGTH)
    licence_consideration: str | None = Field(
        default=None, max_length=MAX_LICENCE_CONSIDERATION_LENGTH
    )


class TargetingIn(BaseModel):
    """Who a brand is hoping to reach with a brief, on the way in.

    Shared by create and patch because it is one set of fields with one
    meaning, and a second copy would be a second place for the null rule
    below to be forgotten.

    NONE OF IT NARROWS ANYTHING. These four fields rank the open board for a
    creator and never hide a brief from one — campaigns.board says why at
    length. The naming says "target", not "require", for exactly that reason.
    """

    target_categories: list[str] | None = None
    target_countries: list[str] | None = None
    # ge=0 rather than ge=1: a brand may legitimately say "up to 5000", and
    # the floor of that band is zero followers, not one.
    target_min_followers: int | None = Field(default=None, ge=0)
    target_max_followers: int | None = Field(default=None, ge=0)

    @field_validator(*TARGET_LIST_FIELDS, mode="before")
    @classmethod
    def _null_clears_to_empty(cls, value):
        """An explicit null on a targeting list means "clear it".

        Coerced to [] here rather than refused, because the two spellings
        plainly mean the same thing: a form whose last chip was just removed
        posts [] in some clients and null in others, and both are a brand
        saying it no longer wants to target that dimension. The column is NOT
        NULL, so letting the null through would turn a cleared form into an
        integrity error at commit — a 500 for a user who did nothing wrong.

        Only runs on a value the client actually sent, so the exclude_unset
        contract PATCH depends on is untouched: a field nobody mentioned stays
        unmentioned.
        """
        return [] if value is None else value


class CampaignCreate(TargetingIn):
    title: str = Field(min_length=1)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_LENGTH)
    budget_amount: int | None = Field(default=None, ge=1)
    budget_currency: str | None = None
    deliverables: list[Deliverable] = Field(default_factory=list)
    # How the brand may use the content. Taken at creation beside the budget
    # and the deliverables because it is a TERM and not a description: a
    # creator prices a licence to redistribute in paid advertising differently
    # from a post on the creator's own feed, so it belongs on the brief they
    # are pricing rather than on a second screen afterwards.
    #
    # Optional, like every other term on a draft: somebody writing down an
    # idea before they know what it is should not be stopped on Article 10.
    # What is not optional is generating a contract from a brief that never
    # stated one, which contracts/service.py refuses.
    licence_terms: LicenceTermsIn | None = None
    deadline: date | None = None
    publish: bool = False
    # Whether the brief goes onto the open board. Accepted at creation as well
    # as on a PATCH because deciding who a brief is for is part of writing it,
    # and making a brand save the brief and then open it in a second request
    # would be two calls for one decision. Still defaults to False: a client
    # that has never heard of the board cannot open a brief by accident.
    is_open: bool = False


class CampaignPatch(TargetingIn):
    """A partial correction to a campaign.

    Every field is optional, and the rule is exclude_unset — the same contract
    the profile upsert runs on. A field the client did not send is left alone;
    a nullable field the client explicitly sent as null IS cleared, because
    that is how a form clears a value. A client that does not know about a
    column must not be able to wipe it just by not knowing.

    Which of these may actually change is NOT decided here, and cannot be: the
    answer depends on whether the campaign is published and whether anybody
    has priced against it. That lives in campaigns.editing, which answers with
    a 400 naming the field — a 422 field-error would tell a brand its budget
    is invalid without ever explaining that a creator has already bid on it.

    The targeting fields inherited from TargetingIn are deliberately NOT in
    campaigns.editing.LOCKED_FIELDS, so they stay editable after a creator has
    bid. They are not terms: nobody prices a brief against who else the brand
    was hoping to hear from, and a bid on the table means exactly what it
    meant before the brand widened its board. is_open is the same — closing a
    brief to new applications takes nothing away from the offers already made.

    licence_terms, by contrast, IS in LOCKED_FIELDS, and the difference is the
    whole reason that tuple exists: a creator who bid on a brief that said the
    brand would not redistribute did not bid on one that says it may.

    publish is absent on purpose. Going live is a state change with its own
    readiness gate (POST /campaigns/{id}/publish), not a field to set.
    """

    # min_length rather than nullable: the column is NOT NULL, so an explicit
    # null is refused in the service with a sentence rather than crashing on
    # the insert.
    title: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_LENGTH)
    budget_amount: int | None = Field(default=None, ge=1)
    budget_currency: str | None = None
    deliverables: list[Deliverable] | None = None
    # An explicit null clears the licence, exactly as it clears a deadline:
    # that is how a form unsets a value, and a brand that has not published
    # yet is entitled to take the clause back out. Once a creator has priced
    # against it, clearing it is a change like any other and campaigns.editing
    # refuses it with campaign_field_locked.
    licence_terms: LicenceTermsIn | None = None
    deadline: date | None = None
    is_open: bool | None = None


class CampaignOut(BaseModel):
    id: str
    business_user_id: str
    title: str
    description: str | None = None
    budget_amount: int | None
    budget_currency: str | None
    deliverables: list[Deliverable]
    # The licence the brand stated, or null when it has stated none.
    #
    # ON THE ORDINARY CAMPAIGN PAYLOAD AND NOT ONLY ON THE BOARD'S, because
    # this is the payload every creator-facing surface nests: the open board
    # row (OpenBriefOut) and the invitation card (InvitationWithCampaign) both
    # carry a CampaignOut, and the licence has to reach the creator while they
    # still have a decision to make. It also has to reach the buyer's own list,
    # which is where a brand checks what it published.
    #
    # A PLAIN DICT, the same choice ContractDetailOut makes about its party
    # blocks and for the same reason: the block's shape varies by option, which
    # is why the column is JSON rather than five mostly null columns, and a
    # response model enumerating every field would be a second place to keep in
    # step with the capture schema. Both clients already carry the typed shape.
    #
    # Null means the brand has stated nothing, which both clients must render
    # as unstated rather than as option 1. Nobody chose option 1.
    licence_terms: dict[str, Any] | None = None
    deadline: date | None
    status: str
    # True when this campaign is really a direct order. The client needs it to
    # label the card as an order rather than a brief, and to know there is
    # nobody else bidding.
    is_direct: bool = False
    # Whether the brief is on the open board. Carried on the ordinary campaign
    # payload, not only on the board's own, because the buyer's list of its
    # campaigns has to be able to say which of them strangers can apply to —
    # that is the difference between a brief with three invited creators and a
    # brief that may collect thirty applications overnight.
    is_open: bool = False
    target_categories: list[str] = Field(default_factory=list)
    target_countries: list[str] = Field(default_factory=list)
    target_min_followers: int | None = None
    target_max_followers: int | None = None


class OpenBriefOut(CampaignOut):
    """One row of the open board (GET /campaigns/open).

    The whole brief, not a summary of it: a creator decides from this card
    whether to spend an evening pricing the job, and deliverables, budget and
    deadline are exactly what they would be pricing.

    So is the licence, inherited from CampaignOut. A brief that says the brand
    may redistribute the content in paid advertising for a year is a bigger job
    than one that says the creator posts it once, and a board that showed the
    budget without the licence would be a board creators price wrong.

    match_score is shown rather than hidden. A board that silently reorders
    itself is a board creators invent theories about, and the number is small,
    explainable and bounded (campaigns.board.MAX_MATCH_SCORE). It is a
    ranking hint and not a verdict — a zero-scoring brief is just as
    applicable as a perfect one, which is the point of a soft filter.

    has_applied and is_invited keep the card honest about what the creator has
    already done here: applying twice is refused with a 409, and finding that
    out from the button rather than from the error is the difference between
    a board and a trap.
    """

    # Who is asking. Null while the buyer has written no profile — the users
    # table has only a phone number to offer, and that is never exposed.
    business_company_name: str | None = None
    match_score: int = 0
    has_applied: bool = False
    is_invited: bool = False


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
    # NO LICENCE FIELD, AND THAT IS THE RULE RATHER THAN AN OMISSION. The brand
    # states how it may use the content; the creator accepts or declines those
    # terms. A creator countering a direct order writes this payload, and
    # service.submit_proposal carries the brand's block forward onto the new
    # version rather than taking one from here, so a counter answers the price
    # without rewriting the licence it was offered under.


class ProposalReplyIn(BaseModel):
    """The business answering an offer.

    The note is required and the terms are optional, which is the entire point
    of the endpoint. A reply always says something — "the budget stops at
    40k", "can you do it in five days" — and it counters only when the business
    actually wants different numbers. A note with no terms is a message, and
    messages leaving for WhatsApp is what this whole feature is here to stop.

    Currency is not on this schema: a chain is priced in one currency or it is
    two negotiations pretending to be one.

    Neither is the licence, for a reason worth stating because the buyer DOES
    author this one. A reply is a counter on the money and the date, which are
    the two things a negotiation moves; the licence was stated when the order
    was placed and the creator has been reading it ever since. Changing it
    mid-chain would move what is being bought rather than what it costs, and
    silently: there is no creator-facing diff of a licence. A brand that wants
    different licence terms places a new order.
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

    THE LICENCE BELONGS TO NEITHER FORM AND TRAVELS WITH BOTH. A package is
    the creator's statement of what they will make and what it costs; how the
    brand may then use it is the brand's to state, on a listed package exactly
    as on terms it typed itself. So licence_terms sits beside `note` as a
    field both shapes carry, and check_order_form has no opinion about it.

    The bounds on the custom fields (quantity, floor price, timeline) are NOT
    declared here. They are checked in campaigns.negotiated so the answer is a
    400 naming the rule and what is allowed, in the same words the packages
    module uses — a 422 field-error would tell a brand that its price is
    invalid without ever mentioning the floor. The licence is checked in
    campaigns.licence for the same reason.
    """

    # Shared by both forms: a word to the creator about the offer.
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)
    # Shared by both forms: how the brand may use what it is buying.
    licence_terms: LicenceTermsIn | None = None

    package_id: str | None = None

    creator_user_id: str | None = None
    platform: str | None = None
    deliverable_type: str | None = None
    quantity: int | None = None
    rate_amount: int | None = None
    currency: str | None = None
    timeline_days: int | None = None


class CartItemIn(OrderIn):
    """One line of a basket.

    Literally an order body, inherited rather than re-declared: a line in a
    cart is a thing a brand could have ordered on its own, in either of the
    same two forms, under the same rules. Copying the fields would let the two
    drift, and the first place they drifted would be which terms a checkout
    accepts that a single order does not.

    WHICH MEANS A LINE CARRIES A LICENCE, and a basket can therefore state two
    different ones for the same creator. That is not a merge for the server to
    resolve: one creator's lines become ONE order with one contract, and a
    contract states one licence. campaigns.cart refuses the disagreement
    naming it, the same way it refuses two currencies for one creator.
    """


class CartCheckoutIn(BaseModel):
    """A whole basket, posted in one go.

    There is no cart on the server: the client holds it and sends all of it at
    checkout. campaigns.cart says why — briefly, a stored basket buys a table,
    an expiry policy and a stale-price problem for nothing.

    The 1..20 bound is enforced in the service, not here, so an oversized cart
    hears a sentence about the limit instead of a field error about "items".
    """

    items: list[CartItemIn] = Field(default_factory=list)


class CartOrderOut(BaseModel):
    """One creator's order out of a checkout.

    Carries creator_user_id where a single order's receipt does not: the buyer
    sent a flat list of items and got back a shorter list of orders, and
    without the creator on each row it cannot tell which order is whose.
    """

    creator_user_id: str
    campaign_id: str
    proposal_id: str
    expires_at: datetime | None


class CartCheckoutOut(BaseModel):
    orders: list[CartOrderOut] = Field(default_factory=list)


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
    # The licence this offer was made under, or null when the row states none.
    #
    # THIS IS THE ONLY PLACE A CREATOR READS A DIRECT ORDER'S LICENCE, which is
    # why it is on the proposal payload and not only on the campaign's. An
    # order's terms live on the brand's offer row, the creator meets that row as
    # `proposal` on their invitation card, and accept and decline are addressed
    # by its id. A card that showed the price without the licence would ask
    # somebody to accept terms they cannot see.
    #
    # Null on everything born of a brief, where the licence is on the campaign
    # instead, so a client reads the proposal's block when there is one and the
    # nested campaign's otherwise — which is the same precedence
    # contracts/service.py::_licence_snapshot applies at generation.
    licence_terms: dict[str, Any] | None = None
    # When a direct order stops being answerable. Null on everything else —
    # only direct orders run on a clock.
    expires_at: datetime | None = None
    # When this version was sent. A chain without timestamps is a list of
    # numbers; with them it is a conversation, and "they countered four days
    # ago" is most of what somebody needs to decide whether to chase. Required
    # rather than defaulted because the column is NOT NULL and every path that
    # builds this row goes through service._proposal_out, which carries it.
    created_at: datetime


class CampaignDetailOut(CampaignOut):
    invitations: list[InvitationOut] = Field(default_factory=list)
    proposals: list[ProposalOut] = Field(default_factory=list)


class CampaignDeletedOut(BaseModel):
    """The receipt for a hard delete.

    The id is echoed back because the row it names no longer exists to be
    fetched, and a client that removed the wrong card from its list has no way
    to find out otherwise.
    """

    id: str
    deleted: bool = True


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
    #
    # It is also where an order's licence arrives: the nested campaign above
    # carries a brief's block, and this carries an order's.
    proposal: ProposalOut | None = None
    # Every version of that same chain, OLDEST FIRST, capped exactly as the
    # brand's list is (service.MAX_PROPOSAL_VERSIONS, taken from the recent
    # end). The brand has always had the whole thread; the creator had only
    # the live version, so from version two onwards they were reading a number
    # with no idea what it was answering.
    #
    # Additive, and `proposal` above is deliberately left alone: it is still
    # the live version, still what accept and decline are addressed to, and a
    # client that has not been taught about this list behaves exactly as it
    # did. Empty — not absent — when nothing has been offered yet.
    proposal_history: list[ProposalOut] = Field(default_factory=list)

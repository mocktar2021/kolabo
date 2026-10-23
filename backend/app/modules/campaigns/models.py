"""Campaign, invitation, and proposal models (Epic D).

Money is stored in minor units (for example cents) with an explicit currency,
never as a float, per the multi currency principle in the architecture notes.
"""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


DRAFT = "draft"
PUBLISHED = "published"
# Closed with no deal. Reached two ways: a direct order the creator turned
# down or let lapse, and a brief the buyer called off (campaigns.editing).
# The row is kept rather than deleted in both cases: proposals, contracts and
# the audit trail hang off it, and the buyer changing its mind is not a reason
# to erase the other side's half of the record.
CANCELLED = "cancelled"
# Finished, as opposed to called off. Every contract on the brief reached an
# ending and at least one of those endings was the money moving — the rule the
# web client already derived for its Active/Completed shelves, now a status the
# server writes and guards from (campaigns.completion).
#
# Reached only from PUBLISHED, and never left. Nothing here re-opens: a brand
# with more work to commission publishes the next brief, which is a different
# brief with its own proposals and its own record.
COMPLETED = "completed"

INVITED = "invited"
ACCEPTED = "accepted"
DECLINED = "declined"

SUBMITTED = "submitted"
SUPERSEDED = "superseded"
PROPOSAL_ACCEPTED = "accepted"
PROPOSAL_REJECTED = "rejected"
# The creator saying no to a direct order, or the window closing on one.
# Deliberately not folded into PROPOSAL_REJECTED even though both mean "no
# deal": who said no is the useful part. Rejected is the buyer walking away
# from a bid it invited; declined is the seller turning down a purchase. The
# buyer needs to tell those apart to know whether re-offering makes any sense.
PROPOSAL_DECLINED = "declined"

# Taken back by whoever offered it, before the other side answered. Used for
# both an invitation the buyer retracted and a proposal the creator pulled
# (campaigns.withdrawals).
#
# One more status rather than reusing declined or rejected, and the reason is
# whose record it lands on. Declined and rejected both mean SOMEBODY SAID NO,
# and they are read that way: a creator's history full of declines reads as a
# creator who turns work down, and a campaign full of rejections reads as a
# buyer nobody could satisfy. A withdrawal is neither. Nobody refused
# anything; the offer was pulled before there was an answer to give, and
# recording that as a refusal would put a decision on somebody's record that
# they never made and cannot appeal.
WITHDRAWN = "withdrawn"

# Which side of the table a proposal version came from. A negotiation is two
# parties alternating, and without this a chain of five versions looks like one
# creator changing their mind five times.
AUTHOR_INFLUENCER = "influencer"
AUTHOR_BUSINESS = "business"


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    business_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    # The brief in prose: context, tone, what the brand is trying to say.
    # Nullable because a title alone is a legitimate draft — somebody writing
    # down an idea before they know what it is — and because every campaign
    # written before this column existed has nothing to put here.
    #
    # It is description and not terms, which is the whole reason it sits
    # beside title in campaigns.editing.LOCKED_FIELDS' opposite: rewriting it
    # after a creator has bid does not change what they bid FOR.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    budget_currency: Mapped[str | None] = mapped_column(String, nullable=True)
    deliverables: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # HOW THE BRAND MAY USE THE CONTENT, stated by the brand before any
    # contract exists.
    #
    # Article 10 of the model counsel approved
    # (claude/kolabo-contrat-collaboration-modele-fr.md) makes the Parties
    # retain one of three options and leaves "Option retenue : [ 1 / 2 / 3 ]"
    # to be filled in per contract. Until this column there was nothing in
    # this database that could fill it in, so every generated contract carried
    # an unanswered choice at the heart of it.
    #
    # IT IS A TERM, NOT A DESCRIPTION, and that is the distinction this whole
    # file turns on. A creator prices option 2 differently from option 1:
    # being redistributable on the brand's channels in paid advertising for a
    # year is not the same job as posting once on your own feed. So it sits in
    # campaigns.editing.LOCKED_FIELDS with budget, currency, deliverables and
    # deadline, it is carried on every creator-facing payload before
    # acceptance (the open board, the invitation, the direct order), and a
    # brand that wants different terms after somebody has bid publishes a new
    # brief rather than rewriting this one underneath them.
    #
    # THE SHAPE, documented here as well as at the schema that validates it,
    # because this is the column a reader will find first:
    #
    #   licence_option         "1" | "2" | "3"
    #   licence_duration       free text, option 2 and 3 only
    #   licence_territories    free text, option 2 and 3 only
    #   licence_media          free text, option 2 only
    #   licence_consideration  free text, option 3 only, optional
    #
    # Only the keys belonging to the stated option are written, so an option 1
    # block carries no empty duration for a renderer to wonder about.
    # campaigns/licence.py is where that is enforced and where each option's
    # required set is argued from the model's own table.
    #
    # EVERY VALUE IS FREE TEXT THE PARTIES STATED AND IS PRINTED VERBATIM. A
    # duration typed in French stays French; nothing normalises, translates or
    # maps these onto a vocabulary. They are not checked against anything
    # either, exactly as a party block is not: the platform records what the
    # brand states about the licence it wants, and whether that wording
    # achieves it in a given market is counsel's question (annex, question 6).
    #
    # JSON for the two reasons `deliverables` above established and
    # c8e2a5f71b30 restated: nothing joins on a licence block, it is read
    # whole for one campaign at a time, and its shape varies by option.
    #
    # Nullable, and null means NOBODY HAS STATED A LICENCE HERE rather than
    # "option 1". Every brief written before this column existed has nothing
    # to backfill from, and contracts/service.py refuses to generate from a
    # brief with no licence (contract_licence_terms_missing) rather than
    # guessing the option that happens to grant the brand least.
    licence_terms: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, default=DRAFT, nullable=False)
    # A direct order: one brand buying one creator's package, wearing a
    # campaign's clothes. It is a campaign because contracts, escrow, reviews
    # and disputes all already hang off a campaign and a proposal, and a
    # second parallel path through the money code would double the surface
    # where a payout can go wrong.
    #
    # It is HIDDEN because it is a private transaction between two parties,
    # not a brief anyone may bid on. Any listing that shows campaigns to
    # somebody who is not a participant must filter these out; a participant's
    # own views (my campaigns, my invitations, contracts) must still show them.
    is_direct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Whether this brief appears on the open board (campaigns.board), where a
    # creator can find it without ever having been invited.
    #
    # DEFAULT FALSE, AND THE DEFAULT IS THE POINT. Every campaign written
    # before the board existed was addressed to invited creators only, and a
    # migration that flipped them open would start showing strangers'
    # applications to brands that never asked for any — proposals arriving
    # from people they had not heard of, against briefs they thought were
    # private. Opening a brief is a decision the buyer makes, once, on
    # purpose.
    is_open: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Who the brand is hoping for. All four are a SOFT filter: they decide
    # what a creator sees FIRST on the board, and they never decide what a
    # creator sees at all. campaigns.board argues it at length — briefly, a
    # hard filter over a pilot-sized roster shows most creators an empty
    # board, and a brand can decline an application it did not want but can
    # never receive one it never saw.
    #
    # JSON lists rather than association tables because nothing joins on them:
    # they are read whole, for one campaign at a time, by a scoring function
    # that already has the row in memory.
    target_categories: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    target_countries: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # An audience band, either end of which may be left open. NULL means "no
    # opinion", which is not the same as 0 or as infinity: a brief that says
    # nothing about audience size must not quietly rank a creator with no
    # follower count below one who has filled the field in.
    target_min_followers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_max_followers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class CampaignInvitation(Base):
    __tablename__ = "campaign_invitations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    influencer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default=INVITED, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    influencer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_currency: Mapped[str] = mapped_column(String, nullable=False)
    timeline_days: Mapped[int] = mapped_column(Integer, nullable=False)
    # Why the number is the number. A rate with no reasoning attached gets
    # discussed somewhere else — which in this market means WhatsApp, and a
    # deal that leaves the platform is a deal we cannot contract or escrow.
    # The note hangs off the version rather than off a thread of its own: it
    # is an argument for these terms, and it stops being true the moment the
    # terms change.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Defaults to the creator because every proposal that existed before this
    # column came from one.
    author_role: Mapped[str] = mapped_column(String, default=AUTHOR_INFLUENCER, nullable=False)
    # THE LICENCE A DIRECT ORDER WAS PLACED UNDER. Same shape as
    # campaigns.licence_terms above, which carries the full argument and the
    # field list.
    #
    # It is here because on a direct order the brand's offer IS this row:
    # service._place_order writes version 1 with author_role business, and the
    # campaign it hangs off is a wrapper the creator never reads terms from. A
    # brief states its licence on the brief; an order states it on the offer.
    #
    # THE CREATOR NEVER WRITES IT. There is no licence field on ProposalIn and
    # no creator-facing form for one. What happens when a creator counters is
    # that the block is CARRIED FORWARD, exactly as expires_at below is
    # carried forward, and for a closely related reason: a counter is the same
    # order on the same clock under the same licence, and only the price or
    # the timeline moved. Left to default it would go to NULL, and the
    # countered order would then be uncontractable — generation would find no
    # licence and refuse, which is to say the creator could kill their own
    # deal by negotiating it.
    #
    # NULL on every proposal born of a brief, deliberately, and that is the
    # common case: there the licence lives on the campaign and generation
    # reads it from there. Null here therefore means "this row states no
    # licence of its own", never "no licence applies".
    licence_terms: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # When this offer stops being answerable. NULL for everything born of a
    # brief, and that is deliberate: a brief's proposals do not expire,
    # because there is no promise attached to leaving one open — the business
    # simply has not chosen yet. A direct order is the opposite. The buyer has
    # named a price and is waiting, so the creator gets a bounded window
    # (ORDER_ACCEPT_WINDOW_HOURS) to answer, after which the offer lapses.
    # Nothing is refunded when it does, because escrow is only funded after
    # acceptance and there is no money in the system yet.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, default=SUBMITTED, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

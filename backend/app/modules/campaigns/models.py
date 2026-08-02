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

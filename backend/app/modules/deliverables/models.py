"""Handing in the work, and the answer to it.

WHAT WAS MISSING. The word "deliverables" already existed in this codebase and
meant the AGREED SCOPE — `[{platform, type, quantity}]` frozen onto the campaign
and copied onto the contract. Nothing recorded the work itself. A creator handed
in a published post by pasting a link into the (text-only) message thread, and
the brand "validated" it by pressing Release on the escrow, which recorded that
money moved and never recorded WHAT it moved for. Acceptance and rejection
collapsed into two unrelated buttons: release (accept) and open-a-dispute
(reject). So when a case did reach an admin, there was no record of what had
been delivered or when — only whatever text happened to be in the chat.

A SUBMISSION IS AN IMMUTABLE ATTEMPT. "Request changes" does not reopen a row
for editing; it closes that attempt as changes_requested, and the creator's next
hand-in is a NEW row. The history is therefore the whole negotiation over
whether the work was done — the same shape as the proposal chain in campaigns
and the message thread in a dispute, and for the same reason: an admin settling
an argument needs to read what happened in order, not the last state somebody
left behind.

WHY THE STATUSES ARE A CLOSED SET. The brand's review queue triages by it, and
later fraud and quality analytics count it — "changes_requested three times on
one contract" is a pattern free text can never be counted into. The words go in
`note` and `review_note`; this is the label.

WHAT THIS MODULE MAY IMPORT. Nothing here imports payments.service or
contracts.service — only Base and the foreign keys, which are declared as
strings. That is what lets payments.service read THIS module's models (for the
auto-release rule) without closing a circle: deliverables.service depends on
payments.service, and payments.service depends only on deliverables.models.
contracts/cancellation.py documents the same arrangement from the other side.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Awaiting the brand's review. THE ONLY STATUS THAT RUNS THE AUTO-RELEASE
# CLOCK — see payments.service.run_due_auto_releases for why that matters.
SUBMITTED = "submitted"
# The brand accepted it. Terminal, and the escrow was released in the same
# transaction that wrote it.
APPROVED = "approved"
# The brand wants it redone. Terminal FOR THIS ATTEMPT: the escrow stays held
# and the creator submits again as a new row.
CHANGES_REQUESTED = "changes_requested"
# The creator pulled it back before anybody reviewed it.
WITHDRAWN = "withdrawn"

# The statuses in which an attempt is still the brand's to answer. Exactly one
# submission per contract may be in this set at a time, which is enforced in
# the service rather than by a unique column — "is there a live one" is a
# question about status, and a column cannot ask it. disputes.OPEN_STATUSES is
# the same rule for the same reason.
OPEN_STATUSES = (SUBMITTED,)


class DeliverableSubmission(Base):
    """One hand-in of completed work against one funded contract."""

    __tablename__ = "deliverable_submissions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    # The contract, not the escrow. The contract is what names the two parties
    # and what survives; the escrow is found through it (escrows.contract_id is
    # UNIQUE, so the relationship is 1:1) and may not be the thing a later
    # reader cares about.
    contract_id: Mapped[str] = mapped_column(
        ForeignKey("contracts.id"), nullable=False, index=True
    )
    submitted_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    # The published post. For influencer marketing this IS the deliverable —
    # the work lives on Instagram or TikTok, not in a file — so a URL is the
    # primary field and the attachments below are the supporting evidence.
    # Nullable because a submission may be screenshots only; the service
    # refuses one that is BOTH empty of a link and empty of attachments.
    link_url: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default=SUBMITTED, nullable=False)
    # What the brand wants changed. Required by the service when requesting
    # changes: "redo it" with no reason is a round trip that teaches the
    # creator nothing and comes straight back.
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class DeliverableAttachment(Base):
    """A file offered as proof of the work, pointing at a media_assets row.

    It carries no bytes of its own, exactly like DisputeAttachment. There is
    already a working upload with an owner and a content type
    (POST /profiles/{user_id}/media) and a serving route
    (GET /profiles/media/{id}); a deliverables-only image store would be a
    second upload path, a second size limit and a second thing to move to
    object storage later, to hold the same JPEGs.
    """

    __tablename__ = "deliverable_attachments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("deliverable_submissions.id"), nullable=False, index=True
    )
    media_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

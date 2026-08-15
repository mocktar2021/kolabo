"""Submitting completed work, and the brand's answer to it.

THE RULE THIS MODULE ADDS: money follows an accepted deliverable. Releasing an
escrow used to be a bare "confirm delivery" button that recorded no delivery.
Here, approving a submission is what releases it — one act, in one transaction,
with a row saying what was approved and by whom.

WHAT IT DELIBERATELY DOES NOT DO. It does not replace the dispute path. A brand
that thinks the work is wrong has two different acts available and they mean
different things: REQUEST CHANGES is "do it again", the escrow stays held and
nobody is accused of anything; a DISPUTE is a claim on the money, freezes it and
starts a clock towards an admin. Collapsing them would make every rejected first
draft a formal case, which is how a marketplace's support desk gets priced off
the number of disagreements rather than the number of real failures — the same
argument payments/disputes.py makes for its response window.

DEPENDENCY DIRECTION. This module reads contracts.models, payments.models and
payments.service, and NOTHING imports it back except payments.service, which
takes deliverables.MODELS ONLY (for the auto-release rule). deliverables.models
imports nothing but Base, so the graph stays acyclic. See the note at the top of
models.py, and contracts/cancellation.py for the same arrangement viewed from
the other side.
"""
from datetime import timedelta

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.modules.campaigns import completion
from app.modules.campaigns import models as campaigns
from app.modules.contracts import models as contracts
from app.modules.deliverables import models
from app.modules.notifications.service import notify
from app.modules.payments import models as payments
from app.modules.payments import service as payments_service
from app.modules.profiles.models import MediaAsset

# EVERY REFUSAL IN THIS MODULE CARRIES A CODE (app.core.errors.AppError), which
# makes this the first module converted off bare HTTPException. Deliverables
# went first because its refusals are the ones a creator is most likely to hit
# while money is already in escrow — "the brand has not answered yet", "this
# escrow is no longer held" — and reading those in a language you do not speak,
# about your own unpaid work, is the worst version of the problem.
#
# The English `detail` is unchanged in every case below. It is not a leftover:
# it is the fallback for a client that has not learned the code, and it is what
# a log shows. What is new is only the code beside it.

# Proof is a handful of screenshots, not an album. The same ceiling disputes
# put on evidence, and for the same reason: it keeps one request from pulling a
# hundred blobs into a payload.
MAX_ATTACHMENTS = 10

# A note is optional, but a long one is a document. Only a ceiling here — there
# is no floor, because "posted, link above" is a perfectly good note and the
# link carries the substance.
MAX_NOTE_CHARS = 4000

EMPTY_DETAIL = (
    "A submission needs the link to the published post, a file, or both. "
    "Send what the brand is meant to look at."
)

NOT_FUNDED_DETAIL = (
    "This contract has no money in escrow yet, so there is nothing to deliver "
    "against. Work is submitted once the brand has funded it."
)

OPEN_ALREADY_DETAIL = (
    "You have already submitted work on this contract and the brand has not "
    "answered yet. Wait for their review, or withdraw the submission first."
)


def _media_url(media_id: str) -> str:
    """The same URL shape profiles.service._media_url builds."""
    return f"/profiles/media/{media_id}"


def _checked_media(db: Session, owner_user_id: str, media_ids) -> list[str]:
    """Attachments that exist and that the person attaching them owns.

    The ownership check is the point, exactly as it is in disputes: media ids
    are opaque but still guessable by enumeration, and attaching somebody
    else's would show a private image to the other party and to any admin who
    later reads the case. 403 rather than 404 because the caller is a party
    here and the refusal is about the image, not about the contract.

    Deliberately a local copy of the rule rather than an import from
    payments.disputes: the two guard different tables with different ceilings,
    and pointing this module at the dispute module for a helper would put a
    dependency between two features that have nothing else to say to each
    other. The rule is short enough that stating it twice is cheaper than that
    coupling.
    """
    # dict.fromkeys rather than set(): duplicates drop out and the creator's
    # ordering survives, so the proof reads in the order they picked it.
    ids = list(dict.fromkeys(media_ids or []))
    if not ids:
        return []
    if len(ids) > MAX_ATTACHMENTS:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="deliverable_attachments_max",
            detail=f"At most {MAX_ATTACHMENTS} files can be attached.",
            # The ceiling travels as a number so the translated sentence can
            # put it wherever that language puts it, rather than either
            # language hard-coding a 10 that then drifts from the constant.
            values={"max": MAX_ATTACHMENTS},
        )
    found = {
        asset.id: asset for asset in db.query(MediaAsset).filter(MediaAsset.id.in_(ids)).all()
    }
    for media_id in ids:
        asset = found.get(media_id)
        if asset is None:
            raise AppError(
                status.HTTP_404_NOT_FOUND,
                code="deliverable_attachment_not_found",
                detail="Attachment not found",
            )
        if asset.owner_user_id != owner_user_id:
            raise AppError(
                status.HTTP_403_FORBIDDEN,
                code="deliverable_attachment_not_yours",
                detail="You can only attach files you uploaded",
            )
    return ids


def _load_contract(db: Session, contract_id: str) -> contracts.Contract:
    contract = db.query(contracts.Contract).filter(contracts.Contract.id == contract_id).first()
    if contract is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="deliverable_contract_not_found",
            detail="Contract not found",
        )
    return contract


def _require_party(contract: contracts.Contract, user_id: str) -> None:
    if user_id not in (contract.business_user_id, contract.influencer_user_id):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="deliverable_not_a_party",
            detail="Not a party to this contract",
        )


def _escrow_for(db: Session, contract_id: str) -> payments.Escrow | None:
    """The escrow on a contract, if it has been funded. At most one: the
    column is UNIQUE."""
    return (
        db.query(payments.Escrow).filter(payments.Escrow.contract_id == contract_id).first()
    )


def open_submission_for_contract(db: Session, contract_id: str):
    """The attempt the brand still owes an answer on, if there is one.

    A contract carries several submissions over its life — changes requested,
    withdrawn, then the one that was accepted — but at most one open at a
    time. Anything that acts on "the submission" of a contract means this one,
    and asking by contract_id alone would hand back whichever row the database
    returned first. disputes.open_dispute_for_escrow is the same helper for
    the same reason.
    """
    return (
        db.query(models.DeliverableSubmission)
        .filter(
            models.DeliverableSubmission.contract_id == contract_id,
            models.DeliverableSubmission.status.in_(models.OPEN_STATUSES),
        )
        .order_by(models.DeliverableSubmission.created_at.desc())
        .first()
    )


def _attachments_for(db: Session, submission_ids) -> dict:
    """Serving urls grouped by submission id, in one query rather than one per
    row — a contract with four attempts is otherwise four extra round trips to
    render one panel."""
    ids = list(submission_ids)
    if not ids:
        return {}
    rows = (
        db.query(models.DeliverableAttachment)
        .filter(models.DeliverableAttachment.submission_id.in_(ids))
        .order_by(models.DeliverableAttachment.created_at.asc())
        .all()
    )
    grouped: dict = {}
    for row in rows:
        grouped.setdefault(row.submission_id, []).append(_media_url(row.media_id))
    return grouped


def _out(submission: models.DeliverableSubmission, attachments: list[str] | None = None) -> dict:
    return {
        "id": submission.id,
        "contract_id": submission.contract_id,
        "submitted_by_user_id": submission.submitted_by_user_id,
        "link_url": submission.link_url,
        "note": submission.note,
        "status": submission.status,
        "review_note": submission.review_note,
        "reviewed_by_user_id": submission.reviewed_by_user_id,
        "reviewed_at": submission.reviewed_at,
        "created_at": submission.created_at,
        "attachments": attachments or [],
    }


def _campaign_title(db: Session, campaign_id: str) -> str | None:
    campaign = (
        db.query(campaigns.Campaign).filter(campaigns.Campaign.id == campaign_id).first()
    )
    return campaign.title if campaign is not None else None


def submit(db: Session, actor_user_id: str, payload) -> dict:
    """The creator hands in the work, and the brand's review clock starts.

    ONLY THE CREATOR, and only against a SIGNED, FUNDED contract. Delivering
    into an unfunded contract would be the creator doing the work before the
    money is at the provider, which is precisely the position escrow exists to
    keep them out of.

    ONE OPEN ATTEMPT AT A TIME. A second hand-in while the first is unanswered
    would give the brand two things to review and no way to say which one it
    approved — and the approval releases money, so "which one" is not a
    cosmetic question. A creator with more to add withdraws and resubmits.

    THE CLOCK MOVES HERE, and this is the change with real consequences for
    money. due_release_at was set at FUNDING (held_at + auto_release_days),
    which meant the brand's review window started before there was anything to
    review, and an escrow auto-released seven days after funding whether or not
    the creator had delivered anything at all. Anchoring it to the submission
    makes auto-release mean what it always should have: the brand had N days to
    look at delivered work and did not object. Paired with the rule in
    payments.service.run_due_auto_releases — an escrow with no open submission
    does not auto-release at all — un-delivered money now waits instead of
    paying itself out.
    """
    contract = _load_contract(db, payload.contract_id)
    _require_party(contract, actor_user_id)
    if actor_user_id != contract.influencer_user_id:
        # 403 rather than 400: they are a party, they simply have no standing
        # to deliver — the brand is the buyer, not the supplier.
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="deliverable_submit_creator_only",
            detail="Only the creator on this contract can submit work.",
        )
    if contract.status != contracts.SIGNED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="deliverable_contract_not_signed",
            detail="Work can only be submitted on a fully signed contract.",
        )

    escrow = _escrow_for(db, contract.id)
    if escrow is None:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="deliverable_escrow_not_funded",
            detail=NOT_FUNDED_DETAIL,
        )
    if escrow.status != payments.HELD:
        # Released, refunded or frozen in a dispute. None of the three is a
        # state in which a new hand-in means anything, and answering 200 would
        # tell a creator their work was filed against money that has already
        # moved.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="deliverable_escrow_not_held",
            detail="This escrow is no longer held, so work cannot be submitted against it.",
        )

    # Checked before the payload is validated, so a double submit is told the
    # real obstacle rather than being asked to fix a link it already sent.
    if open_submission_for_contract(db, contract.id) is not None:
        raise AppError(
            status.HTTP_409_CONFLICT,
            code="deliverable_submission_open_already",
            detail=OPEN_ALREADY_DETAIL,
        )

    link_url = (payload.link_url or "").strip() or None
    note = (payload.note or "").strip() or None
    if note is not None and len(note) > MAX_NOTE_CHARS:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="deliverable_note_too_long",
            detail=f"A note is at most {MAX_NOTE_CHARS} characters.",
            values={"max": MAX_NOTE_CHARS},
        )
    media_ids = _checked_media(db, actor_user_id, payload.media_ids)
    if link_url is None and not media_ids:
        # A submission that points at nothing is not a submission. Refused
        # rather than stored, because the brand's next action on it releases
        # money.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="deliverable_submission_empty",
            detail=EMPTY_DETAIL,
        )

    submission = models.DeliverableSubmission(
        contract_id=contract.id,
        submitted_by_user_id=actor_user_id,
        link_url=link_url,
        note=note,
        status=models.SUBMITTED,
    )
    db.add(submission)
    db.flush()
    for media_id in media_ids:
        db.add(
            models.DeliverableAttachment(submission_id=submission.id, media_id=media_id)
        )

    # The review window opens now. Reset on every submission, so revised work
    # earns the brand a fresh look rather than inheriting whatever was left of
    # the last one.
    escrow.due_release_at = models.utcnow() + timedelta(days=settings.review_window_days)

    title = _campaign_title(db, contract.campaign_id)
    notify(
        db,
        contract.business_user_id,
        "deliverable",
        f"Work was submitted for review on {title}." if title else "Work was submitted for review.",
        link=f"/contracts/{contract.id}",
        params=(
            {"key": "deliverable_submitted", "campaign": title}
            if title
            else {"key": "deliverable_submitted_generic"}
        ),
    )
    db.commit()
    db.refresh(submission)
    return _out(submission, [_media_url(mid) for mid in media_ids])


def list_for_contract(db: Session, user_id: str, contract_id: str) -> list[dict]:
    """Every attempt on one contract, newest first. Either party.

    The whole history and not just the live one: "they asked for changes twice
    and then approved it" is the story both sides argue from, and it is the
    record an admin reads if this ever becomes a dispute.
    """
    contract = _load_contract(db, contract_id)
    _require_party(contract, user_id)
    rows = (
        db.query(models.DeliverableSubmission)
        .filter(models.DeliverableSubmission.contract_id == contract_id)
        .order_by(models.DeliverableSubmission.created_at.desc())
        .all()
    )
    by_submission = _attachments_for(db, [r.id for r in rows])
    return [_out(r, by_submission.get(r.id, [])) for r in rows]


def _load_submission(db: Session, submission_id: str):
    submission = (
        db.query(models.DeliverableSubmission)
        .filter(models.DeliverableSubmission.id == submission_id)
        .first()
    )
    if submission is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="deliverable_submission_not_found",
            detail="Submission not found",
        )
    return submission, _load_contract(db, submission.contract_id)


def _require_reviewable(submission, actor_user_id: str, contract: contracts.Contract) -> None:
    """The brand, on an attempt nobody has answered yet."""
    _require_party(contract, actor_user_id)
    if actor_user_id != contract.business_user_id:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="deliverable_review_business_only",
            detail="Only the business on this contract can review submitted work.",
        )
    if submission.status != models.SUBMITTED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="deliverable_already_answered",
            detail="This submission has already been answered.",
        )


def approve(db: Session, actor_user_id: str, submission_id: str) -> dict:
    """The brand accepts the work, and the escrow is released in the same breath.

    THIS IS THE POINT OF THE MODULE. Approval and payment are one act and one
    transaction: there is no state in which the work is accepted and the money
    is not on its way, and no release that fails to record what it paid for.

    The release goes through payments.service._release, the SAME path the
    standalone confirm-delivery button and the auto-release sweep use — so
    commission, the payout, the escrow event and the referral hook are
    computed in exactly one place. Duplicating any of that here would be a
    second way for money to move, and the second way is always the one that
    drifts.
    """
    submission, contract = _load_submission(db, submission_id)
    _require_reviewable(submission, actor_user_id, contract)

    escrow = _escrow_for(db, contract.id)
    if escrow is None:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="deliverable_escrow_not_funded",
            detail=NOT_FUNDED_DETAIL,
        )
    if escrow.status != payments.HELD:
        # Most likely a dispute froze it between the submission and this
        # click, or the sweep auto-released it. Either way the money is no
        # longer this button's to move.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="deliverable_release_escrow_not_held",
            detail="This escrow is not held, so it cannot be released.",
        )

    # The one definition of what approving a hand-in writes (status, reviewer,
    # timestamp) — shared with the standalone confirm-delivery button, which
    # approves the open submission this same way before it releases. See
    # deliverables.models.mark_approved.
    models.mark_approved(submission, actor_user_id)
    campaign_id = escrow.campaign_id
    # Notifies both parties (escrow_released_*) and awards referral credit.
    payments_service._release(db, escrow, actor_user_id)
    db.commit()
    # The brand approving the last outstanding piece of work is the commonest
    # way a brief finishes. After the commit, off a local id: the commit
    # expires the escrow row.
    completion.maybe_complete_campaign(db, campaign_id)
    db.refresh(submission)
    by_submission = _attachments_for(db, [submission.id])
    return _out(submission, by_submission.get(submission.id, []))


def request_changes(db: Session, actor_user_id: str, submission_id: str, payload) -> dict:
    """The brand wants it redone. The money does not move.

    A note is REQUIRED. "Rejected" with no reason is a round trip that teaches
    the creator nothing, comes back the same, and is the fastest route to the
    dispute this whole path exists to avoid.

    The escrow is untouched — still held, still on its schedule — and the
    attempt closes as changes_requested. Because the auto-release sweep only
    counts escrows with an OPEN submission, asking for changes also stops the
    clock: work the brand has rejected cannot quietly auto-pay while the
    creator is redoing it.
    """
    submission, contract = _load_submission(db, submission_id)
    _require_reviewable(submission, actor_user_id, contract)

    note = (payload.note or "").strip()
    if not note:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="deliverable_changes_need_note",
            detail="Say what needs to change, so the creator can fix it.",
        )
    if len(note) > MAX_NOTE_CHARS:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="deliverable_note_too_long",
            detail=f"A note is at most {MAX_NOTE_CHARS} characters.",
            values={"max": MAX_NOTE_CHARS},
        )

    submission.status = models.CHANGES_REQUESTED
    submission.review_note = note
    submission.reviewed_by_user_id = actor_user_id
    submission.reviewed_at = models.utcnow()
    notify(
        db,
        contract.influencer_user_id,
        "deliverable",
        "The brand asked for changes to the work you submitted.",
        link=f"/contracts/{contract.id}",
        params={"key": "deliverable_changes_requested"},
    )
    db.commit()
    db.refresh(submission)
    by_submission = _attachments_for(db, [submission.id])
    return _out(submission, by_submission.get(submission.id, []))


def withdraw(db: Session, actor_user_id: str, submission_id: str) -> dict:
    """The creator pulls a submission back before anybody has reviewed it.

    ONLY THE SUBMITTER, and only while it is unanswered: once the brand has
    approved it the money has moved, and once they have asked for changes the
    attempt is already closed. This exists so a creator who posted the wrong
    link is not stuck waiting for a rejection to fix it.

    Withdrawing leaves the escrow held and, since the sweep only counts open
    submissions, stops the review clock — which is right: there is nothing in
    front of the brand to review.
    """
    submission, contract = _load_submission(db, submission_id)
    _require_party(contract, actor_user_id)
    if submission.submitted_by_user_id != actor_user_id:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="deliverable_withdraw_own_only",
            detail="Only the creator who submitted this work can withdraw it",
        )
    if submission.status != models.SUBMITTED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="deliverable_already_answered",
            detail="This submission has already been answered.",
        )
    submission.status = models.WITHDRAWN
    db.commit()
    db.refresh(submission)
    by_submission = _attachments_for(db, [submission.id])
    return _out(submission, by_submission.get(submission.id, []))

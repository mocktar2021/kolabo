"""Raising a dispute: what it freezes, and who is allowed to answer first.

THE PARTIES GET THE FIRST 72 HOURS. Raising a dispute freezes the escrow and
opens a RESPONSE WINDOW rather than filing a ticket. The other party is
notified and can answer or settle it directly, and only after the window
closes does the case reach an admin. Most disputes are misunderstandings — a
deliverable posted to the wrong handle, a file the buyer never saw — and
routing every disagreement straight to a human does not survive volume growth:
it prices a marketplace's support desk off the number of arguments rather than
off the number of real failures.

WHY THIS IS ITS OWN MODULE. service.py already carries funding, release, the
auto-release sweep and the referral hook, all of which move money on the happy
path. Disputes are a second lifecycle with their own states, their own
authorisation and their own thread, and bolting them onto that file would make
the most dangerous module in the codebase the biggest one too. The dependency
runs one way — disputes -> service — so nothing here can be imported into a
cycle.
"""
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.notifications.service import notify
from app.modules.payments import models
from app.modules.payments import service as payments_service
from app.modules.profiles.models import MediaAsset

# A statement short enough to be typed by accident says nothing an admin can
# act on ("bad"), and one longer than a few pages is a document, not a
# statement. Both bounds answer 400 naming the rule rather than a 422 field
# error, for the reason OrderIn spells out: a client can act on the first.
MIN_STATEMENT_CHARS = 10
MAX_STATEMENT_CHARS = 4000

# Evidence is screenshots, not an album. Ten is more than any real case has
# needed and it keeps one request from pulling a hundred blobs into a payload.
MAX_EVIDENCE_IMAGES = 10


def _media_url(media_id: str) -> str:
    """The same URL shape profiles.service._media_url builds.

    One media route serves every surface that shows an image, so evidence
    needs no serving code of its own.
    """
    return f"/profiles/media/{media_id}"


def load_escrow(db: Session, escrow_id: str) -> models.Escrow:
    escrow = db.query(models.Escrow).filter(models.Escrow.id == escrow_id).first()
    if escrow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escrow not found")
    return escrow


def parties(escrow: models.Escrow) -> tuple[str, str]:
    return escrow.business_user_id, escrow.influencer_user_id


def other_party(escrow: models.Escrow, user_id: str) -> str:
    return (
        escrow.influencer_user_id
        if user_id == escrow.business_user_id
        else escrow.business_user_id
    )


def require_party(escrow: models.Escrow, user_id: str) -> None:
    if user_id not in parties(escrow):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this escrow"
        )


def _checked_reason(reason: str) -> str:
    if reason not in models.DISPUTE_REASONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"reason must be one of: {', '.join(models.DISPUTE_REASONS)}",
        )
    return reason


def _checked_statement(statement: str | None) -> str:
    text = (statement or "").strip()
    if len(text) < MIN_STATEMENT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Say what went wrong in at least {MIN_STATEMENT_CHARS} characters.",
        )
    if len(text) > MAX_STATEMENT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A statement is at most {MAX_STATEMENT_CHARS} characters.",
        )
    return text


def checked_media(db: Session, owner_user_id: str, media_ids) -> list[str]:
    """Evidence images that exist and that the person attaching them owns.

    The ownership check is the point. media_assets ids are opaque but they are
    still guessable-by-enumeration in a way a private image should never rely
    on, and attaching someone else's would LEAK IT INTO THE DISPUTE: the other
    party and every admin who ever reads the case would be shown a picture its
    owner never offered. 403 rather than 404 because the caller is a party
    here and the refusal is about the image, not about the case.
    """
    # dict.fromkeys rather than set(): duplicates are dropped and the buyer's
    # ordering survives, so the evidence reads in the order they picked it.
    ids = list(dict.fromkeys(media_ids or []))
    if not ids:
        return []
    if len(ids) > MAX_EVIDENCE_IMAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At most {MAX_EVIDENCE_IMAGES} images can be attached.",
        )
    found = {
        asset.id: asset
        for asset in db.query(MediaAsset).filter(MediaAsset.id.in_(ids)).all()
    }
    for media_id in ids:
        asset = found.get(media_id)
        if asset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Evidence image not found"
            )
        if asset.owner_user_id != owner_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only attach images you uploaded",
            )
    return ids


def dispute_out(db: Session, dispute: models.Dispute, escrow: models.Escrow | None = None) -> dict:
    rows = (
        db.query(models.DisputeAttachment)
        .filter(
            models.DisputeAttachment.dispute_id == dispute.id,
            models.DisputeAttachment.message_id.is_(None),
        )
        .order_by(models.DisputeAttachment.created_at.asc())
        .all()
    )
    out = {
        "id": dispute.id,
        "escrow_id": dispute.escrow_id,
        "opened_by_user_id": dispute.opened_by_user_id,
        "reason": dispute.reason,
        "statement": dispute.statement,
        "status": dispute.status,
        "respond_by": dispute.respond_by.isoformat(),
        "resolved_at": dispute.resolved_at.isoformat() if dispute.resolved_at else None,
        "resolution": dispute.resolution,
        "released_amount": dispute.released_amount,
        "refunded_amount": dispute.refunded_amount,
        "resolved_by": dispute.resolved_by,
        "attachments": [_media_url(row.media_id) for row in rows],
    }
    if escrow is not None:
        out["escrow"] = payments_service._out(escrow)
    return out


def raise_dispute(db: Session, actor_user_id: str, escrow_id: str, payload) -> dict:
    """Freeze the escrow, record what went wrong, and start the clock.

    Only the two parties may raise one: a dispute is a claim on money held
    between them, and nobody else has one to make.

    Only while the escrow is HELD. A released escrow has already been paid out
    at the provider and a refunded one already returned — there is nothing
    left to freeze, and answering 200 would tell a creator their payout was
    stopped when it was not. 400 rather than 409 because the request is about
    a state the escrow will never return to.
    """
    escrow = load_escrow(db, escrow_id)
    require_party(escrow, actor_user_id)
    if escrow.status != models.HELD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only a held escrow can be disputed",
        )
    # One dispute per escrow, matched by the UNIQUE column behind it. A second
    # one would fork the thread and give an admin two half-cases over the same
    # money; a party who has more to say adds a message to the open one.
    existing = (
        db.query(models.Dispute).filter(models.Dispute.escrow_id == escrow.id).first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This escrow already has a dispute",
        )

    reason = _checked_reason(payload.reason)
    statement = _checked_statement(payload.statement)
    media_ids = checked_media(db, actor_user_id, payload.media_ids)

    now = models.utcnow()
    dispute = models.Dispute(
        escrow_id=escrow.id,
        opened_by_user_id=actor_user_id,
        reason=reason,
        statement=statement,
        status=models.AWAITING_RESPONSE,
        respond_by=now + timedelta(hours=settings.dispute_response_hours),
    )
    db.add(dispute)
    db.flush()
    for media_id in media_ids:
        db.add(models.DisputeAttachment(dispute_id=dispute.id, media_id=media_id))

    escrow.status = models.DISPUTED
    payments_service._event(db, escrow, actor_user_id, "disputed")

    # The other party is told they have a window and that it is theirs to use.
    # The whole point of the design is that this message, not an admin, is
    # what usually ends the dispute.
    notify(
        db,
        other_party(escrow, actor_user_id),
        "dispute",
        f"A dispute was opened on your escrow ({reason}). You have "
        f"{settings.dispute_response_hours} hours to answer or resolve it before "
        "it goes to the Kolabo team.",
    )
    notify(
        db,
        actor_user_id,
        "dispute",
        "Your dispute was opened and the escrow is frozen. The other party has "
        f"{settings.dispute_response_hours} hours to answer.",
    )
    db.commit()
    db.refresh(dispute)
    db.refresh(escrow)
    return dispute_out(db, dispute, escrow)

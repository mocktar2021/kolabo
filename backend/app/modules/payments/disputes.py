"""Raising a dispute, answering it, and the two ways it reaches an admin.

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
from sqlalchemy import or_
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

# The two states in which a dispute is still a live conversation. Resolved and
# withdrawn cases are closed records: they are read, not written to — and they
# do not stand in the way of a new dispute on the same escrow, which is why
# this tuple, not a UNIQUE column, is what "one dispute per escrow" means.
OPEN_STATUSES = (models.AWAITING_RESPONSE, models.AWAITING_ADMIN)


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


def load_dispute(db: Session, dispute_id: str) -> tuple[models.Dispute, models.Escrow]:
    dispute = db.query(models.Dispute).filter(models.Dispute.id == dispute_id).first()
    if dispute is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")
    return dispute, load_escrow(db, dispute.escrow_id)


def open_dispute_for_escrow(db: Session, escrow_id: str) -> models.Dispute | None:
    """The live dispute on an escrow, if it has one.

    An escrow can carry several dispute rows over its life — withdrawn ones,
    resolved ones — but at most one open at a time. Anything that acts on "the
    dispute" of an escrow means this one, and asking by escrow_id alone would
    hand back whichever row the database happened to return first.
    """
    return (
        db.query(models.Dispute)
        .filter(
            models.Dispute.escrow_id == escrow_id,
            models.Dispute.status.in_(OPEN_STATUSES),
        )
        .order_by(models.Dispute.created_at.desc())
        .first()
    )


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


def _checked_body(body: str | None) -> str:
    """A message has no floor beyond being something. "Sorry, reposted it" is
    a perfectly good end to a dispute and would not clear the statement's ten
    characters; only the ceiling is shared.
    """
    text = (body or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A message needs a body."
        )
    if len(text) > MAX_STATEMENT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A message is at most {MAX_STATEMENT_CHARS} characters.",
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


def _attachments(db: Session, dispute_id: str, opening: bool) -> dict:
    """Evidence urls, keyed by message id — or the opening statement's list."""
    query = db.query(models.DisputeAttachment).filter(
        models.DisputeAttachment.dispute_id == dispute_id
    )
    if opening:
        query = query.filter(models.DisputeAttachment.message_id.is_(None))
    else:
        query = query.filter(models.DisputeAttachment.message_id.isnot(None))
    rows = query.order_by(models.DisputeAttachment.created_at.asc()).all()
    if opening:
        return {None: [_media_url(row.media_id) for row in rows]}
    grouped: dict = {}
    for row in rows:
        grouped.setdefault(row.message_id, []).append(_media_url(row.media_id))
    return grouped


def _messages_out(db: Session, dispute_id: str) -> list[dict]:
    by_message = _attachments(db, dispute_id, opening=False)
    rows = (
        db.query(models.DisputeMessage)
        .filter(models.DisputeMessage.dispute_id == dispute_id)
        .order_by(models.DisputeMessage.created_at.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "author_user_id": row.author_user_id,
            "body": row.body,
            "created_at": row.created_at.isoformat(),
            "attachments": by_message.get(row.id, []),
        }
        for row in rows
    ]


def dispute_out(
    db: Session,
    dispute: models.Dispute,
    escrow: models.Escrow | None = None,
    messages: bool = False,
) -> dict:
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
        "created_at": dispute.created_at.isoformat(),
        "attachments": _attachments(db, dispute.id, opening=True)[None],
    }
    if escrow is not None:
        out["escrow"] = payments_service._out(escrow)
    if messages:
        out["messages"] = _messages_out(db, dispute.id)
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
    # One OPEN dispute per escrow — not one ever. A second live case would
    # fork the thread and give an admin two half-cases over the same money, so
    # a party with more to say adds a message to the open one. But a withdrawn
    # or resolved case blocks nothing: the same contract can go wrong twice,
    # and two people settling a first misunderstanding themselves must not
    # cost them the only claim their escrow was ever allowed.
    existing = open_dispute_for_escrow(db, escrow.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This escrow already has an open dispute",
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


def _escalate(db: Session, dispute: models.Dispute, escrow: models.Escrow, why: str) -> None:
    dispute.status = models.AWAITING_ADMIN
    for user_id in parties(escrow):
        notify(db, user_id, "dispute", why)


def _maybe_escalate_after_message(
    db: Session, dispute: models.Dispute, escrow: models.Escrow
) -> None:
    """Both sides have now posted, so stop waiting out the clock.

    The window exists for one reason: to give the two of them room to settle
    it without a stranger reading their contract. Once BOTH have spoken in the
    thread and the money is still frozen, that room has been used and did not
    work — sitting on the case for the rest of the 72 hours only delays the
    queue for money somebody is not being paid.

    The opening statement deliberately does not count as the opener "speaking"
    here. Every dispute has one, so counting it would escalate on the other
    party's very first reply — which is exactly the reply that most often ends
    the whole thing.
    """
    if dispute.status != models.AWAITING_RESPONSE:
        return
    authors = {
        row[0]
        for row in db.query(models.DisputeMessage.author_user_id)
        .filter(models.DisputeMessage.dispute_id == dispute.id)
        .distinct()
        .all()
    }
    if set(parties(escrow)) <= authors:
        _escalate(
            db,
            dispute,
            escrow,
            "Both parties have answered the dispute, so it has gone to the "
            "Kolabo team for a decision.",
        )


def post_message(db: Session, actor_user_id: str, dispute_id: str, payload) -> dict:
    """Either party adds to the thread, with optional evidence.

    Allowed while awaiting_admin as well as during the window. An admin
    reading the case benefits from both sides continuing to explain: half the
    facts in a dispute arrive after somebody has been asked a question, and
    freezing the thread the moment it queues would push that conversation to
    email, where the decision cannot be audited from.
    """
    dispute, escrow = load_dispute(db, dispute_id)
    require_party(escrow, actor_user_id)
    if dispute.status not in OPEN_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This dispute is closed",
        )

    body = _checked_body(payload.body)
    media_ids = checked_media(db, actor_user_id, payload.media_ids)

    message = models.DisputeMessage(
        dispute_id=dispute.id, author_user_id=actor_user_id, body=body
    )
    db.add(message)
    db.flush()
    for media_id in media_ids:
        db.add(
            models.DisputeAttachment(
                dispute_id=dispute.id, message_id=message.id, media_id=media_id
            )
        )
    db.flush()

    notify(
        db,
        other_party(escrow, actor_user_id),
        "dispute",
        "The other party replied on your disputed escrow.",
    )
    _maybe_escalate_after_message(db, dispute, escrow)
    db.commit()
    db.refresh(message)
    db.refresh(dispute)
    return {
        "id": message.id,
        "dispute_id": dispute.id,
        "author_user_id": message.author_user_id,
        "body": message.body,
        "created_at": message.created_at.isoformat(),
        "attachments": [_media_url(mid) for mid in media_ids],
        "dispute_status": dispute.status,
    }


def withdraw_dispute(db: Session, actor_user_id: str, dispute_id: str) -> dict:
    """The party who raised it takes it back, and the escrow goes back to held.

    ONLY THE OPENER. The other party answering "you are wrong" is not the same
    act as the claimant dropping the claim, and letting them close it would
    let the accused dismiss the accusation. 403, not 400: they are a party,
    they simply have no standing to do this.

    THE ESCROW CAN BE DISPUTED AGAIN AFTERWARDS. Withdrawing closes this case,
    not the escrow's right to ever have one. escrow_id used to be UNIQUE,
    which made a withdrawal permanent in the worst direction: a brand and a
    creator who talked a first misunderstanding out had, by doing the right
    thing, spent the only dispute their contract was allowed — and if the work
    then genuinely failed, the brand's money was frozen behind nothing it
    could raise. The 409 in raise_dispute is scoped to the OPEN set instead,
    so settling amicably costs the parties nothing.

    THE AUTO-RELEASE CLOCK. due_release_at is set at funding to held_at + N
    days and run_due_auto_releases only ever looks at HELD escrows, so a
    freeze does not stop the deadline — it just hides it. If the deadline slid
    past while the money was frozen, handing the escrow back untouched would
    auto-release it on the very next sweep, and the business would lose the
    review time it still had left to a dispute that was WITHDRAWN. So a
    deadline that has already passed is pushed out by exactly how long the
    dispute held the money. A deadline still in the future is left alone:
    nothing was taken from anybody, and moving it would quietly extend the
    creator's wait for their payout.
    """
    dispute, escrow = load_dispute(db, dispute_id)
    if dispute.opened_by_user_id != actor_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the party who raised the dispute can withdraw it",
        )
    if dispute.status not in OPEN_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This dispute is closed"
        )

    now = models.utcnow()
    frozen_for = now - dispute.created_at
    if escrow.due_release_at <= now:
        escrow.due_release_at = escrow.due_release_at + frozen_for

    dispute.status = models.DISPUTE_WITHDRAWN
    dispute.resolved_at = now
    dispute.resolution = "Withdrawn by the party who raised it."
    escrow.status = models.HELD
    payments_service._event(db, escrow, actor_user_id, "dispute_withdrawn")
    for user_id in parties(escrow):
        notify(
            db,
            user_id,
            "dispute",
            "The dispute was withdrawn. The escrow is held again and back on its "
            "normal release schedule.",
        )
    db.commit()
    db.refresh(dispute)
    db.refresh(escrow)
    return dispute_out(db, dispute, escrow)


def escalate_stale_disputes(db: Session, now=None) -> int:
    """Move disputes nobody answered in time into the admin queue.

    Admin-triggered and on demand, exactly like run_due_auto_releases and
    campaigns.orders.expire_stale_orders. THIS IS NOW THE THIRD JOB WAITING
    FOR A SCHEDULER — the point at which "we will add one later" stops being
    free, because this one is the only thing standing between a party who
    stayed silent and money that stays frozen forever. Whoever adds the
    scheduler gets all three unchanged; until then it needs a human to press
    it, which is worth writing down rather than discovering.

    Only awaiting_response rows are touched. A case already in the queue does
    not move, and a resolved or withdrawn one is a closed record.
    """
    now = now or models.utcnow()
    stale = (
        db.query(models.Dispute)
        .filter(
            models.Dispute.status == models.AWAITING_RESPONSE,
            models.Dispute.respond_by <= now,
        )
        .all()
    )
    for dispute in stale:
        escrow = (
            db.query(models.Escrow)
            .filter(models.Escrow.id == dispute.escrow_id)
            .first()
        )
        if escrow is None:
            continue
        _escalate(
            db,
            dispute,
            escrow,
            "The response window on your disputed escrow has closed. The Kolabo "
            "team will now review it and decide.",
        )
    db.commit()
    return len(stale)


def get_dispute(db: Session, viewer_id: str, is_admin: bool, dispute_id: str) -> dict:
    """The whole case: the claim, the thread with its evidence, the escrow.

    Either party or an admin. Nobody else, ever — a dispute contains both
    sides' account of a private commercial agreement, and the statement is
    written by somebody who expects two readers and a referee.
    """
    dispute, escrow = load_dispute(db, dispute_id)
    if not is_admin:
        require_party(escrow, viewer_id)
    return dispute_out(db, dispute, escrow, messages=True)


def list_my_disputes(db: Session, user_id: str) -> list[dict]:
    """Every dispute the caller is a party to, newest first.

    One join rather than a lookup per row: the parties live on the escrow, not
    on the dispute, and a per-row version of this is how a list of ten cases
    becomes twenty round trips.
    """
    rows = (
        db.query(models.Dispute, models.Escrow)
        .join(models.Escrow, models.Escrow.id == models.Dispute.escrow_id)
        .filter(
            or_(
                models.Escrow.business_user_id == user_id,
                models.Escrow.influencer_user_id == user_id,
            )
        )
        .order_by(models.Dispute.created_at.desc())
        .all()
    )
    return [dispute_out(db, dispute, escrow) for dispute, escrow in rows]

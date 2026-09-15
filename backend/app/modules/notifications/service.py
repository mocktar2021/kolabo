"""Notification logic (Epic D and Epic F).

notify() records an in-app notification and delivers it by email through the
sender interface, addressed to the account's email, which is what an account
is. Critical types (payment, dispute) are always delivered.
Non critical types are delivered unless the user has unsubscribed from that
type. Delivery is synchronous so it goes out immediately, which meets the
"within 1 minute" criterion in KOL-35. The caller commits the transaction.

THE READING SIDE. Everything below notify() exists so a bell and a list can be
drawn, which until now nothing could: there was a list with no cap and no
timestamp and a mark-one-read, and that is not enough to render a badge or to
clear one. A NOTIFICATION IS READABLE BY EXACTLY ONE PERSON — every function
here takes the user id the caller's token resolved to and filters on it, and
there is deliberately no read-one-by-id endpoint for an id to be walked
through.
"""
from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.auth.models import User
from app.modules.notifications import email
from app.modules.notifications.models import Notification, NotificationPreference

CRITICAL_TYPES = {"payment", "dispute"}

# How many notifications one request carries when the caller does not say.
# A bell menu shows a screenful and the rest is history nobody scrolls; an
# uncapped list meanwhile grows for the life of an account, so the oldest and
# most valuable users would have had the slowest bell.
DEFAULT_LIMIT = 50
# The ceiling a caller can ask for. Present so a client cannot turn a paged
# endpoint back into an unpaged one by sending limit=100000, which is the only
# way the cap above could stop meaning anything.
MAX_LIMIT = 200

email_sender: email.Sender = email.default_email_sender


def _muted_types(db: Session, user_id: str) -> list[str]:
    pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
    return list(pref.muted_types) if pref else []


def notify(
    db: Session,
    user_id: str,
    type: str,
    message: str,
    *,
    link: str | None = None,
    params: dict | None = None,
) -> None:
    """Record an in-app notification and email it (subject to muting).

    link and params are keyword-only and both optional, so a call site that has
    not been migrated yet still writes a valid row — it just carries no deep
    link and no localised body, and the client falls back to routeForType and
    to `message`. message stays the source of truth for the EMAIL, which has no
    client to render params and no stored language to render them in.
    """
    db.add(Notification(user_id=user_id, type=type, message=message, link=link, params=params))
    should_email = type in CRITICAL_TYPES or type not in _muted_types(db, user_id)
    if should_email:
        user = db.query(User).filter(User.id == user_id).first()
        # ADDRESSED TO user.email AND NOTHING ELSE. This was
        # `user.email or user.phone`, from when the phone was the identity and
        # an address was an optional extra; the fallback put a phone number
        # into a mail API, which ResendSender had to learn to decline.
        #
        # THE GUARD IS NOT DEFENSIVE PROGRAMMING, it is a state that really
        # exists: accounts registered before the flip have no address, because
        # nothing ever asked them for one, and users.email is nullable for
        # exactly that reason. Such an account still gets the in-app
        # notification — the row above is already written — and simply gets no
        # email, which is the honest outcome when there is nowhere to send one.
        # It is not logged as an error because it is not one; they see it in
        # the bell, and the settings screen is where they fix it.
        #
        # What must never happen is None reaching a sender. LoggingEmailSender
        # would file it in its outbox and ResendSender would post null as a
        # recipient, and neither failure is visible from the call site.
        if user is not None and user.email:
            email_sender.send(user.email, type, message)


def list_notifications(
    db: Session, user_id: str, limit: int = DEFAULT_LIMIT, offset: int = 0
) -> list[dict]:
    """One page of the caller's own notifications, newest first.

    Scoped to the caller and to nobody else. There is no id parameter and no
    endpoint that reads a single notification, so this filter is the entire
    read surface — which is why it is a filter on the token-derived id rather
    than a check made afterwards on rows that were already loaded.

    The secondary sort on id is not cosmetic. created_at is written by the
    application clock, so two notifications raised in the same call — an
    escrow release tells both parties, a contract signature tells both — can
    share a timestamp, and with only one sort key a paged read could show the
    same row twice and skip another. An arbitrary but STABLE tiebreak is what
    makes offset paging safe.

    limit is clamped rather than rejected. A client asking for more than the
    ceiling wants as much as it can have, and a 422 in a bell menu is a blank
    bell; a caller who genuinely needs more pages the rest.
    """
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [
        {
            "id": n.id,
            "type": n.type,
            "message": n.message,
            "link": n.link,
            "params": n.params,
            "is_read": n.is_read,
            "created_at": n.created_at,
        }
        for n in rows
    ]


def unread_count(db: Session, user_id: str) -> dict:
    """How many unread notifications the caller has — the badge, and only it.

    A COUNT rather than a length taken from the list above, because the list
    is capped: deriving the badge from a page would under-report it the moment
    somebody has more unread rows than a page holds, and uncapping the list to
    make that work would mean shipping an entire history to draw a number.
    """
    return {
        "unread": db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read.is_(False))
        .count()
    }


def mark_read(db: Session, user_id: str, notification_id: str) -> dict:
    """Mark one notification read. Only ever your own.

    404 and not 403 for a row belonging to somebody else, deliberately: a 403
    would confirm that the id exists and belongs to someone, which is a fact
    the caller has no standing to learn. "Not found" is what an id that is not
    yours means here.
    """
    n = db.query(Notification).filter(Notification.id == notification_id).first()
    if n is None or n.user_id != user_id:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="notification_not_found",
            detail="Notification not found",
        )
    n.is_read = True
    db.commit()
    return {"id": n.id, "is_read": True}


def mark_all_read(db: Session, user_id: str) -> dict:
    """Clear the whole bell in one request.

    Without this, dismissing a badge of forty is forty round trips, and the
    forty-first notification arriving mid-sweep leaves the badge stuck on a
    number that no longer matches anything. One UPDATE scoped to the caller's
    unread rows, and the count of what it touched comes back so the client can
    settle its badge without asking again.

    Filtered on is_read as well as on the user so the statement only rewrites
    rows that change — re-stamping a thousand already-read rows every time
    somebody taps the bell is work nobody asked for.
    """
    marked = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read.is_(False))
        .update({Notification.is_read: True}, synchronize_session=False)
    )
    db.commit()
    return {"marked": marked}


def set_email_subscription(db: Session, user_id: str, type: str, enabled: bool) -> dict:
    if type in CRITICAL_TYPES and not enabled:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="notification_critical_locked",
            detail="Critical notifications (payment, dispute) cannot be turned off",
        )
    pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
    if pref is None:
        pref = NotificationPreference(user_id=user_id, muted_types=[])
        db.add(pref)
    muted = set(pref.muted_types or [])
    if enabled:
        muted.discard(type)
    else:
        muted.add(type)
    pref.muted_types = sorted(muted)
    db.commit()
    return {"muted_types": pref.muted_types}

"""The two questions every block-aware surface asks, and nothing else.

ONE ANSWER TO "ARE THESE TWO BLOCKED", IN ONE PLACE. Eleven surfaces have to
honour a block: search, the featured strip, the public storefront,
favourites, the cart, invitations, proposals, contract creation and both
message send paths. Eleven copies of the same filter is eleven chances for
one of them to drift, and the one that drifts is the one somebody finds.

WHY THE EFFECT IS SYMMETRIC WHEN THE ROW IS NOT. A block is one person's
decision, but it cannot run in only one direction. If it hid the blocker
from the blocked and no more, the blocked person would still appear in the
blocker's own search results, their own favourites and their own inbox,
which is the single face they pressed the button to stop seeing. So both
helpers here read the pair, never the direction, and the direction is
consulted exactly once: when something has to decide WHICH refusal sentence
to show, which is the enforcement layer's job and not this module's.

TWO SHAPES BECAUSE THERE ARE TWO QUESTIONS. A list endpoint wants every id
it must drop, once, before it filters; a write path wants a yes or no about
one counterparty and should not pay for a set it will look at once.
"""
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.modules.trust_safety.models import Block


def blocked_pair_ids(db: Session, user_id: str) -> set[str]:
    """Every user this one cannot transact with, in either direction.

    For list endpoints: read it once, then filter in memory. An empty set is
    the overwhelmingly common answer and costs one indexed query.

    The caller is never in the returned set. A row where both columns hold
    the same id should not exist (the endpoint layer refuses a self block),
    but a helper that would hide somebody from their own search results if
    one ever did is a helper that fails in a way nobody would guess, so it is
    discarded here rather than assumed away.
    """
    rows = (
        db.query(Block.blocker_user_id, Block.blocked_user_id)
        .filter(or_(Block.blocker_user_id == user_id, Block.blocked_user_id == user_id))
        .all()
    )
    other_ids = {
        blocked if blocker == user_id else blocker
        for blocker, blocked in rows
    }
    other_ids.discard(user_id)
    return other_ids


def block_between(db: Session, user_id: str, other_user_id: str) -> Block | None:
    """The block standing between these two, whichever of them created it.

    Returns the ROW rather than a boolean because the one caller that needs
    the direction needs it from here: a refusal has to say either "you
    blocked this person" or "this person is not accepting contact from you",
    and those are different sentences to a reader who has forgotten which way
    round it was.

    If both directions exist, which of the two comes back is not defined and
    does not matter: either row refuses the action, and the pair being
    mutually blocked makes the direction moot.
    """
    return (
        db.query(Block)
        .filter(
            or_(
                and_(Block.blocker_user_id == user_id, Block.blocked_user_id == other_user_id),
                and_(Block.blocker_user_id == other_user_id, Block.blocked_user_id == user_id),
            )
        )
        .first()
    )


def is_blocked_pair(db: Session, user_id: str, other_user_id: str) -> bool:
    """Yes or no for one pair, for write paths that do not need the reason."""
    return block_between(db, user_id, other_user_id) is not None

"""The questions every block-aware surface asks, and nothing else.

ONE ANSWER TO "ARE THESE TWO BLOCKED", IN ONE PLACE. Eleven surfaces have to
honour a block: search, the featured strip, the public storefront,
favourites, the cart, invitations, proposals, contract creation and both
message send paths. Eleven copies of the same filter is eleven chances for
one of them to drift, and the one that drifts is the one somebody finds.

WHY THE EFFECT IS SYMMETRIC WHEN THE ROW IS NOT. A block is one person's
decision, but it cannot run in only one direction. If it hid the blocker
from the blocked and no more, the blocked person would still appear in the
blocker's own search results, their own favourites and their own inbox,
which is the single face they pressed the button to stop seeing. So the
helpers here read the pair, never the direction, and the direction is
consulted exactly once: in require_not_blocked, to choose which of two
sentences a refusal shows.

THREE SHAPES BECAUSE THERE ARE THREE QUESTIONS. A list endpoint wants every
id it must drop, once, before it filters. A write path wants a yes or no
about one counterparty and should not pay for a set it will look at once. A
write path that is about to refuse wants the row, so it can say which way
round the block went.

AND TWO SHAPES OF REFUSAL, WHICH IS NOT AN INCONSISTENCY. A write path
answers 403 and says which way round the block went, because the two people
on it may be bound by a contract and a silent failure would leave one of
them believing they had answered when they had not. The public storefront
answers 404 instead, reusing profile_not_found so a blocked page is the same
bytes as a deleted one. The difference is who is reading: a write path is
reached by somebody who already knows the other party exists, and a
storefront is reached by anybody with a link. require_not_blocked is for the
first case only; a read path that wants to disappear calls is_blocked_pair
and raises its own surface's not-found.
"""
from fastapi import status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.trust_safety.models import Block

# Said once, here, so eight call sites cannot word the same refusal eight
# ways. The client replaces both with a localised sentence keyed by the code;
# these are the English fallbacks and the text an untranslated client shows.
BLOCKED_BY_YOU_DETAIL = "You blocked this person. Unblock them to continue."
BLOCKED_BY_THEM_DETAIL = "This person is not accepting contact from you."


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
    """Yes or no for one pair, for any path that does not need the reason.

    Used by write paths that only have to stop, and by the public storefront,
    which has to answer as though the page were not there and therefore must
    not learn the direction it would be tempted to put in a message.
    """
    return block_between(db, user_id, other_user_id) is not None


def require_not_blocked(db: Session, actor_id: str, other_user_id: str) -> None:
    """Refuse an action between two people who are blocked, and say which way.

    THE REFUSED PERSON IS TOLD, and this is the deliberate difference from a
    social app. Hiding a block is right where the only thing at stake is
    somebody's feed. It is wrong here: these two may be bound by a signed
    contract with money in escrow, and a message that silently never arrives
    leaves the sender believing they have answered when they have not, which
    is worse for them than an awkward sentence. Silence would also be a lie
    the product tells on behalf of one user to another it has obligations to.

    WHAT IS STILL NOT DISCLOSED is who blocked whom anywhere else. This fires
    only at the moment somebody tries to act. No list and no search result
    says anything, so a block cannot be used to go fishing for whether a
    particular person has blocked you without trying to contact them, which
    is a thing they would then see.

    THE STOREFRONT IS THE ONE SURFACE THAT ANSWERS BEFORE AN ACTION, and it
    says 404 rather than anything about a block, which is why it is not a
    hole in the paragraph above. A reader who gets profile_not_found has
    learned that the page is not there, and a deleted account, a creator who
    never finished a profile and a block are all that same answer. What they
    cannot learn is which, or in which direction.

    403 here rather than 404, though. A 404 is the concealing answer and
    concealment is not available on a write path anyway: both parties already
    know the other exists, because a contract names them.
    """
    block = block_between(db, actor_id, other_user_id)
    if block is None:
        return
    if block.blocker_user_id == actor_id:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="blocked_user",
            detail=BLOCKED_BY_YOU_DETAIL,
        )
    raise AppError(
        status.HTTP_403_FORBIDDEN,
        code="blocked_by_user",
        detail=BLOCKED_BY_THEM_DETAIL,
    )

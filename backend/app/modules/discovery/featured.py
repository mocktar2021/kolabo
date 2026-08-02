"""A different handful of creators every time the landing page loads.

WHY THIS IS NOT JUST search?limit=8. Search is deterministic by design —
verified first, then biggest audience, then oldest profile — which is exactly
right when somebody is looking for a creator and exactly wrong when the page
is looking for somebody to show them. The landing page called it with a limit
of eight, so the same eight faces were above the fold on every visit, forever:
the ninth-ranked creator was invisible to every brand that never scrolled or
never searched, and the top eight collected every impression the platform had
to give. On a pilot roster that is not a ranking, it is a lottery nobody can
re-enter, and it is the same cold-start asymmetry the open board exists to fix
from the other side.

So: same searchable creators, same card, random order. Nothing here decides
who is eligible — service._is_searchable does, and it is called rather than
restated, because two definitions of "who is live" would mean a creator
visible on the landing page and missing from search, which nobody reports
because each screen looks correct on its own.

THE ORDERING IS THE DATABASE'S, AND HERE IS THE TRADE-OFF WE ACCEPTED. ORDER
BY random() makes the database assign a random value to every candidate row
and then sort all of them, so the cost is the whole table on every request —
no index can help, and it does not care that we only want eight. At pilot
volume (hundreds of profiles) that is a few milliseconds and it is worth it
for code with no shuffling logic of its own to get wrong. IT IS WORTH
REVISITING WHEN THE CREATOR TABLE IS LARGE: the usual replacements are
sampling a random id range, keeping a periodically-shuffled featured set, or
TABLESAMPLE on PostgreSQL, and all three are more machinery than a pilot
needs. The named _random_order below is the single line any of them would
replace.

A separate module from service.py rather than another function in it: service
is about the search query and the favourites list, and this is a different
question ("show me anybody") that happens to render the same card. The
dependency runs one way — router -> featured -> service.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.discovery import service
from app.modules.profiles import models as profiles

# What the landing page asks for. A strip, not a page.
DEFAULT_FEATURED_LIMIT = 8

# The most anybody can ask for in one call. Not a performance guard — the sort
# below already costs the whole table whatever the limit is — but a guard
# against this becoming an undocumented "dump every creator" endpoint that
# gets depended on and then cannot be changed.
MAX_FEATURED_LIMIT = 50


def _random_order():
    """Database-side random ordering, in one named place.

    A function rather than an inline func.random() for two reasons. It is the
    single line that any smarter sampling strategy replaces when the creator
    table outgrows a full sort (see the module docstring). And it gives the
    tests something deterministic to hold: a test can swap this for a fixed
    ordering and assert the result follows it, which proves the ordering
    expression really does come from here — an assertion that cannot flake,
    unlike any test that has to observe randomness happening.
    """
    return func.random()


def featured_creators(db: Session, limit: int = DEFAULT_FEATURED_LIMIT) -> list[dict]:
    """A random sample of searchable creators, as ordinary search cards.

    The random ordering is applied by the database and the searchability rule
    is applied here, in that order, and the reason is that searchability is
    not a column: it depends on a bio, a category list and a COUNT of active
    packages from another table. So the query cannot both shuffle and filter,
    and the cut to `limit` has to happen after the filter — taking eight rows
    from the database first would return two or three cards on a roster where
    most profiles are half-finished, which is the exact page this replaces.

    The loop stops as soon as it has enough, so a large roster does not build
    a card for every profile in it.
    """
    # Clamped rather than refused: this is a landing page strip, and a stale
    # client asking for a hundred should get fifty rather than an error page
    # where the creators were supposed to be.
    wanted = max(1, min(limit, MAX_FEATURED_LIMIT))

    rows = (
        db.query(profiles.InfluencerProfile, User)
        .join(User, User.id == profiles.InfluencerProfile.user_id)
        .order_by(_random_order())
        .all()
    )
    ctx = service._card_context(db)

    out: list[dict] = []
    for prof, user in rows:
        if not service._is_searchable(prof, ctx["package_counts"].get(prof.user_id, 0)):
            continue
        out.append(service._result_card(prof, user, ctx))
        if len(out) >= wanted:
            break
    return out

"""Checking out a basket: one order per creator, all of them or none.

Brands do not shop one creator at a time. They put four packages from three
people in a basket and pay once, and the thing they must NOT get for it is one
order covering three people. Each creator accepts or declines their own work,
on their own clock, for their own money — and one creator's no has nothing to
do with another's yes. So a checkout FANS OUT: one direct order per creator,
each one an ordinary order built by service._place_order, each one living or
dying alone. Everything downstream (accept, decline, contract, escrow, the
expiry sweep) then has nothing new to learn.

WHY THE CART IS NOT STORED. The client holds the basket and posts the whole
thing at checkout; the server keeps nothing between requests. A server-side
cart would buy a table, an expiry policy (how long does an abandoned basket
live, and who tells the creator their package is sitting in one?) and a
stale-price problem (the package moved from 25k to 40k while the basket sat —
which price is the order?). It would buy all of that to solve a problem the
client does not have: holding a list of package ids is what a client is for,
and reading prices off the live rows at checkout means there is never a stale
one to reconcile.

WHY IT IS ALL OR NOTHING. Every item is validated before a single row is
written, and the writes are one transaction. A checkout that half-succeeded
would leave a brand not knowing which half: two creators booked and paid for,
a third silently dropped, and no way to tell from the response which is which.
A brand that has to audit its own basket after every checkout will go back to
ordering one at a time — or to WhatsApp.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.campaigns import schemas, service

MIN_CART_ITEMS = 1

# Twenty lines is already a bigger campaign than a brief, and every line is a
# package lookup plus an order to build. Past that the request is either a
# client bug or somebody scripting the endpoint, and neither deserves an
# unbounded transaction holding rows for twenty-odd creators at once.
MAX_CART_ITEMS = 20


def _resolve_item(db: Session, business_user_id: str, item, index: int) -> dict:
    """One line of the basket, checked the same way a single order is.

    Every rule a lone order runs — the package exists and is active, the
    creator exists and is a creator, the platform/deliverable pair is real,
    the rate clears the currency floor, the quantity and timeline are in
    range, nobody is ordering from themselves — comes from the same two
    resolvers create_direct_order and create_negotiated_order use. A cart with
    its own copy of those checks is a cart that eventually disagrees with the
    single-order endpoint about what a valid order is, and the disagreement
    would be about money.

    Whatever they raise is re-raised as a 400 naming the POSITION in the cart.
    A brand looking at "Package not found" against a twenty-line basket has no
    idea which line to fix; the index is the only thing that makes the message
    actionable. That does mean a missing package answers 400 here where the
    single-order endpoint answers 404 — deliberate: the request as a whole is
    malformed, and nothing about the checkout URL is missing.
    """
    try:
        service.check_order_form(item)
        if item.package_id is not None:
            return service.resolve_package_terms(db, business_user_id, item.package_id, item.note)
        return service.resolve_negotiated_terms(db, business_user_id, item)
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Item {index}: {exc.detail}",
        ) from exc


def _group_by_creator(resolved: list[dict]) -> dict[str, list[dict]]:
    """The basket, sorted into one pile per creator.

    Insertion ordered, so the orders come back in the order the buyer built
    the basket rather than in whatever order a set happened to iterate. A
    response whose rows move between identical requests is a response nobody
    can write a test or a UI against.
    """
    grouped: dict[str, list[dict]] = {}
    for terms in resolved:
        grouped.setdefault(terms["creator_user_id"], []).append(terms)
    return grouped


def _one_currency(creator_user_id: str, lines: list[dict]) -> str:
    """A creator's pile has to be priced in a single currency.

    One order carries one escrow, and an escrow carries one currency: there is
    no such thing as holding 25,000 XOF and 400 GHS against one agreement, and
    summing them would need a rate the platform does not set. So a basket that
    mixes currencies for ONE creator is refused, naming them, and the fix is
    to check out each currency separately — which is two orders, which is what
    it always was.

    Two creators priced in two different currencies is fine and untouched:
    they are two orders and two escrows already.
    """
    currencies = {line["currency"] for line in lines}
    if len(currencies) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"The items for creator {creator_user_id} are priced in "
                f"{', '.join(sorted(currencies))}. An order carries one escrow and an "
                "escrow carries one currency, so order each currency separately."
            ),
        )
    return currencies.pop()


def _merge(lines: list[dict]) -> dict:
    """Several basket lines, as the one order the creator will answer.

    title is derived rather than asked for, exactly as a negotiated order's
    is: the buyer has already said all of it by choosing the packages, and a
    title box on a checkout is one more thing to leave blank.

    timeline_days is the LONGEST of the lines. The order is one commitment
    with one contract behind it, and it is met when the slowest piece lands;
    promising the shortest would put the creator in breach on delivery day for
    work they never agreed to rush.

    The notes are concatenated in basket order. A proposal carries one note
    and each line may have brought its own word to the creator; dropping all
    but the first would quietly lose instructions somebody typed.
    """
    notes = [line["note"] for line in lines if line["note"]]
    return {
        "title": " + ".join(line["title"] for line in lines),
        "deliverables": [line["deliverable"] for line in lines],
        "rate_amount": sum(line["rate_amount"] for line in lines),
        "timeline_days": max(line["timeline_days"] for line in lines),
        "note": "\n".join(notes) or None,
    }


def checkout(db: Session, business_user_id: str, payload: schemas.CartCheckoutIn) -> dict:
    """Turn a basket into one direct order per creator, or into nothing."""
    items = payload.items
    # Bounds answered here rather than declared on the schema, for the reason
    # OrderIn spells out: a 400 naming the rule tells a client what to do, a
    # 422 field-error tells it that "items" is wrong.
    if len(items) < MIN_CART_ITEMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A checkout needs at least one item.",
        )
    if len(items) > MAX_CART_ITEMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A cart holds at most {MAX_CART_ITEMS} items. Check out in smaller baskets.",
        )

    # The buyer's role is a fact about the caller, not about any line, so it
    # is asked once and answers 403 rather than a 400 naming an item — the
    # same guard, in the same words, that gates authoring a brief and placing
    # a single order.
    service._require_campaign_author(db, business_user_id)

    # EVERY item, before a single row exists. This loop is the all-or-nothing
    # promise: it can only raise, never write, so a failure on the last line
    # leaves the first nineteen creators knowing nothing about it.
    resolved = [
        _resolve_item(db, business_user_id, item, index) for index, item in enumerate(items)
    ]

    orders = []
    for creator_user_id, lines in _group_by_creator(resolved).items():
        currency = _one_currency(creator_user_id, lines)
        merged = _merge(lines)
        # commit=False: the orders are written together and committed once
        # below, so a failure part-way through this loop rolls back the
        # creators already placed instead of leaving a brand half-ordered.
        placed = service._place_order(
            db,
            business_user_id=business_user_id,
            creator_user_id=creator_user_id,
            title=merged["title"],
            deliverables=merged["deliverables"],
            rate_amount=merged["rate_amount"],
            currency=currency,
            timeline_days=merged["timeline_days"],
            note=merged["note"],
            notice=(
                f"A brand ordered {merged['title']} from you. You have "
                f"{service.ORDER_ACCEPT_WINDOW_HOURS} hours to accept or decline."
            ),
            notice_key="order_cart",
            commit=False,
        )
        placed["creator_user_id"] = creator_user_id
        orders.append(placed)

    db.commit()
    return {"orders": orders}

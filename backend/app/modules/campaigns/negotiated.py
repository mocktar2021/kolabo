"""Checking the terms a brand typed instead of the terms a creator published.

A package order copies its terms off a row the creator created, and that row
was validated when it was published: the platform and deliverable exist, the
price clears the floor for its currency. A negotiated order has no such row —
the buyer types the numbers — so every rule the package went through has to be
applied here instead. Otherwise "negotiate" becomes the way around all of
them, and the first thing to go around would be the price floor.

Deliberately pure: nothing here touches the database or builds anything.
Placing the order is campaigns.service's job, and keeping this module free of
it is what keeps the import running one way (service -> negotiated) instead of
in a circle.
"""
from fastapi import HTTPException, status

from app.core.platforms import PLATFORM_DELIVERABLES, is_valid_pair
from app.core.pricing import min_price

MIN_OFFER_QUANTITY = 1
# The same ceiling a brief's deliverables run under
# (campaigns.service.MAX_DELIVERABLE_QUANTITY) and for the same reason: past a
# hundred, the number in the quantity box is an amount somebody pasted into
# the wrong field. Two constants rather than one shared one only because the
# import runs service -> negotiated and must not run back; if they ever need
# to differ, that is a decision somebody makes on purpose.
MAX_OFFER_QUANTITY = 100

MIN_OFFER_TIMELINE_DAYS = 1
# Three months. Past a quarter this is not a deliverable with a deadline, it
# is a retainer — a different relationship, with different escrow and a
# different contract, and none of that exists yet. A number that long is far
# more likely to be a typo than a plan.
MAX_OFFER_TIMELINE_DAYS = 90


def _label(value: str) -> str:
    """A platform or deliverable id, made readable.

    Built from the id rather than looked up, because the real display names
    live in the frontend's i18n and are rendered in the reader's language.
    This string is only for the places that have nowhere to put a structured
    deliverable — a notification, a row in a campaign list — while the client
    renders the deliverables array properly.
    """
    return value.replace("_", " ").title()


def order_title(platform: str, deliverable_type: str, quantity: int) -> str:
    """A name for an order that has no package title behind it.

    "2 × Reel — Instagram". Derived rather than asked for: the buyer has
    already said all of it in the terms, and a title field would only be one
    more thing to get wrong or leave blank on an order that is otherwise
    complete the moment it is placed.
    """
    return f"{quantity} × {_label(deliverable_type)} — {_label(platform)}"


def validate_offer(offer) -> None:
    """Every rule a package was held to, applied to typed-in terms.

    Messages mirror the ones the packages module and the brief validator
    already raise, word for word where the rule is the same: a brand should
    not learn two different phrasings of one rule depending on which screen it
    hit. Each error names what is wrong and what is allowed, so the fix is in
    the message.
    """
    if offer.platform not in PLATFORM_DELIVERABLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{offer.platform} is not a supported platform. Allowed: {', '.join(sorted(PLATFORM_DELIVERABLES))}",
        )
    if not is_valid_pair(offer.platform, offer.deliverable_type):
        allowed = ", ".join(PLATFORM_DELIVERABLES.get(offer.platform, [])) or "none"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{offer.deliverable_type} is not available on {offer.platform}. Allowed: {allowed}",
        )

    quantity = offer.quantity
    # bool is an int subclass in Python, so `true` would otherwise slip
    # through as a quantity of 1 — the same guard _validate_deliverables uses.
    if not isinstance(quantity, int) or isinstance(quantity, bool) or not (
        MIN_OFFER_QUANTITY <= quantity <= MAX_OFFER_QUANTITY
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Deliverable quantity must be a whole number between "
                f"{MIN_OFFER_QUANTITY} and {MAX_OFFER_QUANTITY}"
            ),
        )

    if not isinstance(offer.rate_amount, int) or isinstance(offer.rate_amount, bool) or offer.rate_amount < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The rate must be a whole positive amount in minor units.",
        )
    currency = offer.currency.upper()
    floor = min_price(currency)
    if floor is not None and offer.rate_amount < floor:
        # A negotiated price cannot undercut the floor either — that is the
        # entire point of having one. The floor is not a rule about packages,
        # it is a rule about the market: it keeps joke listings out and keeps
        # the rate reachable for nano-creators without going to zero. An offer
        # that lands underneath it is the same listing wearing a different
        # hat, so it gets the same answer, in the same words the packages
        # module uses.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum price for {currency} is {floor}.",
        )

    timeline_days = offer.timeline_days
    if not isinstance(timeline_days, int) or isinstance(timeline_days, bool) or not (
        MIN_OFFER_TIMELINE_DAYS <= timeline_days <= MAX_OFFER_TIMELINE_DAYS
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Timeline must be a whole number of days between "
                f"{MIN_OFFER_TIMELINE_DAYS} and {MAX_OFFER_TIMELINE_DAYS}"
            ),
        )

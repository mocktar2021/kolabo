"""Which rows a statement is about, defined once for both sides of the money.

WHY THIS IS ONE OBJECT AND NOT TWO SETS OF PARAMETERS. The creator's earnings
screen and the buyer's spend screen ask the same four questions — when, on
which campaign, with whom — and the answers have to mean exactly the same
thing on both. Two copies of "is this row in the range" is two chances for one
of them to make a bound exclusive, and the first anyone would know about it is
a creator and a brand quoting each other different totals for the same
contract.

THE FILTER NARROWS THE TOTALS AND THE LIST TOGETHER, and that is the rule the
whole module exists to enforce. A filtered list sitting beside all-time totals
is not a smaller view of the truth, it is two different questions answered on
one screen: somebody who asked for March sees a March statement under an
all-time "earned" figure, adds up the rows, gets a different number, and
concludes our arithmetic is broken. The year filter has always worked this way
and every filter added since follows it. The list CAP is the one thing that
applies to the list alone, for the opposite reason — totals truncated to a
page would mean "earned, in the hundred rows we felt like loading".

HOW year COMPOSES WITH from_date AND to_date: as an INTERSECTION. A request
carrying both is answered with the rows that satisfy both, not with one
silently overriding the other. Two reasons. A caller that sends year=2025 and
a March window plainly means March 2025, and intersection is the only reading
that gives them that. And where the two genuinely contradict — year=2025 with
a 2024 window — the honest answer is zero rows, which is visibly empty and
sends them to fix the request; picking a winner would show a confident, wrong
number instead. Rejecting the combination with a 400 was the alternative and
was dropped: it would break every client that sends its year selector on
every request while the user also picks a date range.

All bounds are INCLUSIVE. from_date and to_date name days a human picked off a
calendar, and a range whose last day is not in it is the kind of off-by-one
nobody reports and everybody works around.

Filtering happens in Python, over rows already loaded, rather than in the
query. At pilot volume a creator's whole escrow history is a few dozen rows
and the read model already loads all of them to compute the totals; pushing
the predicate into SQL would buy nothing and would have to be written twice,
once per screen. Worth revisiting when somebody's history is long enough that
loading it is the cost.
"""
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class StatementFilter:
    """The four narrowings a statement understands, all optional.

    Frozen because a filter is a description of a request, not a thing a read
    model should be able to edit halfway through building an answer.

    counterparty_id is deliberately not named business_user_id or
    influencer_user_id: it is "the other party", which is the buyer on the
    creator's screen and the creator on the buyer's. One field, resolved by
    whichever read model is asking.
    """

    year: int | None = None
    from_date: date | None = None
    to_date: date | None = None
    campaign_id: str | None = None
    counterparty_id: str | None = None

    @property
    def has_period(self) -> bool:
        return (
            self.year is not None
            or self.from_date is not None
            or self.to_date is not None
        )

    def matches(self, when, campaign_id: str | None, counterparty_id: str | None) -> bool:
        """Is this row inside every narrowing that was asked for?

        An empty filter matches everything, which is what makes the unfiltered
        screen and the filtered one the same code path.

        A row with NO DATE cannot be shown to fall inside a period, so it is
        excluded the moment any period filter is set. Including it would be
        asserting something about when it happened that we do not know; it
        still appears on the unfiltered screen, where no such claim is made.
        """
        if self.campaign_id is not None and campaign_id != self.campaign_id:
            return False
        if self.counterparty_id is not None and counterparty_id != self.counterparty_id:
            return False

        if not self.has_period:
            return True
        if when is None:
            return False

        # Compared as a DAY, not as an instant. from_date and to_date are
        # dates a human picked off a calendar, and a payment released at
        # 18:00 on the last day of the range is inside the range — comparing
        # a datetime against midnight of to_date would drop almost everything
        # that happened on the final day.
        day = when.date() if isinstance(when, datetime) else when

        if self.year is not None and day.year != self.year:
            return False
        if self.from_date is not None and day < self.from_date:
            return False
        if self.to_date is not None and day > self.to_date:
            return False
        return True

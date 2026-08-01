"""What a creator has actually earned, is waiting on, and cannot touch.

THREE FIGURES, AND THEY ARE THREE FOR A REASON.

  earned    money that has been released to them and is theirs.
  pending   money funded into escrow and not yet released — on its way.
  disputed  money frozen by a dispute — not on its way, and possibly never.

DISPUTED IS NOT PART OF PENDING, and that separation is the whole point of
this module rather than a presentation detail. Pending is a promise: a brand
has already paid, the escrow will release on delivery or on the auto-release
timer, and a creator can plan around it. Disputed money has no such date and
may end up refunded to the buyer in whole or in part by an admin. Folding one
into the other would put a number on a creator's screen that means "expect
this" when the true meaning is "argue for this", and somebody would commit
rent to it.

EVERY FIGURE IS NET OF COMMISSION. The platform's cut comes off at release, so
the gross is a number the creator never sees in their wallet; an earnings
screen quoting it overstates every single line by the commission rate and
turns each payout into a small disappointment. commission_for is reused rather
than re-derived — one definition of the fee, shared with the ordinary release
and with a disputed split, so this screen and the payout can never disagree
about what a payment was worth. Each row still carries gross, commission and
net side by side, so nothing is hidden, only ordered honestly.

NOTHING IS EVER SUMMED ACROSS CURRENCIES. Totals are dicts keyed by currency,
for the same reason the rest of the codebase keeps an explicit currency beside
every amount: XOF and GHS are not addends. A single "total earnings" number
across two markets is not a rounding problem, it is a meaningless number, and
the one place it would appear is the screen a creator trusts most.

CREATOR SIDE ONLY. A business calling this gets empty totals and an empty
list, deliberately. What a business would want here is SPEND, which is a
different question with a different shape — commission is not deducted from
it, refunds belong in it, and "pending" means money already gone from their
wallet rather than money coming into it. Answering both from one endpoint
would mean one field meaning two opposite things depending on who asked.
Buyer-side spend is out of scope here and wants its own endpoint.

A separate module from service.py, which owns the money path itself. This is a
read model: it writes nothing, moves nothing, and the dependency runs one way
— router -> earnings -> service.commission_for, models.
"""
from sqlalchemy.orm import Session

from app.modules.campaigns.models import Campaign
from app.modules.contracts.models import Contract
from app.modules.payments import models
from app.modules.payments.service import commission_for
from app.modules.profiles.models import BusinessProfile

# How many payment rows the list carries. A statement panel on an earnings
# screen, not an accounting export: past this the page is slower than it is
# useful, and somebody wanting their whole history wants a real export with a
# date range rather than a longer list.
EARNINGS_LIST_LIMIT = 100

# The statuses that mean anything to a creator. REFUNDED is deliberately
# absent: that money went back to the buyer, never reached the creator, and is
# not earnings of any kind — not earned, not pending, not frozen. Showing it
# as a zero-value row would only invite the question of why it is there.
COUNTED_STATUSES = (models.HELD, models.RELEASED, models.DISPUTED)


def _released_gross(escrow: models.Escrow, split_released: int | None) -> int:
    """What a released escrow actually sent to the creator.

    Normally the whole escrow. After a DISPUTE SPLIT it is not: resolution
    marks the escrow RELEASED the moment any money at all reaches the creator,
    while escrow.amount still holds the full sum the buyer paid in and part of
    it went back to them as a refund. Reading escrow.amount there would credit
    a creator with money that was refunded away from them — the single worst
    number this screen could show, because it is wrong in the creator's favour
    and they will notice only when the payout lands short.

    The dispute row is the record of the split, so it is what the released
    figure comes from when there is one. commission_amount needs no such care:
    resolution already charges the fee on the released part only.
    """
    if split_released is not None:
        return split_released
    return escrow.amount


def _split_amounts(db: Session, escrow_ids: list[str]) -> dict[str, int]:
    """escrow id -> the released half of its settled dispute, where there is one.

    One query for the whole page. An escrow can carry several dispute rows
    over its life (escrow_id is indexed, not unique), so the newest RESOLVED
    one wins: it is the one that decided where the money actually went.
    """
    if not escrow_ids:
        return {}
    rows = (
        db.query(models.Dispute)
        .filter(
            models.Dispute.escrow_id.in_(escrow_ids),
            models.Dispute.status == models.DISPUTE_RESOLVED,
            models.Dispute.released_amount.isnot(None),
        )
        .order_by(models.Dispute.resolved_at.asc())
        .all()
    )
    # Ascending, so a later resolution overwrites an earlier one.
    return {d.escrow_id: d.released_amount for d in rows}


def my_earnings(db: Session, user_id: str, year: int | None = None) -> dict:
    """The caller's earnings, from the creator side of every escrow they are on.

    Totals cover EVERY qualifying escrow; the year filter and the list cap
    apply to the payments list alone. Truncating the totals to a page would
    make "earned" mean "earned, in the hundred rows we felt like loading",
    which is the kind of almost-true number that gets quoted back to us in a
    support ticket. The year filter is the one exception a caller asks for
    explicitly, so it applies to both: somebody who filtered to 2025 wants the
    2025 totals, not the all-time ones beside a 2025 list.
    """
    escrows = (
        db.query(models.Escrow)
        .filter(
            models.Escrow.influencer_user_id == user_id,
            models.Escrow.status.in_(COUNTED_STATUSES),
        )
        .all()
    )
    if not escrows:
        # An empty answer with the right shape, not a 404. A creator who has
        # never been paid still opens this screen, and zero is the true
        # answer. It is also what a business gets, for the reason at the top.
        return {"earned": {}, "pending": {}, "disputed": {}, "payments": []}

    splits = _split_amounts(db, [e.id for e in escrows if e.status == models.RELEASED])

    campaign_titles = {
        c.id: c.title
        for c in db.query(Campaign).filter(Campaign.id.in_({e.campaign_id for e in escrows})).all()
    }
    # The counterparty on a creator's earnings row is always the buyer, and a
    # buyer's only public identity is its company name — the same source the
    # inbox and the invitation card read. Null when they have written no
    # profile: the users table has nothing to fall back on but a phone number,
    # and a phone number is never handed to the other side of a deal.
    company_names = {
        p.user_id: p.company_name
        for p in db.query(BusinessProfile)
        .filter(BusinessProfile.user_id.in_({e.business_user_id for e in escrows}))
        .all()
    }
    # The contract id is on the escrow already; this only confirms the row is
    # still there, so a payment whose contract was tidied away still renders.
    known_contracts = {
        row[0]
        for row in db.query(Contract.id)
        .filter(Contract.id.in_({e.contract_id for e in escrows}))
        .all()
    }

    earned: dict[str, int] = {}
    pending: dict[str, int] = {}
    disputed: dict[str, int] = {}
    rows = []

    for escrow in escrows:
        if escrow.status == models.RELEASED:
            gross = _released_gross(escrow, splits.get(escrow.id))
            # Written at release from commission_for. Falling back to a fresh
            # calculation covers rows released before the column existed,
            # rather than quietly reporting a fee of zero on them.
            commission = (
                escrow.commission_amount
                if escrow.commission_amount is not None
                else commission_for(gross)
            )
            # resolved_at is when the money actually moved. held_at is the
            # fallback only for rows predating that column being filled in.
            when = escrow.resolved_at or escrow.held_at
            bucket = earned
        else:
            gross = escrow.amount
            # Nothing has been charged yet, so the fee is projected from the
            # one shared definition. It is a projection and the row says so by
            # carrying the three figures separately — but a "pending" number
            # quoted gross would promise 15 percent more than will arrive.
            commission = commission_for(gross)
            when = escrow.held_at
            bucket = disputed if escrow.status == models.DISPUTED else pending

        net = gross - commission

        if year is not None and (when is None or when.year != year):
            continue

        # Keyed by currency, never added across them. Two markets are two
        # numbers, and a creator paid in XOF and GHS has two balances.
        bucket[escrow.currency] = bucket.get(escrow.currency, 0) + net

        rows.append(
            {
                "escrow_id": escrow.id,
                "contract_id": escrow.contract_id if escrow.contract_id in known_contracts else escrow.contract_id,
                "campaign_title": campaign_titles.get(escrow.campaign_id),
                "counterparty_name": company_names.get(escrow.business_user_id),
                "gross": gross,
                "commission": commission,
                "net": net,
                "currency": escrow.currency,
                "status": escrow.status,
                # The date the row is about: when it settled if it settled,
                # when it was funded if it has not. One column rather than
                # two, because a statement line has one date on it.
                "date": when,
            }
        )

    # Newest first: the thing a creator opened this screen to check is the
    # most recent payment, not the first one they ever earned.
    rows.sort(key=lambda r: (r["date"] is not None, r["date"]), reverse=True)
    return {
        "earned": earned,
        "pending": pending,
        "disputed": disputed,
        "payments": rows[:EARNINGS_LIST_LIMIT],
    }

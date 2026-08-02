"""What a buyer has spent, has committed, and has had come back.

THE MIRROR OF EARNINGS, AND DELIBERATELY NOT THE SAME ENDPOINT. It would have
been a one-line change to let /payments/earnings answer for a business too,
and it would have been wrong in three separate ways at once, because the same
words mean different things depending on which side of the escrow you are on:

  COMMISSION IS NOT DEDUCTED HERE. The platform's cut comes out of the
  creator's release, not out of the buyer's payment: a brand that funded
  100000 XOF paid 100000 XOF and its accounting says so, whatever the creator
  received. Earnings quotes net for the opposite reason — gross is a number
  that never reaches a creator's wallet. One field cannot honestly be both.

  REFUNDS BELONG IN THIS SCREEN AND NOT IN THAT ONE. Money returned to the
  buyer is a real line in the buyer's ledger — they paid it and got it back,
  and the two facts have to be visible together or the arithmetic does not
  close. For the creator it is money that never arrived at all, which is why
  earnings drops REFUNDED entirely rather than showing a zero.

  "PENDING" MEANS THE OPPOSITE THING. To a creator it is money on its way to
  them. To a buyer it is money already gone from their wallet and sitting at
  the provider, committed against work that has not been signed off. Same
  word, opposite direction, and a single endpoint answering both would put a
  field on the screen whose meaning depends on who is looking at it.

NOTHING IS EVER SUMMED ACROSS CURRENCIES, exactly as in earnings and for the
same reason: XOF and GHS are not addends, and a brand running in two markets
has two budgets, not one meaningless total.

BUYER SIDE ONLY. A creator calling this gets empty figures, because the filter
is on business_user_id and a creator is on no escrow as the buyer. That is the
same shape earnings has in reverse, and it is deliberate: an empty answer with
the right fields is a usable screen, and there is no version of "what have I
spent" that means anything to somebody who has never bought.

A read model like earnings.py: it writes nothing, moves nothing, and the
dependency runs one way — router -> spend -> models, identity.
"""
from sqlalchemy.orm import Session

from app.core.identity import creator_identities
from app.modules.campaigns.models import Campaign
from app.modules.payments import models

# How many rows the statement carries, the same bound and the same reasoning as
# earnings: a panel on a screen, not an accounting export. Somebody who wants
# their whole history wants a real export with a date range.
SPEND_LIST_LIMIT = 100

# Every status a buyer's money can be in. REFUNDED is here where earnings
# leaves it out, which is the whole difference between the two screens: the
# money came back to this person, so it is theirs to see.
COUNTED_STATUSES = (models.HELD, models.RELEASED, models.DISPUTED, models.REFUNDED)


def _split_amounts(db: Session, escrow_ids: list[str]) -> dict[str, tuple[int, int]]:
    """escrow id -> (released, refunded) for escrows settled by a dispute split.

    BOTH HALVES, which is what makes this its own function rather than a call
    into earnings._split_amounts. That one returns only the released figure,
    correctly: a creator has no refunded column, because refunded money is
    money that never reached them. A buyer has both, and they are two
    different lines in their ledger.

    Why it cannot be skipped. resolution.py marks an escrow RELEASED the
    moment ANY money at all reaches the creator, while escrow.amount still
    holds the full sum the buyer funded and part of it went back to them.
    Reading escrow.amount for a split would overstate spend by the refund AND
    lose the refund entirely — one mistake misreporting both figures, in the
    direction that makes the platform look like it kept the money.

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
    return {d.escrow_id: (d.released_amount, d.refunded_amount or 0) for d in rows}


def _empty() -> dict:
    """The right shape with nothing in it.

    Not a 404. A brand that has never funded an escrow still opens this
    screen, and zero is the true answer; it is also what a creator gets, for
    the reason at the top of the module.
    """
    return {"spent": {}, "pending": {}, "disputed": {}, "refunded": {}, "payments": []}


def my_spend(db: Session, user_id: str) -> dict:
    """The caller's spend, from the buyer side of every escrow they are on.

    Four figures, each a map of currency to minor units:

      spent     released to the creator. The FULL amount, no commission taken
                off — the brand paid it.
      pending   funded and held, committed against work not yet signed off.
      disputed  frozen while a dispute runs. Not folded into pending, because
                pending is money the buyer expects to lose and disputed is
                money they may get back; a buyer planning a budget needs to
                know which is which just as much as a creator does.
      refunded  money that came back, whether the whole escrow or the
                refunded half of a split.

    The list cap applies to the LIST alone and never to the totals, the same
    rule earnings runs on: totals truncated to a page would mean "spent, in
    the hundred rows we felt like loading", which is the kind of almost-true
    number that gets quoted back to us in a support ticket.
    """
    escrows = (
        db.query(models.Escrow)
        .filter(
            models.Escrow.business_user_id == user_id,
            models.Escrow.status.in_(COUNTED_STATUSES),
        )
        .all()
    )
    if not escrows:
        return _empty()

    splits = _split_amounts(db, [e.id for e in escrows if e.status == models.RELEASED])

    campaign_titles = {
        c.id: c.title
        for c in db.query(Campaign).filter(Campaign.id.in_({e.campaign_id for e in escrows})).all()
    }
    # The counterparty on a buyer's row is always the creator, named the one
    # shared way (app.core.identity) so the brand reads the same name here, on
    # its shortlist and on the proposal it accepted. Null where the creator
    # has written no profile: the users table holds nothing but a phone
    # number, and a phone number is never handed to the other side of a deal.
    identities = creator_identities(db, [e.influencer_user_id for e in escrows])

    spent: dict[str, int] = {}
    pending: dict[str, int] = {}
    disputed: dict[str, int] = {}
    refunded: dict[str, int] = {}
    rows = []

    for escrow in escrows:
        # How much of this escrow went each way, and when it was decided.
        # amount is what the row is ABOUT under its own status; came_back is
        # the part of a split that returned to the buyer.
        came_back = 0
        if escrow.status == models.RELEASED:
            split = splits.get(escrow.id)
            if split is not None:
                amount, came_back = split
            else:
                amount = escrow.amount
            # resolved_at is when the money actually moved; held_at is the
            # fallback only for rows predating that column being filled in.
            when = escrow.resolved_at or escrow.held_at
            _add(spent, escrow.currency, amount)
            if came_back:
                _add(refunded, escrow.currency, came_back)
        elif escrow.status == models.REFUNDED:
            # Fully refunded: resolution only writes this status when nothing
            # at all reached the creator, so the whole escrow came back.
            amount = escrow.amount
            when = escrow.resolved_at or escrow.held_at
            _add(refunded, escrow.currency, amount)
        else:
            amount = escrow.amount
            when = escrow.held_at
            _add(disputed if escrow.status == models.DISPUTED else pending,
                 escrow.currency, amount)

        rows.append(
            {
                "escrow_id": escrow.id,
                "contract_id": escrow.contract_id,
                "campaign_title": campaign_titles.get(escrow.campaign_id),
                "counterparty_name": (identities.get(escrow.influencer_user_id) or {}).get(
                    "display_name"
                ),
                "amount": amount,
                # Carried on the row and not only in the totals. Without it a
                # split shows 60000 spent on a contract the buyer funded with
                # 100000, and the 40000 that came back appears in the refunded
                # total with no line to trace it to — the statement and the
                # totals would disagree and neither would be findable.
                "refunded_amount": came_back,
                "currency": escrow.currency,
                "status": escrow.status,
                # The date the row is about: when it settled if it settled,
                # when it was funded if it has not. One column, because a
                # statement line has one date on it.
                "date": when,
            }
        )

    # Newest first: what a buyer opened this screen to check is the most
    # recent payment, not the first one they ever made.
    rows.sort(key=lambda r: (r["date"] is not None, r["date"]), reverse=True)
    return {
        "spent": spent,
        "pending": pending,
        "disputed": disputed,
        "refunded": refunded,
        "payments": rows[:SPEND_LIST_LIMIT],
    }


def _add(bucket: dict, currency: str, amount: int) -> None:
    """Add to one currency's total, never across them.

    A named helper rather than the expression inline four times, because the
    thing being protected is that every one of these totals is keyed by
    currency — and the way that rule gets broken is somebody adding a fifth
    figure and writing a plain += .
    """
    bucket[currency] = bucket.get(currency, 0) + amount

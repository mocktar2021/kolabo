"""Referral rewards: who gets credited, when, and in what.

The product decisions live here, at the top of the module that implements
them, because they are business rules rather than implementation details and
the next person to touch this needs the reasoning before the code:

- THE REWARD TRIGGERS ON THE REFERRED USER'S FIRST COMPLETED ORDER, NEVER AT
  SIGNUP. Paying at signup pays for accounts, and accounts are free to
  manufacture: an email address and an OTP is the whole cost of one. Paying at
  completion pays for a transaction that had to clear escrow, which is a thing
  nobody can fake for free. Fake signups must earn nothing.
- THE REWARD IS PLATFORM CREDIT, NOT CASH. Credit needs no payout rails, opens
  no KYC surface, and cannot be cashed out by a ring of accounts referring each
  other. At pilot stage that is worth more than the extra pull a cash bonus
  would give, and the decision is reversible later; a fraud incident on real
  money is not.
- CREATORS REFER BOTH CREATORS AND BUSINESSES WITH ONE CODE. One code is one
  thing to share and one thing to explain, and a creator who brings in a brand
  has done the marketplace at least as much good as one who brings in a peer.
  The two audiences are told apart in the reporting, not in the code itself.
"""
import logging
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.core.country_config import COUNTRY_CONFIG
from app.core.rewards import referral_credit
from app.modules.auth.models import REFEREE, REFERRER, ReferralCredit, User

logger = logging.getLogger(__name__)

# Which roles count as a creator when a referrer's signups are split for
# reporting. Everything else is a buyer: an agency books creators the same way
# a business does, so it belongs on the same side of the tally.
CREATOR_ROLES = {"influencer"}

# The referral screen shows a proof panel, not a CRM export.
REFERRAL_LIST_LIMIT = 50


def market_currency(user: User) -> str | None:
    """The currency of the user's own market, or None if it is unconfigured."""
    cfg = COUNTRY_CONFIG.get(user.country_code or "")
    return cfg["currency"] if cfg else None


def has_ordered(db: Session, user_id: str) -> bool:
    """Whether this user's first completed order has already been rewarded.

    The existence of their "referee" row IS the first-completed-order flag.
    One is written the first time an escrow of theirs is released, so every
    later order finds it and awards nothing. No separate counter, no flag on
    the user row: the ledger is the record.
    """
    return (
        db.query(ReferralCredit)
        .filter(ReferralCredit.user_id == user_id, ReferralCredit.kind == REFEREE)
        .first()
        is not None
    )


def _award_pair(db: Session, referee: User, contract_id: str | None) -> None:
    """Credit both halves of one referral, if this is the referee's first order."""
    if not referee.referred_by_user_id:
        return
    if has_ordered(db, referee.id):
        return
    referrer = db.query(User).filter(User.id == referee.referred_by_user_id).first()
    if referrer is None:
        # The referrer deleted their account. Nothing to pay them, and the
        # referee's half exists only as one side of a pair.
        return

    # Each side is credited in its OWN market's currency, not the order's. A
    # Ghanaian creator who referred an Ivorian business will spend the credit
    # in GHS; telling them they earned XOF would be telling them nothing. The
    # two rows can therefore carry different currencies and different amounts.
    referee_currency = market_currency(referee)
    referee_amount = referral_credit(referee_currency) if referee_currency else None
    if referee_amount is None:
        # An unpriced market earns nothing on either side, and that has to
        # include the referrer: the referee's row is also the "already
        # rewarded" flag, so writing the referrer's half without it would pay
        # them again on every order the referee ever completes.
        return

    rows = [
        ReferralCredit(
            user_id=referee.id,
            amount=referee_amount,
            currency=referee_currency,
            kind=REFEREE,
            source_user_id=referrer.id,
            contract_id=contract_id,
        )
    ]
    referrer_currency = market_currency(referrer)
    referrer_amount = referral_credit(referrer_currency) if referrer_currency else None
    if referrer_amount is not None:
        rows.append(
            ReferralCredit(
                user_id=referrer.id,
                amount=referrer_amount,
                currency=referrer_currency,
                kind=REFERRER,
                source_user_id=referee.id,
                contract_id=contract_id,
            )
        )

    # Built first, added last: every lookup that could fail has already run, so
    # the session never ends up holding half an award.
    for row in rows:
        db.add(row)


def award_for_completed_order(
    db: Session, user_ids: Iterable[str], contract_id: str | None = None
) -> None:
    """Credit referrals for every party whose first completed order this was.

    Both sides of the contract are offered up by the caller, because one code
    brings in creators and businesses alike: either party may be somebody's
    referee. Rows are added to the session and left for the caller's commit,
    so the credit lands in the same transaction as the release that earned it.
    """
    for user_id in user_ids:
        user = db.query(User).filter(User.id == user_id).first()
        if user is not None:
            _award_pair(db, user, contract_id)

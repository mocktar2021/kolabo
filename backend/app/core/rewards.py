"""Per-currency referral reward amounts.

Each value is roughly US$3-4 at launch rates: deliberately modest, because a
referral bonus is a bet that the person brought in will stay, and no retention
data exists yet to size that bet. Paying more before knowing what a retained
user is worth would be buying signups, not growth. These are launch values,
expected to be tuned per market once real order data exists — the same posture
as the package price floors in app.core.pricing.

Amounts are integers in the same minor units the rest of the platform stores
money in.
"""

REFERRAL_CREDIT: dict[str, int] = {
    "XOF": 2000,
    "XAF": 2000,
    "GHS": 40,
    "NGN": 4000,
}


def referral_credit(currency: str) -> int | None:
    """The credit for a currency, or None when it has no configured value.

    Permissive on purpose, exactly like min_price: an unknown currency simply
    earns nothing rather than raising. Which currencies are valid at all is not
    this module's question; that belongs to the payments layer that has to
    settle in them.
    """
    return REFERRAL_CREDIT.get(currency)

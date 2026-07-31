"""Per-currency price floors for creator packages.

The floors keep spam and joke listings out of the marketplace while staying
reachable for nano-creators: each floor sits around US$8-16 at launch rates.
These are launch values, expected to be tuned per market once real order data
exists.

Amounts are integers in the same minor units packages store.
"""

MIN_PACKAGE_PRICE: dict[str, int] = {
    "XOF": 5000,
    "XAF": 5000,
    "GHS": 100,
    "NGN": 10000,
}

# How many active packages a profile needs to go live (and be searchable).
# One lonely package reads as a placeholder; three make a storefront.
MIN_LIVE_PACKAGES = 3


def min_price(currency: str) -> int | None:
    """The floor for a currency, or None when it has no floor.

    Permissive on purpose: an unknown currency simply has no floor. Whether a
    currency is valid at all is not this module's job; that belongs to the
    payments layer that has to settle in it.
    """
    return MIN_PACKAGE_PRICE.get(currency)

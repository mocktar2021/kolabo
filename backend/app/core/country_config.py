"""Country settings: currency, rollout state, and the language a creator's
profile defaults to.

FOUR MARKETS ARE OPEN: Benin, Togo, Cote d'Ivoire and Senegal. Those are the
four where the payment provider can actually move money, confirmed against the
FeexPay production dashboard on 23 October 2026, where each of them carries
activated channels rather than merely appearing in a list. Naming a country is
not a guarantee of activation, and the two were conflated here for a month.

Ghana, Cameroon and Nigeria stay in this table with `enabled: False` rather
than being deleted. They keep their currency and their language default, which
is what `default_language` below needs for a party who contracts from one of
them, and reopening a market stays a one-line change. They were never payable:
GHS, XAF and NGN sit outside the XOF area the gateway's BCEAO licence covers.

The `enabled` flag is rollout state and nothing more. It says nothing about
payments readiness: whether money can actually move in a country is tracked by
the payments layer, so `enabled: True` must not be read as "fully operational".

THIS IS NOT THE ONLY COUNTRY LIST IN THE PRODUCT, and that is the defect behind
this change rather than the flags themselves. There are four, and none derives
from another:

  1. this dict
  2. the `country_configs` table seeded in modules/config/service.py, whose
     `enabled` flag is read by nothing except GET /admin/countries
  3. web/src/lib/countries.ts, the hardcoded client list that actually drives
     every country picker a user sees
  4. whatever GET /payments/config reports to the payout form

Changing one of them changes nothing anywhere else. Until one is derived from
the others, a market has to be opened or closed in all four.

`language` is a starting point for the interface and for which bio field is
written first, never a restriction: every creator can fill both the French and
English bio. Cameroon is officially bilingual and is defaulted to French
because the creator market is concentrated in the francophone regions; a
Cameroonian anglophone creator simply switches.
"""

DEFAULT_LANGUAGE = "fr"

COUNTRY_CONFIG = {
    "BJ": {"name": "Benin", "currency": "XOF", "language": "fr", "enabled": True},
    "TG": {"name": "Togo", "currency": "XOF", "language": "fr", "enabled": True},
    "CI": {"name": "Cote d'Ivoire", "currency": "XOF", "language": "fr", "enabled": True},
    "GH": {"name": "Ghana", "currency": "GHS", "language": "en", "enabled": False},
    "SN": {"name": "Senegal", "currency": "XOF", "language": "fr", "enabled": True},
    "CM": {"name": "Cameroon", "currency": "XAF", "language": "fr", "enabled": False},
    "NG": {"name": "Nigeria", "currency": "NGN", "language": "en", "enabled": False},
}


def default_language(country_code: str | None) -> str:
    """The language a creator in this country writes in first. Unknown or
    missing countries fall back rather than raising: a bio default is never
    worth failing a request over.

    Deliberately reads COUNTRY_CONFIG rather than the enabled subset. A party
    may contract from a country Kolabo does not sell in, and their bio should
    still default sensibly."""
    cfg = COUNTRY_CONFIG.get(country_code or "")
    return cfg["language"] if cfg else DEFAULT_LANGUAGE


def get_enabled_countries() -> list[str]:
    return [code for code, cfg in COUNTRY_CONFIG.items() if cfg["enabled"]]


def get_country_config(country_code: str) -> dict:
    cfg = COUNTRY_CONFIG.get(country_code)
    if cfg is None:
        raise ValueError(f"Unknown or unconfigured country: {country_code}")
    return cfg

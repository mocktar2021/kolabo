"""Country settings: currency, rollout state, and the language a creator's
profile defaults to.

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
    "CI": {"name": "Cote d'Ivoire", "currency": "XOF", "language": "fr", "enabled": False},
    "GH": {"name": "Ghana", "currency": "GHS", "language": "en", "enabled": False},
    "SN": {"name": "Senegal", "currency": "XOF", "language": "fr", "enabled": False},
    "CM": {"name": "Cameroon", "currency": "XAF", "language": "fr", "enabled": False},
    "NG": {"name": "Nigeria", "currency": "NGN", "language": "en", "enabled": False},
}


def default_language(country_code: str | None) -> str:
    """The language a creator in this country writes in first. Unknown or
    missing countries fall back rather than raising: a bio default is never
    worth failing a request over."""
    cfg = COUNTRY_CONFIG.get(country_code or "")
    return cfg["language"] if cfg else DEFAULT_LANGUAGE


def get_enabled_countries() -> list[str]:
    return [code for code, cfg in COUNTRY_CONFIG.items() if cfg["enabled"]]


def get_country_config(country_code: str) -> dict:
    cfg = COUNTRY_CONFIG.get(country_code)
    if cfg is None:
        raise ValueError(f"Unknown or unconfigured country: {country_code}")
    return cfg

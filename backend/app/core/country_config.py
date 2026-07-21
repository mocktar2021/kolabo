"""
Country configuration as data, not code.

Per Part 6.10 / Part 17 of the project plan: currency, payment provider,
phone format, verification method, and enabled features are modeled as
configuration entries so that adding a new country is a data change, not
a platform rebuild. This starter dict will move to a DB-backed table
(see backend/app/modules/admin) once the admin config UI exists — kept
as a plain dict here so the pilot (Benin, Togo) can ship without waiting
on that UI.

Provider names are placeholders pending direct provider outreach
(Part 18 open item) — do not treat as confirmed integrations.
"""

COUNTRY_CONFIG = {
    "BJ": {
        "name": "Benin",
        "currency": "XOF",
        "language_default": "fr",
        "languages_supported": ["fr"],
        "phone_country_code": "+229",
        "mobile_money_providers": ["mtn_momo", "moov_money"],  # TBD — pending provider outreach
        "manual_payout_allowed": True,
        "enabled": True,
    },
    "TG": {
        "name": "Togo",
        "currency": "XOF",
        "language_default": "fr",
        "languages_supported": ["fr"],
        "phone_country_code": "+228",
        "mobile_money_providers": ["tmoney", "flooz"],  # TBD
        "manual_payout_allowed": True,
        "enabled": True,
    },
    "CI": {
        "name": "Côte d'Ivoire", "currency": "XOF", "language_default": "fr",
        "languages_supported": ["fr"], "phone_country_code": "+225",
        "mobile_money_providers": ["orange_money", "mtn_momo", "moov_money", "wave"],
        "manual_payout_allowed": False, "enabled": False,
    },
    "GH": {
        "name": "Ghana", "currency": "GHS", "language_default": "en",
        "languages_supported": ["en"], "phone_country_code": "+233",
        "mobile_money_providers": ["mtn_momo", "telecel_cash", "airteltigo_money"],
        "manual_payout_allowed": False, "enabled": False,
    },
    "SN": {
        "name": "Senegal", "currency": "XOF", "language_default": "fr",
        "languages_supported": ["fr"], "phone_country_code": "+221",
        "mobile_money_providers": ["orange_money", "wave", "free_money"],
        "manual_payout_allowed": False, "enabled": False,
    },
    "CM": {
        "name": "Cameroon", "currency": "XAF", "language_default": "fr",
        "languages_supported": ["fr", "en"], "phone_country_code": "+237",
        "mobile_money_providers": ["mtn_momo", "orange_money", "wave"],
        "manual_payout_allowed": False, "enabled": False,
    },
    "NG": {
        "name": "Nigeria", "currency": "NGN", "language_default": "en",
        "languages_supported": ["en"], "phone_country_code": "+234",
        "mobile_money_providers": ["opay", "palmpay", "moniepoint"],
        "manual_payout_allowed": False, "enabled": False,
    },
}


def get_enabled_countries() -> list[str]:
    return [code for code, cfg in COUNTRY_CONFIG.items() if cfg["enabled"]]


def get_country_config(country_code: str) -> dict:
    cfg = COUNTRY_CONFIG.get(country_code)
    if cfg is None:
        raise ValueError(f"Unknown or unconfigured country: {country_code}")
    return cfg

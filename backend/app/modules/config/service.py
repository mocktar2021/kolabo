"""Country configuration logic (Epic I, KOL-34).

An admin can list countries, add a new one, edit it, and enable or disable it,
all as data. Adding or turning on a market is a config write, not a deploy.
Every write is attributed to an admin in the AdminActionLog.
"""
from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.admin.models import AdminActionLog
from app.modules.config import models

# Seed values for the seven target markets, all open for registration — the
# same product decision as app.core.country_config: `enabled` gates rollout
# only, not payments readiness, and stays so a market can be closed again
# with one config write. Phone prefixes are country calling codes. Providers
# are intentionally left unset until one is chosen per country.
SEED = [
    {"code": "BJ", "name": "Benin", "currency": "XOF", "phone_prefix": "+229", "enabled": True},
    {"code": "TG", "name": "Togo", "currency": "XOF", "phone_prefix": "+228", "enabled": True},
    {"code": "CI", "name": "Cote d'Ivoire", "currency": "XOF", "phone_prefix": "+225", "enabled": True},
    {"code": "GH", "name": "Ghana", "currency": "GHS", "phone_prefix": "+233", "enabled": True},
    {"code": "SN", "name": "Senegal", "currency": "XOF", "phone_prefix": "+221", "enabled": True},
    {"code": "CM", "name": "Cameroon", "currency": "XAF", "phone_prefix": "+237", "enabled": True},
    {"code": "NG", "name": "Nigeria", "currency": "NGN", "phone_prefix": "+234", "enabled": True},
]


def seed_countries(db: Session) -> None:
    """Populate the table once if it is empty. Idempotent and safe to call on boot."""
    if db.query(models.CountryConfig).count() > 0:
        return
    for row in SEED:
        db.add(models.CountryConfig(**row))
    db.commit()


def _out(c: models.CountryConfig) -> dict:
    return {
        "code": c.code,
        "name": c.name,
        "currency": c.currency,
        "phone_prefix": c.phone_prefix,
        "phone_example": c.phone_example,
        "mobile_money_provider": c.mobile_money_provider,
        "enabled": c.enabled,
    }


def list_countries(db: Session, enabled_only: bool = False) -> list[dict]:
    query = db.query(models.CountryConfig)
    if enabled_only:
        query = query.filter(models.CountryConfig.enabled.is_(True))
    return [_out(c) for c in query.order_by(models.CountryConfig.code.asc()).all()]


def get_country(db: Session, code: str) -> dict:
    c = db.query(models.CountryConfig).filter(models.CountryConfig.code == code).first()
    if c is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="country_not_configured",
            detail="Country not configured",
        )
    return _out(c)


def upsert_country(db: Session, admin_id: str, payload: dict) -> dict:
    code = payload["code"].upper()
    c = db.query(models.CountryConfig).filter(models.CountryConfig.code == code).first()
    action = "country_updated" if c else "country_added"
    if c is None:
        c = models.CountryConfig(code=code)
        db.add(c)
    c.name = payload["name"]
    c.currency = payload["currency"].upper()
    c.phone_prefix = payload["phone_prefix"]
    c.phone_example = payload.get("phone_example")
    c.mobile_money_provider = payload.get("mobile_money_provider")
    c.enabled = bool(payload.get("enabled", False))
    db.add(AdminActionLog(admin_id=admin_id, action=action, target_type="country_config", target_id=code, reason=None))
    db.commit()
    db.refresh(c)
    return _out(c)


def set_enabled(db: Session, admin_id: str, code: str, enabled: bool) -> dict:
    code = code.upper()
    c = db.query(models.CountryConfig).filter(models.CountryConfig.code == code).first()
    if c is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="country_not_configured",
            detail="Country not configured",
        )
    c.enabled = enabled
    action = "country_enabled" if enabled else "country_disabled"
    db.add(AdminActionLog(admin_id=admin_id, action=action, target_type="country_config", target_id=code, reason=None))
    db.commit()
    db.refresh(c)
    return _out(c)

"""Admin operations (Epic B verification queue, Epic I dashboard and config).

Admin authentication and role based access control are not built yet, so admin
identity is taken from an X-Admin-Id header for now. This is a deliberate
placeholder to be replaced by real admin auth in a later epic; it is enough to
attribute and log decisions during the manual pilot.
"""
from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.admin import service
from app.modules.config import service as config_service
from app.modules.config.schemas import CountryConfigIn, CountryConfigOut, EnabledIn

router = APIRouter()


def get_current_admin(x_admin_id: str | None = Header(default=None)) -> str:
    if not x_admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Admin-Id header")
    return x_admin_id


@router.get("/dashboard")
def dashboard_summary(db: Session = Depends(get_db), admin_id: str = Depends(get_current_admin)):
    """Queue counts across verification, disputes, payouts, and reports. KOL-33."""
    return service.dashboard_summary(db)


@router.get("/countries", response_model=list[CountryConfigOut])
def list_countries(
    enabled_only: bool = False,
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """List configured countries from the database. KOL-34."""
    return config_service.list_countries(db, enabled_only)


@router.post("/countries", response_model=CountryConfigOut, status_code=201)
def upsert_country(
    payload: CountryConfigIn,
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """Add or edit a country as config, no deploy required. KOL-34."""
    return config_service.upsert_country(db, admin_id, payload.model_dump())


@router.post("/countries/{code}/enabled", response_model=CountryConfigOut)
def set_country_enabled(
    code: str,
    payload: EnabledIn,
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """Turn a market on or off. KOL-34."""
    return config_service.set_enabled(db, admin_id, code, payload.enabled)


@router.get("/verification-queue")
def verification_queue(
    item_type: str | None = None,
    item_status: str | None = None,
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """List pending verification documents and social accounts. KOL-18."""
    return service.list_verification_queue(db, item_type, item_status)


@router.post("/verification-documents/{doc_id}/decision")
def decide_document(
    doc_id: str,
    decision: str = Body(..., embed=True),
    reason: str | None = Body(default=None, embed=True),
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """Approve or reject a verification document, logged with admin id. KOL-18."""
    return service.decide_document(db, admin_id, doc_id, decision, reason)


@router.post("/social-accounts/{social_id}/decision")
def decide_social(
    social_id: str,
    decision: str = Body(..., embed=True),
    reason: str | None = Body(default=None, embed=True),
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """Approve or reject a manually connected social account, logged. KOL-18."""
    return service.decide_social(db, admin_id, social_id, decision, reason)

"""Epic I (KOL-9): Admin, Analytics & Platform Configuration.

This is launch-blocking, not a back-office nicety: verification, dispute,
and payout queues live here, and the manual-process pilot depends on it.
"""
from fastapi import APIRouter

from app.core.country_config import COUNTRY_CONFIG

router = APIRouter()


@router.get("/dashboard")
def dashboard_summary():
    """See KOL-33."""
    raise NotImplementedError


@router.get("/countries")
def list_countries():
    """See KOL-34."""
    return COUNTRY_CONFIG

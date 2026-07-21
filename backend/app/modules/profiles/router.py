"""Epic B (KOL-2): Profiles & Verification."""
from fastapi import APIRouter

router = APIRouter()


@router.post("/influencer")
def create_influencer_profile():
    """See KOL-15."""
    raise NotImplementedError


@router.post("/business")
def create_business_profile():
    raise NotImplementedError


@router.post("/{profile_id}/verification-documents")
def upload_verification_document(profile_id: str):
    """See KOL-16. Documents are sensitive PII — encrypt at rest."""
    raise NotImplementedError


@router.post("/{profile_id}/social-accounts")
def connect_social_account(profile_id: str):
    """See KOL-17. Prefer OAuth where the platform supports it."""
    raise NotImplementedError

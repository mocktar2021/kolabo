"""Epic B (KOL-2): Profiles and Verification."""
from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.profiles import schemas, service

router = APIRouter()


@router.put("/influencer/{user_id}", response_model=schemas.InfluencerProfileOut)
def upsert_influencer_profile(
    user_id: str, payload: schemas.InfluencerProfileIn, db: Session = Depends(get_db)
):
    """Create or update an influencer profile. See KOL-15."""
    return service.upsert_influencer_profile(db, user_id, payload)


@router.get("/influencer/{user_id}", response_model=schemas.InfluencerProfileOut)
def get_influencer_profile(user_id: str, db: Session = Depends(get_db)):
    return service.get_influencer_profile(db, user_id)


@router.put("/business/{user_id}", response_model=schemas.BusinessProfileOut)
def upsert_business_profile(
    user_id: str, payload: schemas.BusinessProfileIn, db: Session = Depends(get_db)
):
    """Create or update a business profile."""
    return service.upsert_business_profile(db, user_id, payload)


@router.post(
    "/{user_id}/verification-documents",
    response_model=schemas.VerificationDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_verification_document(
    user_id: str,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a verification document, stored encrypted with status pending. KOL-16."""
    content = await file.read()
    return service.upload_verification_document(db, user_id, doc_type, file.filename, content)


@router.post(
    "/{user_id}/social-accounts",
    response_model=schemas.SocialAccountOut,
    status_code=status.HTTP_201_CREATED,
)
def connect_social_account(
    user_id: str, payload: schemas.SocialAccountConnect, db: Session = Depends(get_db)
):
    """Connect a social account via OAuth (verified) or manual proof (pending). KOL-17."""
    return service.connect_social_account(db, user_id, payload)

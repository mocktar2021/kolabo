"""Epic B (KOL-2): Profiles and Verification, plus packages and profile media.

Admin/RBAC is still the placeholder from Epic B, so these endpoints identify the
profile owner by the user id in the path rather than a bearer token. Real auth
replaces this in a later epic.
"""
from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
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


@router.get("/influencer/{user_id}/public", response_model=schemas.PublicProfileOut)
def public_influencer_profile(user_id: str, language: str | None = None, db: Session = Depends(get_db)):
    """Public creator page: profile, packages, portfolio, rating, socials.

    `language` (fr or en) picks which bio to show, falling back to the other
    when the creator has only filled one.
    """
    return service.get_public_profile(db, user_id, language)


@router.get("/influencer/{user_id}", response_model=schemas.InfluencerProfileOut)
def get_influencer_profile(user_id: str, db: Session = Depends(get_db)):
    return service.get_influencer_profile(db, user_id)


@router.put("/business/{user_id}", response_model=schemas.BusinessProfileOut)
def upsert_business_profile(
    user_id: str, payload: schemas.BusinessProfileIn, db: Session = Depends(get_db)
):
    """Create or update a business profile."""
    return service.upsert_business_profile(db, user_id, payload)


@router.get("/business/{user_id}", response_model=schemas.BusinessProfileOut)
def get_business_profile(user_id: str, db: Session = Depends(get_db)):
    """Load a business profile for editing.

    The profile was write-only until now: the PUT existed without a GET, so
    the settings page had nothing to prefill and came up blank on every visit.
    """
    return service.get_business_profile(db, user_id)


@router.get("/media/{media_id}")
def serve_media(media_id: str, db: Session = Depends(get_db)):
    """Serve a stored profile image."""
    asset = service.get_media(db, media_id)
    return Response(content=asset.data, media_type=asset.content_type)


@router.post("/{user_id}/media", response_model=schemas.MediaOut, status_code=status.HTTP_201_CREATED)
async def upload_media(user_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a profile image (avatar or portfolio)."""
    content = await file.read()
    return service.save_media(db, user_id, file.content_type or "application/octet-stream", content)


@router.get("/{user_id}/packages", response_model=list[schemas.PackageOut])
def list_packages(user_id: str, active_only: bool = False, db: Session = Depends(get_db)):
    """List a creator's fixed-price packages."""
    return service.list_packages(db, user_id, active_only)


@router.post("/{user_id}/packages", response_model=schemas.PackageOut, status_code=status.HTTP_201_CREATED)
def create_package(user_id: str, payload: schemas.PackageIn, db: Session = Depends(get_db)):
    return service.create_package(db, user_id, payload)


@router.put("/{user_id}/packages/{package_id}", response_model=schemas.PackageOut)
def update_package(user_id: str, package_id: str, payload: schemas.PackageIn, db: Session = Depends(get_db)):
    return service.update_package(db, package_id, user_id, payload)


@router.delete("/{user_id}/packages/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_package(user_id: str, package_id: str, db: Session = Depends(get_db)):
    service.delete_package(db, package_id, user_id)


@router.get("/{user_id}/portfolio", response_model=list[schemas.PortfolioItemOut])
def list_portfolio(user_id: str, db: Session = Depends(get_db)):
    return service.list_portfolio(db, user_id)


@router.post("/{user_id}/portfolio", response_model=schemas.PortfolioItemOut, status_code=status.HTTP_201_CREATED)
def add_portfolio_item(user_id: str, payload: schemas.PortfolioItemIn, db: Session = Depends(get_db)):
    return service.add_portfolio_item(db, user_id, payload.media_id)


@router.delete("/{user_id}/portfolio/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_portfolio_item(user_id: str, item_id: str, db: Session = Depends(get_db)):
    service.remove_portfolio_item(db, item_id, user_id)


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


@router.post("/{user_id}/bio/generate", response_model=schemas.BioGenerateOut)
def generate_bio(user_id: str, payload: schemas.BioGenerateIn, db: Session = Depends(get_db)):
    """Draft a bio in French or English from the creator's own profile facts.

    Returns a draft; nothing is written to the profile until the creator saves.
    """
    return service.generate_bio(db, user_id, payload)


@router.get("/{user_id}/social-accounts", response_model=list[schemas.SocialAccountOut])
def list_social_accounts(user_id: str, db: Session = Depends(get_db)):
    """Social accounts connected to this profile."""
    return service.list_social_accounts(db, user_id)


@router.get("/{user_id}/onboarding-status", response_model=schemas.OnboardingStatusOut)
def onboarding_status(user_id: str, db: Session = Depends(get_db)):
    """What is still missing before the creator profile can go live."""
    return service.onboarding_status(db, user_id)


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


@router.put("/{user_id}/social-accounts/{account_id}", response_model=schemas.SocialAccountOut)
def update_social_account(
    user_id: str, account_id: str, payload: schemas.SocialAccountUpdate, db: Session = Depends(get_db)
):
    """Edit a connected account. Changing the handle of a verified account
    resets it to pending: the badge was earned by the old handle."""
    return service.update_social_account(db, user_id, account_id, payload)


@router.delete("/{user_id}/social-accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_social_account(user_id: str, account_id: str, db: Session = Depends(get_db)):
    """Disconnect a social account from the profile."""
    service.delete_social_account(db, user_id, account_id)

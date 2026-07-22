"""Profiles and verification business logic (Epic B).

KOL-15: influencer profile with required fields enforced before it is
searchable, and a completion percentage.
KOL-16: business verification document upload, stored encrypted, with a status
of pending, approved, or rejected and a reason.
KOL-17: connect a social account. OAuth proves ownership so it is marked
verified; the manual fallback is marked pending for admin review. The OAuth
handshake itself is stubbed until a provider is wired in.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_bytes
from app.modules.auth.models import User
from app.modules.profiles import models, schemas

# Required influencer fields drive both completion percentage and searchability.
INFLUENCER_REQUIRED = ("bio", "categories", "rate_card")
DOC_TYPES = {"business_registration", "identity"}


def _require_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _influencer_completion(profile: models.InfluencerProfile) -> tuple[int, bool]:
    present = 0
    if profile.bio:
        present += 1
    if profile.categories:
        present += 1
    if profile.rate_card:
        present += 1
    total = len(INFLUENCER_REQUIRED)
    percent = round(present / total * 100)
    is_searchable = present == total
    return percent, is_searchable


def upsert_influencer_profile(db: Session, user_id: str, payload: schemas.InfluencerProfileIn) -> dict:
    _require_user(db, user_id)
    profile = db.query(models.InfluencerProfile).filter(models.InfluencerProfile.user_id == user_id).first()
    if profile is None:
        profile = models.InfluencerProfile(user_id=user_id)
        db.add(profile)
    profile.bio = payload.bio
    profile.categories = payload.categories
    profile.rate_card = payload.rate_card
    profile.follower_count = payload.follower_count
    db.commit()
    db.refresh(profile)
    percent, is_searchable = _influencer_completion(profile)
    return {
        "user_id": profile.user_id,
        "bio": profile.bio,
        "categories": profile.categories,
        "rate_card": profile.rate_card,
        "follower_count": profile.follower_count,
        "completion_percent": percent,
        "is_searchable": is_searchable,
    }


def get_influencer_profile(db: Session, user_id: str) -> dict:
    profile = db.query(models.InfluencerProfile).filter(models.InfluencerProfile.user_id == user_id).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    percent, is_searchable = _influencer_completion(profile)
    return {
        "user_id": profile.user_id,
        "bio": profile.bio,
        "categories": profile.categories,
        "rate_card": profile.rate_card,
        "follower_count": profile.follower_count,
        "completion_percent": percent,
        "is_searchable": is_searchable,
    }


def upsert_business_profile(db: Session, user_id: str, payload: schemas.BusinessProfileIn) -> dict:
    _require_user(db, user_id)
    profile = db.query(models.BusinessProfile).filter(models.BusinessProfile.user_id == user_id).first()
    if profile is None:
        profile = models.BusinessProfile(user_id=user_id, company_name=payload.company_name)
        db.add(profile)
    profile.company_name = payload.company_name
    profile.industry = payload.industry
    profile.description = payload.description
    db.commit()
    db.refresh(profile)
    return {
        "user_id": profile.user_id,
        "company_name": profile.company_name,
        "industry": profile.industry,
        "description": profile.description,
    }


def upload_verification_document(db: Session, user_id: str, doc_type: str, filename: str, content: bytes) -> dict:
    _require_user(db, user_id)
    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"doc_type must be one of {sorted(DOC_TYPES)}")
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty document")
    doc = models.VerificationDocument(
        user_id=user_id,
        doc_type=doc_type,
        filename=filename,
        ciphertext=encrypt_bytes(content),
        status=models.PENDING,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "doc_type": doc.doc_type, "filename": doc.filename, "status": doc.status, "rejection_reason": None}


def connect_social_account(db: Session, user_id: str, payload: schemas.SocialAccountConnect) -> dict:
    _require_user(db, user_id)
    if payload.platform not in schemas.SOCIAL_PLATFORMS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported platform")
    if payload.method not in schemas.SOCIAL_METHODS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="method must be oauth or manual")
    if payload.method == "manual" and not payload.proof_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Manual connection requires a proof_url")

    # OAuth proves ownership, so it is verified immediately. The OAuth handshake
    # is stubbed until a provider app is registered; the manual path waits for
    # admin review.
    new_status = models.VERIFIED if payload.method == "oauth" else models.PENDING
    account = models.SocialAccount(
        user_id=user_id,
        platform=payload.platform,
        handle=payload.handle,
        method=payload.method,
        status=new_status,
        proof_url=payload.proof_url,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return {"id": account.id, "platform": account.platform, "handle": account.handle, "method": account.method, "status": account.status}

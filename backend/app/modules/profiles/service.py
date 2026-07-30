"""Profiles and verification business logic (Epic B) plus packages and media.

KOL-15: influencer profile with required fields enforced before it is
searchable, and a completion percentage.
KOL-16: business verification document upload, stored encrypted.
KOL-17: connect a social account (OAuth verified, manual pending).

Packages, portfolio images, and a public profile aggregate support the
instant-hire model and the shareable creator page.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_bytes
from app.modules.auth.models import User
from app.modules.profiles import models, schemas

INFLUENCER_REQUIRED = ("bio", "categories", "rate_card")
DOC_TYPES = {"business_registration", "identity"}
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def _require_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _media_url(media_id: str | None) -> str | None:
    return f"/profiles/media/{media_id}" if media_id else None


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


def _influencer_out(profile: models.InfluencerProfile) -> dict:
    percent, is_searchable = _influencer_completion(profile)
    return {
        "user_id": profile.user_id,
        "display_name": profile.display_name,
        "headline": profile.headline,
        "location": profile.location,
        "avatar_media_id": profile.avatar_media_id,
        "avatar_url": _media_url(profile.avatar_media_id),
        "bio": profile.bio,
        "categories": profile.categories,
        "rate_card": profile.rate_card,
        "follower_count": profile.follower_count,
        "completion_percent": percent,
        "is_searchable": is_searchable,
    }


def upsert_influencer_profile(db: Session, user_id: str, payload: schemas.InfluencerProfileIn) -> dict:
    _require_user(db, user_id)
    profile = db.query(models.InfluencerProfile).filter(models.InfluencerProfile.user_id == user_id).first()
    if profile is None:
        profile = models.InfluencerProfile(user_id=user_id)
        db.add(profile)
    profile.display_name = payload.display_name
    profile.headline = payload.headline
    profile.location = payload.location
    profile.avatar_media_id = payload.avatar_media_id
    profile.bio = payload.bio
    profile.categories = payload.categories
    profile.rate_card = payload.rate_card
    profile.follower_count = payload.follower_count
    db.commit()
    db.refresh(profile)
    return _influencer_out(profile)


def get_influencer_profile(db: Session, user_id: str) -> dict:
    profile = db.query(models.InfluencerProfile).filter(models.InfluencerProfile.user_id == user_id).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return _influencer_out(profile)


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


# ---- Media ----

def save_media(db: Session, user_id: str, content_type: str, data: bytes) -> dict:
    _require_user(db, user_id)
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only JPEG, PNG, WEBP, or GIF images are allowed")
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    asset = models.MediaAsset(owner_user_id=user_id, content_type=content_type, data=data)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {"id": asset.id, "url": _media_url(asset.id)}


def get_media(db: Session, media_id: str) -> models.MediaAsset:
    asset = db.query(models.MediaAsset).filter(models.MediaAsset.id == media_id).first()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    return asset


# ---- Packages ----

def _package_out(p: models.Package) -> dict:
    return {
        "id": p.id,
        "user_id": p.user_id,
        "platform": p.platform,
        "deliverable_type": p.deliverable_type,
        "title": p.title,
        "description": p.description,
        "price_amount": p.price_amount,
        "currency": p.currency,
        "is_active": p.is_active,
    }


def list_packages(db: Session, user_id: str, active_only: bool = False) -> list[dict]:
    query = db.query(models.Package).filter(models.Package.user_id == user_id)
    if active_only:
        query = query.filter(models.Package.is_active.is_(True))
    return [_package_out(p) for p in query.order_by(models.Package.created_at.asc()).all()]


def create_package(db: Session, user_id: str, payload: schemas.PackageIn) -> dict:
    _require_user(db, user_id)
    pkg = models.Package(
        user_id=user_id,
        platform=payload.platform,
        deliverable_type=payload.deliverable_type,
        title=payload.title,
        description=payload.description,
        price_amount=payload.price_amount,
        currency=payload.currency.upper(),
        is_active=payload.is_active,
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return _package_out(pkg)


def update_package(db: Session, package_id: str, user_id: str, payload: schemas.PackageIn) -> dict:
    pkg = db.query(models.Package).filter(models.Package.id == package_id).first()
    if pkg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
    if pkg.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your package")
    pkg.platform = payload.platform
    pkg.deliverable_type = payload.deliverable_type
    pkg.title = payload.title
    pkg.description = payload.description
    pkg.price_amount = payload.price_amount
    pkg.currency = payload.currency.upper()
    pkg.is_active = payload.is_active
    db.commit()
    db.refresh(pkg)
    return _package_out(pkg)


def delete_package(db: Session, package_id: str, user_id: str) -> None:
    pkg = db.query(models.Package).filter(models.Package.id == package_id).first()
    if pkg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
    if pkg.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your package")
    db.delete(pkg)
    db.commit()


# ---- Portfolio ----

def _portfolio_out(item: models.PortfolioItem) -> dict:
    return {"id": item.id, "media_id": item.media_id, "url": _media_url(item.media_id)}


def list_portfolio(db: Session, user_id: str) -> list[dict]:
    items = (
        db.query(models.PortfolioItem)
        .filter(models.PortfolioItem.user_id == user_id)
        .order_by(models.PortfolioItem.position.asc(), models.PortfolioItem.created_at.asc())
        .all()
    )
    return [_portfolio_out(i) for i in items]


def add_portfolio_item(db: Session, user_id: str, media_id: str) -> dict:
    _require_user(db, user_id)
    asset = db.query(models.MediaAsset).filter(models.MediaAsset.id == media_id).first()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    count = db.query(models.PortfolioItem).filter(models.PortfolioItem.user_id == user_id).count()
    item = models.PortfolioItem(user_id=user_id, media_id=media_id, position=count)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _portfolio_out(item)


def remove_portfolio_item(db: Session, item_id: str, user_id: str) -> None:
    item = db.query(models.PortfolioItem).filter(models.PortfolioItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio item not found")
    if item.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your portfolio")
    db.delete(item)
    db.commit()


# ---- Public profile aggregate ----

def get_public_profile(db: Session, user_id: str) -> dict:
    profile = db.query(models.InfluencerProfile).filter(models.InfluencerProfile.user_id == user_id).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    from app.modules.trust_safety.service import user_reviews

    reviews = user_reviews(db, user_id)
    social = (
        db.query(models.SocialAccount)
        .filter(models.SocialAccount.user_id == user_id, models.SocialAccount.status == models.VERIFIED)
        .all()
    )
    return {
        "user_id": profile.user_id,
        "display_name": profile.display_name,
        "headline": profile.headline,
        "location": profile.location,
        "avatar_url": _media_url(profile.avatar_media_id),
        "bio": profile.bio,
        "categories": profile.categories,
        "follower_count": profile.follower_count,
        "is_searchable": _influencer_completion(profile)[1],
        "average_stars": reviews["average_stars"],
        "review_count": reviews["count"],
        "packages": list_packages(db, user_id, active_only=True),
        "portfolio": list_portfolio(db, user_id),
        "social_accounts": [
            {"id": s.id, "platform": s.platform, "handle": s.handle, "method": s.method, "status": s.status}
            for s in social
        ],
    }

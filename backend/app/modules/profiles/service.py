"""Profiles and verification business logic (Epic B) plus packages and media.

KOL-15: influencer profile with required fields enforced before it is
searchable, and a completion percentage.
KOL-16: business verification document upload, stored encrypted.
KOL-17: connect a social account (OAuth verified, manual pending).

Packages, portfolio images, and a public profile aggregate support the
instant-hire model and the shareable creator page.
"""
from datetime import date

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.country_config import COUNTRY_CONFIG, default_language
from app.core.crypto import encrypt_bytes
from app.core.errors import AppError
from app.core.platforms import PLATFORM_DELIVERABLES, PLATFORMS_WITH_AUDIENCE, is_valid_pair
from app.core.pricing import MIN_LIVE_PACKAGES, min_price
from app.modules.auth.models import User
from app.modules.profiles import bio_ai, enrichment, models, schemas

# What a complete profile needs: a bio, categories, and a storefront of
# packages (MIN_LIVE_PACKAGES active ones). The legacy rate card no longer
# counts as pricing — product decision: a free-text rate card cannot be
# ordered, so it kept profiles "complete" with nothing a buyer could buy.
INFLUENCER_REQUIRED = ("bio", "categories", "packages")
DOC_TYPES = {"business_registration", "identity"}
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# Creators must be adults: legal register, child-safety item.
MINIMUM_CREATOR_AGE = 18

# How many reviews the public page lists. The page needs recent proof, not a
# full history; the average still covers every revealed review.
PUBLIC_REVIEWS_LIMIT = 20

social_enricher = enrichment.default_enricher
bio_generator = bio_ai.default_generator


def _any_bio(profile: models.InfluencerProfile) -> str | None:
    """A profile counts as having a bio when either language is filled. The
    legacy single column is still honoured until it is dropped."""
    return profile.bio_fr or profile.bio_en or profile.bio


def resolve_bio(profile: models.InfluencerProfile, language: str | None = None) -> str | None:
    """The bio to show a viewer. Prefer their language, but never show an empty
    profile to someone whose language the creator has not filled in yet: a bio
    in the other language is far better than nothing."""
    if language == "en":
        return profile.bio_en or profile.bio_fr or profile.bio
    if language == "fr":
        return profile.bio_fr or profile.bio_en or profile.bio
    return _any_bio(profile)


def _require_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            # auth's code, not a profiles one. It is the same rule — no such
            # user — and a code names the rule, not the module it fired in.
            code="auth_user_not_found",
            detail="User not found",
        )
    return user


def _require_adult(birth_date: date) -> None:
    """Creators must be adults; reject any birth date under MINIMUM_CREATOR_AGE.

    A person is 18 on their 18th birthday, not the day after: the (month, day)
    tuple comparison subtracts a year only while this year's birthday is still
    ahead, which also handles the not-yet-had-their-birthday-this-year case.
    """
    today = date.today()
    age = today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )
    if age < MINIMUM_CREATOR_AGE:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="profile_under_age",
            detail="You must be at least 18 to create a creator profile.",
            values={"min": MINIMUM_CREATOR_AGE},
        )


def _media_url(media_id: str | None) -> str | None:
    return f"/profiles/media/{media_id}" if media_id else None


def _active_package_count(db: Session, user_id: str) -> int:
    return (
        db.query(models.Package)
        .filter(models.Package.user_id == user_id, models.Package.is_active.is_(True))
        .count()
    )


def _influencer_completion(profile: models.InfluencerProfile, active_package_count: int) -> tuple[int, bool]:
    present = 0
    if _any_bio(profile):
        present += 1
    if profile.categories:
        present += 1
    # Pricing means a storefront: MIN_LIVE_PACKAGES active packages. The
    # legacy rate card no longer counts — see INFLUENCER_REQUIRED.
    if active_package_count >= MIN_LIVE_PACKAGES:
        present += 1
    total = len(INFLUENCER_REQUIRED)
    percent = round(present / total * 100)
    is_searchable = present == total
    return percent, is_searchable


def _influencer_out(db: Session, profile: models.InfluencerProfile) -> dict:
    percent, is_searchable = _influencer_completion(profile, _active_package_count(db, profile.user_id))
    return {
        "user_id": profile.user_id,
        "display_name": profile.display_name,
        "headline": profile.headline,
        "location": profile.location,
        "avatar_media_id": profile.avatar_media_id,
        "avatar_url": _media_url(profile.avatar_media_id),
        "bio": _any_bio(profile),
        "bio_fr": profile.bio_fr,
        "bio_en": profile.bio_en,
        "categories": profile.categories,
        "rate_card": profile.rate_card,
        "faq": profile.faq or {},
        "follower_count": profile.follower_count,
        # Owner-facing view: birth_date and gender belong here (the edit form
        # prefills from them) and only here; the public payload never carries
        # either.
        "birth_date": profile.birth_date,
        "gender": profile.gender,
        "languages": profile.languages or [],
        "completion_percent": percent,
        "is_searchable": is_searchable,
    }


def upsert_influencer_profile(db: Session, user_id: str, payload: schemas.InfluencerProfileIn) -> dict:
    _require_user(db, user_id)
    profile = db.query(models.InfluencerProfile).filter(models.InfluencerProfile.user_id == user_id).first()
    if profile is None:
        profile = models.InfluencerProfile(user_id=user_id)
        db.add(profile)
    # Only apply what the client actually sent. Assigning every column
    # unconditionally meant a form that did not know about a field deleted it:
    # the onboarding wizard omits avatar_media_id, so pressing Continue wiped
    # the avatar that enrichment had just downloaded from YouTube.
    #
    # exclude_unset draws the line at omission, not at emptiness: a field the
    # client explicitly sent as null IS still cleared, because that is how a
    # creator deletes their headline or removes their photo. Only leaving the
    # key out entirely is now a no-op.
    data = payload.model_dump(exclude_unset=True)
    # The 18+ gate runs on write, every time the field is present: a stored
    # birth date is re-validated the moment the client sends it again, so
    # resubmitting the form cannot bypass a value that is already saved.
    if data.get("birth_date") is not None:
        _require_adult(data["birth_date"])
    for field, value in data.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return _influencer_out(db, profile)


def get_influencer_profile(db: Session, user_id: str) -> dict:
    profile = db.query(models.InfluencerProfile).filter(models.InfluencerProfile.user_id == user_id).first()
    if profile is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="profile_not_found",
            detail="Profile not found",
        )
    return _influencer_out(db, profile)


def _business_out(profile: models.BusinessProfile) -> dict:
    return {
        "user_id": profile.user_id,
        "company_name": profile.company_name,
        "industry": profile.industry,
        "description": profile.description,
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
    return _business_out(profile)


def get_business_profile(db: Session, user_id: str) -> dict:
    """Read back a saved business profile, mirroring get_influencer_profile.

    Businesses could write their profile but never read it: the PUT had no
    matching GET, so the settings form had nothing to prefill.
    """
    profile = db.query(models.BusinessProfile).filter(models.BusinessProfile.user_id == user_id).first()
    if profile is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="profile_not_found",
            detail="Profile not found",
        )
    return _business_out(profile)


def upload_verification_document(db: Session, user_id: str, doc_type: str, filename: str, content: bytes) -> dict:
    _require_user(db, user_id)
    if doc_type not in DOC_TYPES:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="profile_doc_type_unknown",
            detail=f"doc_type must be one of {sorted(DOC_TYPES)}",
            # Machine values the client posts back, untranslated for the same
            # reason as every other such list: a French rendering would be a
            # list no endpoint accepts.
            values={"types": ", ".join(sorted(DOC_TYPES))},
        )
    if not content:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="profile_document_empty",
            detail="Empty document",
        )
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
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="profile_platform_unsupported",
            detail="Unsupported platform",
        )
    if payload.method not in schemas.SOCIAL_METHODS:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="profile_social_method_unknown",
            detail="method must be oauth or manual",
        )
    if payload.method == "manual" and not payload.proof_url:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="profile_proof_url_required",
            detail="Manual connection requires a proof_url",
        )

    # WhatsApp Status, Discord and UGC expose no public follower metric, so any
    # number supplied for them is unverifiable. Drop it rather than show a buyer
    # a figure the platform itself cannot confirm.
    follower_count = payload.follower_count if payload.platform in PLATFORMS_WITH_AUDIENCE else None

    new_status = models.VERIFIED if payload.method == "oauth" else models.PENDING
    account = models.SocialAccount(
        user_id=user_id,
        platform=payload.platform,
        handle=payload.handle,
        method=payload.method,
        status=new_status,
        proof_url=payload.proof_url,
        follower_count=follower_count,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    enriched = _apply_enrichment(db, user_id, payload.platform, payload.handle, account)
    db.refresh(account)
    return {
        "id": account.id,
        "platform": account.platform,
        "handle": account.handle,
        "method": account.method,
        "status": account.status,
        "follower_count": account.follower_count,
        "enriched": enriched,
    }


def _apply_enrichment(db: Session, user_id: str, platform: str, handle: str, account=None) -> bool:
    """Fill empty profile fields from the platform, never overwriting the
    creator's own edits. Returns whether anything was filled."""
    data = social_enricher.fetch(platform, handle)
    if not data:
        return False
    profile = db.query(models.InfluencerProfile).filter(models.InfluencerProfile.user_id == user_id).first()
    if profile is None:
        profile = models.InfluencerProfile(user_id=user_id)
        db.add(profile)
    filled = False
    if not profile.display_name and data.get("display_name"):
        profile.display_name = data["display_name"]
        filled = True
    if data.get("bio") and not _any_bio(profile):
        # A platform bio is written in one language; file it under the one the
        # creator's country uses rather than guessing it covers both.
        user = db.query(User).filter(User.id == user_id).first()
        language = default_language(user.country_code if user else None)
        if language == "en":
            profile.bio_en = data["bio"]
        else:
            profile.bio_fr = data["bio"]
        filled = True
    if data.get("follower_count") is not None:
        # The count belongs to the platform account; the profile keeps a total
        # only as a fallback for creators who never connected an account.
        if account is not None and account.follower_count is None:
            account.follower_count = data["follower_count"]
            filled = True
        if profile.follower_count is None:
            profile.follower_count = data["follower_count"]
            filled = True
    if not profile.avatar_media_id and data.get("avatar_image_url"):
        downloaded = enrichment.fetch_image(data["avatar_image_url"])
        if downloaded:
            content, content_type = downloaded
            asset = models.MediaAsset(owner_user_id=user_id, content_type=content_type, data=content)
            db.add(asset)
            db.flush()
            profile.avatar_media_id = asset.id
            filled = True
    if filled:
        db.commit()
    return filled


def generate_bio(db: Session, user_id: str, payload: schemas.BioGenerateIn) -> dict:
    """Draft a bio from facts the platform already holds.

    The result is returned, not saved. The creator accepts it by saving the
    profile, so a draft they dislike never lands on their public page.
    """
    user = _require_user(db, user_id)
    profile = db.query(models.InfluencerProfile).filter(models.InfluencerProfile.user_id == user_id).first()
    if profile is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="profile_not_found",
            detail="Profile not found",
        )

    if not getattr(bio_generator, "available", False):
        raise AppError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            code="profile_bio_ai_unavailable",
            detail="Bio generation is not configured. Write your bio yourself for now.",
        )

    remaining = settings.bio_generation_limit - (profile.bio_generations or 0)
    if remaining <= 0:
        raise AppError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            code="profile_bio_limit_reached",
            detail="You have reached the limit for generated bios. Edit the text yourself instead.",
        )

    accounts = list_social_accounts(db, user_id)
    facts = {
        "display_name": profile.display_name,
        # The country name, never the code: "BJ" in a bio prompt reads as noise
        # and the model has no reason to expand it correctly.
        "location": profile.location or (COUNTRY_CONFIG.get(user.country_code) or {}).get("name"),
        "categories": profile.categories or [],
        "platforms": [a["platform"] for a in accounts],
    }
    if not bio_ai.has_enough_facts(facts):
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="profile_bio_needs_categories",
            detail="Choose at least one content category first, so the bio describes you and not a generic creator.",
        )

    text = bio_generator.generate(facts, payload.language)
    if not text:
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            code="profile_bio_failed",
            detail="Could not draft a bio right now. Try again, or write your own.",
        )

    # Counted on success only: a failed call costs the creator nothing.
    profile.bio_generations = (profile.bio_generations or 0) + 1
    db.commit()

    return {
        "language": payload.language,
        "bio": text,
        "saved": False,
        "generations_remaining": settings.bio_generation_limit - profile.bio_generations,
    }


def list_social_accounts(db: Session, user_id: str) -> list[dict]:
    accounts = (
        db.query(models.SocialAccount)
        .filter(models.SocialAccount.user_id == user_id)
        .order_by(models.SocialAccount.created_at.asc())
        .all()
    )
    return [
        {
            "id": a.id, "platform": a.platform, "handle": a.handle, "method": a.method,
            "status": a.status, "follower_count": a.follower_count,
        }
        for a in accounts
    ]


def _require_own_social_account(db: Session, user_id: str, account_id: str) -> models.SocialAccount:
    """404 before 403: an attacker probing other people's account ids learns
    nothing more than a stranger guessing random ids would."""
    account = db.query(models.SocialAccount).filter(models.SocialAccount.id == account_id).first()
    if account is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="profile_social_not_found",
            detail="Social account not found",
        )
    if account.user_id != user_id:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="profile_social_not_yours",
            detail="Not your social account",
        )
    return account


def update_social_account(db: Session, user_id: str, account_id: str, payload: schemas.SocialAccountUpdate) -> dict:
    account = _require_own_social_account(db, user_id, account_id)
    data = payload.model_dump(exclude_unset=True)
    if "handle" in data and data["handle"] != account.handle:
        # A verified badge belongs to the account that was verified. A new
        # handle points at a different account, so the badge must not survive
        # the edit: back to pending until that account passes review too.
        if account.status == models.VERIFIED:
            account.status = models.PENDING
        account.handle = data["handle"]
    if "follower_count" in data:
        # Same rule as connect: platforms without a public audience metric
        # cannot back the number, so it is discarded rather than displayed.
        account.follower_count = (
            data["follower_count"] if account.platform in PLATFORMS_WITH_AUDIENCE else None
        )
    if "proof_url" in data:
        account.proof_url = data["proof_url"]
    db.commit()
    db.refresh(account)
    return {
        "id": account.id, "platform": account.platform, "handle": account.handle,
        "method": account.method, "status": account.status, "follower_count": account.follower_count,
    }


def delete_social_account(db: Session, user_id: str, account_id: str) -> None:
    account = _require_own_social_account(db, user_id, account_id)
    db.delete(account)
    db.commit()


def onboarding_status(db: Session, user_id: str) -> dict:
    """What the creator still needs before the profile can go live."""
    profile = db.query(models.InfluencerProfile).filter(models.InfluencerProfile.user_id == user_id).first()
    active_packages = _active_package_count(db, user_id)
    has_bio = bool(profile and _any_bio(profile))
    has_categories = bool(profile and profile.categories)
    # Pricing now means a storefront: at least MIN_LIVE_PACKAGES active
    # packages. Product decision — the legacy rate card no longer suffices,
    # because a free-text rate card cannot be ordered; it kept profiles "live"
    # with nothing a buyer could actually buy. No grandfathering: a profile
    # that was live on rate card alone drops back until it adds packages.
    has_pricing = active_packages >= MIN_LIVE_PACKAGES
    # Going live requires the 18+ gate to have been passed: the birth date is
    # private data, but its presence is a hard prerequisite.
    has_birth_date = bool(profile and profile.birth_date)
    return {
        "has_bio": has_bio,
        "has_categories": has_categories,
        "has_pricing": has_pricing,
        "has_packages": active_packages > 0,
        "has_social": len(list_social_accounts(db, user_id)) > 0,
        "has_birth_date": has_birth_date,
        "active_package_count": active_packages,
        "is_live": has_bio and has_categories and has_pricing and has_birth_date,
    }


# ---- Media ----

def save_media(db: Session, user_id: str, content_type: str, data: bytes) -> dict:
    _require_user(db, user_id)
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="profile_image_type_unsupported",
            detail="Only JPEG, PNG, WEBP, or GIF images are allowed",
        )
    if not data:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="profile_file_empty",
            detail="Empty file",
        )
    asset = models.MediaAsset(owner_user_id=user_id, content_type=content_type, data=data)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {"id": asset.id, "url": _media_url(asset.id)}


def get_media(db: Session, media_id: str) -> models.MediaAsset:
    asset = db.query(models.MediaAsset).filter(models.MediaAsset.id == media_id).first()
    if asset is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="profile_image_not_found",
            detail="Image not found",
        )
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
        "quantity": p.quantity,
        "duration_value": p.duration_value,
        "duration_unit": p.duration_unit,
        "is_active": p.is_active,
    }


def list_packages(db: Session, user_id: str, active_only: bool = False) -> list[dict]:
    query = db.query(models.Package).filter(models.Package.user_id == user_id)
    if active_only:
        query = query.filter(models.Package.is_active.is_(True))
    return [_package_out(p) for p in query.order_by(models.Package.created_at.asc()).all()]


def _validate_pair(platform: str, deliverable_type: str) -> None:
    if not is_valid_pair(platform, deliverable_type):
        allowed = ", ".join(PLATFORM_DELIVERABLES.get(platform, [])) or "none"
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="profile_deliverable_not_on_platform",
            detail=f"{deliverable_type} is not available on {platform}. Allowed: {allowed}",
            # The platform and the deliverable type are machine values the
            # client chose from a list it already renders in the reader's
            # language; the sentence around them is what needed translating.
            values={"type": deliverable_type, "platform": platform, "allowed": allowed},
        )


def _validate_price_floor(price_amount: int, currency: str) -> None:
    """Reject prices below the per-currency floor (spam defence).

    `currency` must already be uppercased; unknown currencies have no floor
    and pass — see app.core.pricing.min_price.
    """
    floor = min_price(currency)
    if floor is not None and price_amount < floor:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="profile_price_below_floor",
            detail=f"Minimum price for {currency} is {floor}.",
            values={"currency": currency, "floor": floor},
        )


def _validate_duration(duration_value: int | None, duration_unit: str | None) -> None:
    """The duration is a pair or nothing. "30" of nothing and "seconds" of
    nothing are both meaningless chips, so one without the other is rejected
    outright rather than silently dropped."""
    if (duration_value is None) != (duration_unit is None):
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="profile_duration_pair",
            detail="duration_value and duration_unit go together.",
        )


def create_package(db: Session, user_id: str, payload: schemas.PackageIn) -> dict:
    _require_user(db, user_id)
    _validate_pair(payload.platform, payload.deliverable_type)
    _validate_duration(payload.duration_value, payload.duration_unit)
    currency = payload.currency.upper()
    # The floor applies to the package price as a whole, regardless of
    # quantity: a ×10 bundle cannot undercut it by spreading the price across
    # ten deliverables — being impossible to undercut is the point of a floor.
    _validate_price_floor(payload.price_amount, currency)
    pkg = models.Package(
        user_id=user_id,
        platform=payload.platform,
        deliverable_type=payload.deliverable_type,
        title=payload.title,
        description=payload.description,
        price_amount=payload.price_amount,
        currency=currency,
        quantity=payload.quantity,
        duration_value=payload.duration_value,
        duration_unit=payload.duration_unit,
        is_active=payload.is_active,
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return _package_out(pkg)


def update_package(db: Session, package_id: str, user_id: str, payload: schemas.PackageIn) -> dict:
    pkg = db.query(models.Package).filter(models.Package.id == package_id).first()
    if pkg is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="profile_package_not_found",
            detail="Package not found",
        )
    if pkg.user_id != user_id:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="profile_package_not_yours",
            detail="Not your package",
        )
    _validate_pair(payload.platform, payload.deliverable_type)
    _validate_duration(payload.duration_value, payload.duration_unit)
    currency = payload.currency.upper()
    # Same rule as create: the floor is per package, whatever the quantity.
    _validate_price_floor(payload.price_amount, currency)
    pkg.platform = payload.platform
    pkg.deliverable_type = payload.deliverable_type
    pkg.title = payload.title
    pkg.description = payload.description
    pkg.price_amount = payload.price_amount
    pkg.currency = currency
    pkg.quantity = payload.quantity
    pkg.duration_value = payload.duration_value
    pkg.duration_unit = payload.duration_unit
    pkg.is_active = payload.is_active
    db.commit()
    db.refresh(pkg)
    return _package_out(pkg)


def delete_package(db: Session, package_id: str, user_id: str) -> None:
    pkg = db.query(models.Package).filter(models.Package.id == package_id).first()
    if pkg is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="profile_package_not_found",
            detail="Package not found",
        )
    if pkg.user_id != user_id:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="profile_package_not_yours",
            detail="Not your package",
        )
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
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="profile_image_not_found",
            detail="Image not found",
        )
    count = db.query(models.PortfolioItem).filter(models.PortfolioItem.user_id == user_id).count()
    item = models.PortfolioItem(user_id=user_id, media_id=media_id, position=count)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _portfolio_out(item)


def remove_portfolio_item(db: Session, item_id: str, user_id: str) -> None:
    item = db.query(models.PortfolioItem).filter(models.PortfolioItem.id == item_id).first()
    if item is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="profile_portfolio_item_not_found",
            detail="Portfolio item not found",
        )
    if item.user_id != user_id:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="profile_portfolio_not_yours",
            detail="Not your portfolio",
        )
    db.delete(item)
    db.commit()


# ---- Public profile aggregate ----

def get_public_profile(db: Session, user_id: str, language: str | None = None) -> dict:
    profile = db.query(models.InfluencerProfile).filter(models.InfluencerProfile.user_id == user_id).first()
    if profile is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="profile_not_found",
            detail="Profile not found",
        )

    from app.modules.trust_safety import models as trust_safety
    from app.modules.trust_safety.service import user_reviews

    reviews = user_reviews(db, user_id)
    # The page shows the reviews behind the average, not just the number:
    # revealed only (double blind still applies), newest first, capped so the
    # page carries recent proof rather than a full history.
    revealed_reviews = (
        db.query(trust_safety.Review)
        .filter(
            trust_safety.Review.reviewee_user_id == user_id,
            trust_safety.Review.revealed.is_(True),
        )
        .order_by(trust_safety.Review.created_at.desc())
        .limit(PUBLIC_REVIEWS_LIMIT)
        .all()
    )
    # Only an influencer profile carries a public display name today; business
    # reviewers stay unnamed until business profiles gain one. Nothing is ever
    # taken from the users table: its only identifier is a phone number.
    reviewer_names: dict = {}
    reviewer_ids = {r.reviewer_user_id for r in revealed_reviews}
    if reviewer_ids:
        reviewer_names = dict(
            db.query(models.InfluencerProfile.user_id, models.InfluencerProfile.display_name)
            .filter(models.InfluencerProfile.user_id.in_(reviewer_ids))
            .all()
        )
    # Every connected account is shown, not only verified ones. Manual
    # connections stay pending until OAuth verification ships, so during the
    # pilot a verified-only filter emptied the audience section and follower
    # chips for every single creator. Product decision: show them all with
    # their status, and let the frontend badge the verified ones. The filter
    # can come back the day verification is real.
    social = (
        db.query(models.SocialAccount)
        .filter(models.SocialAccount.user_id == user_id)
        .order_by(models.SocialAccount.created_at.asc())
        .all()
    )
    # Of the identity fields, only languages is public. birth_date and gender
    # are deliberately absent from this payload: they exist for the 18+ gate
    # and analytics, and a public endpoint exposing a creator's age or gender
    # would be a privacy leak, not a feature. The owner-facing
    # InfluencerProfileOut is the only place they appear.
    return {
        "user_id": profile.user_id,
        "display_name": profile.display_name,
        "headline": profile.headline,
        "location": profile.location,
        "avatar_url": _media_url(profile.avatar_media_id),
        "bio": resolve_bio(profile, language),
        "bio_fr": profile.bio_fr,
        "bio_en": profile.bio_en,
        "categories": profile.categories,
        "languages": profile.languages or [],
        "follower_count": profile.follower_count,
        "is_searchable": _influencer_completion(profile, _active_package_count(db, user_id))[1],
        # Only the answers the creator wrote: an empty answer is an unanswered
        # question, and the page simply does not show it.
        "faq": {key: answer for key, answer in (profile.faq or {}).items() if answer},
        "average_stars": reviews["average_stars"],
        "review_count": reviews["count"],
        "reviews": [
            {
                "stars": r.stars,
                "comment": r.comment,
                "created_at": r.created_at,
                "reviewer_display_name": reviewer_names.get(r.reviewer_user_id),
            }
            for r in revealed_reviews
        ],
        "packages": list_packages(db, user_id, active_only=True),
        "portfolio": list_portfolio(db, user_id),
        "social_accounts": [
            {
                "id": s.id, "platform": s.platform, "handle": s.handle, "method": s.method,
                "status": s.status, "follower_count": s.follower_count,
            }
            for s in social
        ],
    }

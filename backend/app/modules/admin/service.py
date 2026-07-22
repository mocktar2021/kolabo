"""Admin verification queue and decision logic (KOL-18)."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.admin.models import AdminActionLog, utcnow
from app.modules.profiles import models as profiles

DECISIONS = {"approved", "rejected"}


def list_verification_queue(db: Session, item_type: str | None = None, item_status: str | None = None) -> dict:
    doc_query = db.query(profiles.VerificationDocument)
    social_query = db.query(profiles.SocialAccount)
    if item_status:
        doc_query = doc_query.filter(profiles.VerificationDocument.status == item_status)
        social_query = social_query.filter(profiles.SocialAccount.status == item_status)
    else:
        doc_query = doc_query.filter(profiles.VerificationDocument.status == profiles.PENDING)
        social_query = social_query.filter(profiles.SocialAccount.status == profiles.PENDING)

    documents = []
    social = []
    if item_type in (None, "document"):
        documents = [
            {"id": d.id, "user_id": d.user_id, "doc_type": d.doc_type, "status": d.status, "created_at": d.created_at.isoformat()}
            for d in doc_query.order_by(profiles.VerificationDocument.created_at.asc()).all()
        ]
    if item_type in (None, "social"):
        social = [
            {"id": s.id, "user_id": s.user_id, "platform": s.platform, "handle": s.handle, "status": s.status, "created_at": s.created_at.isoformat()}
            for s in social_query.order_by(profiles.SocialAccount.created_at.asc()).all()
        ]
    return {"documents": documents, "social_accounts": social}


def _log(db: Session, admin_id: str, action: str, target_type: str, target_id: str, reason: str | None) -> None:
    db.add(AdminActionLog(admin_id=admin_id, action=action, target_type=target_type, target_id=target_id, reason=reason))


def decide_document(db: Session, admin_id: str, doc_id: str, decision: str, reason: str | None) -> dict:
    if decision not in DECISIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="decision must be approved or rejected")
    if decision == "rejected" and not reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A rejection requires a reason")
    doc = db.query(profiles.VerificationDocument).filter(profiles.VerificationDocument.id == doc_id).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    doc.status = profiles.APPROVED if decision == "approved" else profiles.REJECTED
    doc.rejection_reason = reason if decision == "rejected" else None
    doc.reviewer_id = admin_id
    doc.reviewed_at = utcnow()
    _log(db, admin_id, f"document_{decision}", "verification_document", doc.id, reason)
    db.commit()
    return {"id": doc.id, "status": doc.status, "reviewer_id": doc.reviewer_id}


def decide_social(db: Session, admin_id: str, social_id: str, decision: str, reason: str | None) -> dict:
    if decision not in DECISIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="decision must be approved or rejected")
    account = db.query(profiles.SocialAccount).filter(profiles.SocialAccount.id == social_id).first()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Social account not found")
    account.status = profiles.VERIFIED if decision == "approved" else profiles.REJECTED
    account.reviewer_id = admin_id
    account.reviewed_at = utcnow()
    _log(db, admin_id, f"social_{decision}", "social_account", account.id, reason)
    db.commit()
    return {"id": account.id, "status": account.status, "reviewer_id": account.reviewer_id}

"""Admin verification queue and decision logic (KOL-18).

A DECISION IS TOLD TO THE PERSON IT IS ABOUT. Approving or rejecting a
document or a connected account used to write an AdminActionLog row and stop
there — accountability for us, silence for them. There is no screen in this
product that polls a verification status, so somebody who uploaded an ID and
is waiting to be allowed to trade had no way to learn the answer except by
opening the app on the off chance; a rejection, which needs them to DO
something, was the case that silence hurt most.
"""
from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.admin.models import AdminActionLog, utcnow
from app.modules.notifications.service import notify
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
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="admin_decision_unknown",
            detail="decision must be approved or rejected",
        )
    if decision == "rejected" and not reason:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="admin_rejection_needs_reason",
            detail="A rejection requires a reason",
        )
    doc = db.query(profiles.VerificationDocument).filter(profiles.VerificationDocument.id == doc_id).first()
    if doc is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="admin_document_not_found",
            detail="Document not found",
        )
    doc.status = profiles.APPROVED if decision == "approved" else profiles.REJECTED
    doc.rejection_reason = reason if decision == "rejected" else None
    doc.reviewer_id = admin_id
    doc.reviewed_at = utcnow()
    _log(db, admin_id, f"document_{decision}", "verification_document", doc.id, reason)
    # THE REASON TRAVELS WITH A REJECTION. It is already required by the guard
    # above, and it is required because a rejection is an instruction: without
    # it the user re-uploads the same unreadable photograph and rejoins the
    # same queue, which costs them days and costs us the review twice.
    #
    # The underscore in the stored doc_type is a database value, not a
    # sentence — "business_registration" in a notification reads like a leak
    # of an internal name.
    doc_name = doc.doc_type.replace("_", " ")
    approved = decision == "approved"
    # NO LINK, and that is the honest answer rather than an oversight: the web
    # app has no verification screen to send anybody to yet (nothing under
    # web/src references the verification-documents endpoints). A link to
    # /account would land the reader somewhere that says nothing about their
    # document, which is worse than a row that simply marks itself read. When
    # the screen exists, this is the line that gets a link.
    notify(
        db,
        doc.user_id,
        "verification",
        (
            f"Your {doc_name} document was approved."
            if approved
            else f"Your {doc_name} document was rejected: {reason}"
        ),
        params=(
            {"key": "verification_document_approved", "document": doc_name}
            if approved
            # reason is never None here: the guard at the top of this function
            # refuses a rejection without one.
            else {
                "key": "verification_document_rejected",
                "document": doc_name,
                "reason": reason,
            }
        ),
    )
    db.commit()
    return {"id": doc.id, "status": doc.status, "reviewer_id": doc.reviewer_id}


def decide_social(db: Session, admin_id: str, social_id: str, decision: str, reason: str | None) -> dict:
    if decision not in DECISIONS:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="admin_decision_unknown",
            detail="decision must be approved or rejected",
        )
    account = db.query(profiles.SocialAccount).filter(profiles.SocialAccount.id == social_id).first()
    if account is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="profile_social_not_found",
            detail="Social account not found",
        )
    account.status = profiles.VERIFIED if decision == "approved" else profiles.REJECTED
    account.reviewer_id = admin_id
    account.reviewed_at = utcnow()
    _log(db, admin_id, f"social_{decision}", "social_account", account.id, reason)
    # The platform and the handle are both named because a creator can have
    # several accounts in this queue at once, and "your account was verified"
    # would not say which one — a verified badge is what a brand filters on,
    # so which account carries it is the whole content of the message.
    #
    # Unlike a document rejection, a reason is optional here, so it is
    # appended only when there is one rather than printing "None".
    subject = f"Your {account.platform} account @{account.handle}"
    shared = {"platform": account.platform, "handle": account.handle}
    if decision == "approved":
        message = f"{subject} was verified."
        params = {"key": "social_verified", **shared}
    else:
        message = f"{subject} was rejected" + (f": {reason}" if reason else ".")
        # Two keys rather than one with an empty {{reason}}: an optional value
        # interpolated when absent leaves "rejected : " with a dangling colon,
        # which reads as a bug in the message rather than as an absent reason.
        params = (
            {"key": "social_rejected_reason", "reason": reason, **shared}
            if reason
            else {"key": "social_rejected", **shared}
        )
    # Unlike a verification document, this one HAS a screen: social accounts
    # are managed on ProfileSetup (/profile), where the verified badge the
    # decision just changed is on show.
    notify(db, account.user_id, "verification", message, link="/profile", params=params)
    db.commit()
    return {"id": account.id, "status": account.status, "reviewer_id": account.reviewer_id}


def dashboard_summary(db: Session) -> dict:
    """Single operational view: queue counts plus recent decisions (KOL-33).

    Drill-down uses the existing queue endpoints (verification queue, reports
    queue, escrow lookups). This returns the counts an admin needs to triage the
    day and the tail of the action log for accountability.
    """
    from app.modules.payments import models as payments
    from app.modules.trust_safety import models as trust_safety

    now = utcnow()

    pending_documents = (
        db.query(profiles.VerificationDocument)
        .filter(profiles.VerificationDocument.status == profiles.PENDING)
        .count()
    )
    pending_social = (
        db.query(profiles.SocialAccount)
        .filter(profiles.SocialAccount.status == profiles.PENDING)
        .count()
    )
    open_disputes = (
        db.query(payments.Escrow).filter(payments.Escrow.status == payments.DISPUTED).count()
    )
    held = db.query(payments.Escrow).filter(payments.Escrow.status == payments.HELD).count()
    due_for_release = (
        db.query(payments.Escrow)
        .filter(payments.Escrow.status == payments.HELD, payments.Escrow.due_release_at <= now)
        .count()
    )
    open_reports = (
        db.query(trust_safety.Report).filter(trust_safety.Report.status == trust_safety.OPEN).count()
    )

    recent = (
        db.query(AdminActionLog)
        .order_by(AdminActionLog.created_at.desc())
        .limit(20)
        .all()
    )
    recent_actions = [
        {
            "admin_id": a.admin_id,
            "action": a.action,
            "target_type": a.target_type,
            "target_id": a.target_id,
            "created_at": a.created_at.isoformat(),
        }
        for a in recent
    ]

    return {
        "verification": {"pending_documents": pending_documents, "pending_social_accounts": pending_social},
        "disputes": {"open": open_disputes},
        "payouts": {"held": held, "due_for_release": due_for_release},
        "reports": {"open": open_reports},
        "recent_actions": recent_actions,
    }

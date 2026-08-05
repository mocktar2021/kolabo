"""Trust and safety business logic (Epic H).

KOL-31: a user can rate and review a collaboration partner, but only after the
collaboration is completed and paid, which on this platform means its escrow has
been released. Reviews are double blind: each side's review stays hidden until
both parties have submitted, so neither can be swayed by the other's rating.
KOL-32: a user can report suspicious behavior. A report becomes an open case in
the admin queue tagged with a reason code, for an admin to investigate.
"""
from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.admin.models import AdminActionLog
from app.modules.notifications.service import notify
from app.modules.payments import models as payments
from app.modules.trust_safety import models

REASON_CODES = {
    "fake_followers",
    "fake_engagement",
    "fraud",
    "harassment",
    "spam",
    "inappropriate_content",
    "impersonation",
    "other",
}

TARGET_TYPES = {"user", "campaign", "message"}

DECISIONS = {models.REVIEWED, models.DISMISSED}


def _review_out(review: models.Review) -> dict:
    return {
        "id": review.id,
        "reviewer_user_id": review.reviewer_user_id,
        "reviewee_user_id": review.reviewee_user_id,
        "stars": review.stars,
        "comment": review.comment,
        "revealed": review.revealed,
    }


def submit_review(db: Session, reviewer_id: str, escrow_id: str, stars: int, comment: str | None) -> dict:
    escrow = db.query(payments.Escrow).filter(payments.Escrow.id == escrow_id).first()
    if escrow is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="review_collaboration_not_found",
            detail="Collaboration not found",
        )
    if reviewer_id not in (escrow.business_user_id, escrow.influencer_user_id):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="review_not_a_party",
            detail="You are not a party to this collaboration",
        )
    if escrow.status != payments.RELEASED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="review_not_completed",
            detail="You can review only after the collaboration is completed and paid",
        )

    existing = (
        db.query(models.Review)
        .filter(models.Review.escrow_id == escrow_id, models.Review.reviewer_user_id == reviewer_id)
        .first()
    )
    if existing is not None:
        raise AppError(
            status.HTTP_409_CONFLICT,
            code="review_already_submitted",
            detail="You have already reviewed this collaboration",
        )

    reviewee_id = (
        escrow.influencer_user_id if reviewer_id == escrow.business_user_id else escrow.business_user_id
    )
    review = models.Review(
        escrow_id=escrow_id,
        campaign_id=escrow.campaign_id,
        reviewer_user_id=reviewer_id,
        reviewee_user_id=reviewee_id,
        stars=stars,
        comment=comment,
        revealed=False,
    )
    db.add(review)
    db.flush()

    # Double blind reveal: once both parties have submitted, reveal both.
    all_reviews = db.query(models.Review).filter(models.Review.escrow_id == escrow_id).all()
    if len(all_reviews) >= 2:
        for r in all_reviews:
            r.revealed = True

    db.commit()
    db.refresh(review)
    return _review_out(review)


def user_reviews(db: Session, user_id: str) -> dict:
    reviews = (
        db.query(models.Review)
        .filter(models.Review.reviewee_user_id == user_id, models.Review.revealed.is_(True))
        .all()
    )
    count = len(reviews)
    average = round(sum(r.stars for r in reviews) / count, 2) if count else None
    return {
        "user_id": user_id,
        "average_stars": average,
        "count": count,
        "reviews": [
            {"reviewer_user_id": r.reviewer_user_id, "stars": r.stars, "comment": r.comment}
            for r in reviews
        ],
    }


def create_report(
    db: Session, reporter_id: str, target_type: str, target_id: str, reason_code: str, details: str | None
) -> dict:
    if target_type not in TARGET_TYPES:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="report_target_type_unknown",
            detail="Unknown target type",
        )
    if reason_code not in REASON_CODES:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="report_reason_unknown",
            detail="Unknown reason code",
        )

    report = models.Report(
        reporter_user_id=reporter_id,
        target_type=target_type,
        target_id=target_id,
        reason_code=reason_code,
        details=details,
        status=models.OPEN,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {
        "id": report.id,
        "target_type": report.target_type,
        "target_id": report.target_id,
        "reason_code": report.reason_code,
        "status": report.status,
    }


def list_reports(db: Session, report_status: str | None) -> list[dict]:
    query = db.query(models.Report)
    if report_status:
        query = query.filter(models.Report.status == report_status)
    reports = query.order_by(models.Report.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "reporter_user_id": r.reporter_user_id,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "reason_code": r.reason_code,
            "details": r.details,
            "status": r.status,
        }
        for r in reports
    ]


def resolve_report(db: Session, admin_id: str, report_id: str, decision: str) -> dict:
    """An admin closes a case, and the person who raised it is told.

    THE REPORTER HEARS THAT IT CLOSED AND NEVER WHAT WAS DECIDED, and the two
    halves of that are both deliberate. They hear something because a report
    that vanishes into an admin queue is a report nobody files a second time,
    and reporting is the only signal we have about behaviour that never
    touches a contract. They do not hear the outcome because the outcome is a
    fact about SOMEBODY ELSE'S ACCOUNT: "we acted on your report" tells the
    reporter that a named person was sanctioned, which is not theirs to know
    and is exactly what turns a reporting tool into a harassment tool.

    So reviewed and dismissed produce the same sentence. That is the point.
    """
    if decision not in DECISIONS:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="report_decision_unknown",
            detail="Decision must be reviewed or dismissed",
        )
    report = db.query(models.Report).filter(models.Report.id == report_id).first()
    if report is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="report_not_found",
            detail="Report not found",
        )
    if report.status != models.OPEN:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="report_already_resolved",
            detail="Report is already resolved",
        )

    report.status = decision
    report.reviewer_id = admin_id
    report.reviewed_at = models.utcnow()
    db.add(
        AdminActionLog(
            admin_id=admin_id,
            action=f"report_{decision}",
            target_type="report",
            target_id=report_id,
            reason=report.reason_code,
        )
    )
    notify(
        db,
        report.reporter_user_id,
        "report",
        f"Your report about a {report.target_type} has been reviewed and the case is closed.",
        # NO LINK: there is no screen where somebody reads their own reports.
        # A row that marks itself read is the honest shape until there is.
        #
        # THE LOCALISED BODY DROPS THE TARGET TYPE, deliberately. target_type
        # is a database enum ("user", "campaign"), and interpolating it into
        # French prose would put an English word mid-sentence. The reporter
        # knows what they reported; the stored `message` keeps it for the
        # email. What must NOT appear either way is the DECISION — see this
        # function's docstring.
        params={"key": "report_reviewed"},
    )
    db.commit()
    return {
        "id": report.id,
        "target_type": report.target_type,
        "target_id": report.target_id,
        "reason_code": report.reason_code,
        "status": report.status,
    }

"""Deliverable submission and review.

The creator hands in the work; the brand approves it (which releases the
escrow) or asks for changes (which does not move the money). See service.py for
why those are two different acts and neither of them is a dispute.

THE COLLECTION PATHS ARE DECLARED AS "" AND NOT "/". Mounted under the
/deliverables prefix that resolves to exactly "/deliverables", so a client
calling the obvious URL gets an answer instead of the 307 redirect the
notifications list earns for being declared as "/" (see the trailing-slash
comment in web/src/lib/notifications.ts). New surface, so it costs nothing to
get right here.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import get_current_user_id
from app.modules.deliverables import schemas, service

router = APIRouter()


@router.post("", response_model=schemas.SubmissionOut, status_code=status.HTTP_201_CREATED)
def submit_work(
    payload: schemas.SubmissionIn,
    db: Session = Depends(get_db),
    actor_user_id: str = Depends(get_current_user_id),
):
    """Creator submits completed work against a signed, funded contract.

    Needs the link to the published post, one or more uploaded files, or both.
    Starts the brand's review window, after which the escrow auto-releases —
    so an unreviewed submission still pays the creator, and an escrow with
    nothing submitted against it does not.
    """
    return service.submit(db, actor_user_id, payload)


@router.get("", response_model=list[schemas.SubmissionOut])
def list_submissions(
    contract_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Every attempt on one contract, newest first. Either party."""
    return service.list_for_contract(db, user_id, contract_id)


@router.post("/{submission_id}/approve", response_model=schemas.SubmissionOut)
def approve_submission(
    submission_id: str,
    db: Session = Depends(get_db),
    actor_user_id: str = Depends(get_current_user_id),
):
    """Business accepts the work, which releases the escrow in the same
    transaction, commission deducted. Both parties are notified by the release
    path itself."""
    return service.approve(db, actor_user_id, submission_id)


@router.post("/{submission_id}/request-changes", response_model=schemas.SubmissionOut)
def request_changes(
    submission_id: str,
    payload: schemas.ReviewIn,
    db: Session = Depends(get_db),
    actor_user_id: str = Depends(get_current_user_id),
):
    """Business asks for the work to be redone. A note saying what to change is
    required; the escrow stays held and the creator can submit again."""
    return service.request_changes(db, actor_user_id, submission_id, payload)


@router.post("/{submission_id}/withdraw", response_model=schemas.SubmissionOut)
def withdraw_submission(
    submission_id: str,
    db: Session = Depends(get_db),
    actor_user_id: str = Depends(get_current_user_id),
):
    """Creator pulls back a submission the brand has not answered yet."""
    return service.withdraw(db, actor_user_id, submission_id)

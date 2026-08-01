"""Epic G (KOL-7): Payments and Escrow."""
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.admin.router import get_current_admin
from app.modules.auth.deps import get_current_user_id
from app.modules.payments import disputes, resolution, schemas, service

router = APIRouter()


def get_case_viewer(
    authorization: str | None = Header(default=None),
    x_admin_id: str | None = Header(default=None),
) -> tuple[str, bool]:
    """Who is reading this case: one of the two parties, or an admin.

    Admin identity is still the X-Admin-Id placeholder (see admin/router.py)
    and a party is still a bearer token, so an endpoint that serves both has
    to accept either credential. No admin holds a user token, and requiring
    one would mean the person handed the queue cannot open anything in it.
    """
    if x_admin_id:
        return x_admin_id, True
    return get_current_user_id(authorization), False


@router.post("/escrow/fund", response_model=schemas.EscrowOut, status_code=status.HTTP_201_CREATED)
def fund_escrow(
    payload: schemas.FundIn,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Fund an escrow via Mobile Money for a fully signed contract. KOL-28."""
    return service.fund_escrow(db, business_user_id, payload.contract_id)


@router.post("/escrow/{escrow_id}/release", response_model=schemas.EscrowOut)
def release_escrow(
    escrow_id: str,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Business confirms delivery and releases the escrow, commission deducted. KOL-36."""
    return service.release_escrow(db, business_user_id, escrow_id)


@router.post(
    "/escrow/{escrow_id}/dispute",
    response_model=schemas.DisputeOut,
    status_code=status.HTTP_201_CREATED,
)
def dispute_escrow(
    escrow_id: str,
    payload: schemas.DisputeIn,
    db: Session = Depends(get_db),
    actor_user_id: str = Depends(get_current_user_id),
):
    """Open a dispute, which freezes the escrow and starts the response window.

    Requires a reason from the closed set, a written statement, and optionally
    the ids of images you uploaded as evidence. The other party is notified
    and gets the first word; only if they do not use it does an admin see the
    case. KOL-37.
    """
    return disputes.raise_dispute(db, actor_user_id, escrow_id, payload)


@router.post("/disputes/escalate")
def escalate_disputes(
    db: Session = Depends(get_db), admin_id: str = Depends(get_current_admin)
):
    """Send disputes whose response window has closed to the admin queue.

    Admin-triggered and on demand, mirroring /payments/escrow/auto-release and
    /campaigns/orders/expire. That makes three jobs with no scheduler behind
    them, and this is the one that keeps frozen money from staying frozen.
    """
    return {"escalated": disputes.escalate_stale_disputes(db)}


# Declared before /disputes/{dispute_id}: FastAPI matches in declaration
# order, so the literal path has to come first or "mine" is read as an id.
@router.get("/disputes/mine")
def my_disputes(
    db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)
):
    """Every dispute the caller is a party to, newest first."""
    return disputes.list_my_disputes(db, user_id)


@router.post("/disputes/{dispute_id}/messages", status_code=status.HTTP_201_CREATED)
def post_dispute_message(
    dispute_id: str,
    payload: schemas.DisputeMessageIn,
    db: Session = Depends(get_db),
    actor_user_id: str = Depends(get_current_user_id),
):
    """Either party answers, with optional evidence.

    Open during the response window and after the case has queued: an admin
    reading it benefits from both sides continuing to explain.
    """
    return disputes.post_message(db, actor_user_id, dispute_id, payload)


@router.post("/disputes/{dispute_id}/withdraw", response_model=schemas.DisputeOut)
def withdraw_dispute(
    dispute_id: str,
    db: Session = Depends(get_db),
    actor_user_id: str = Depends(get_current_user_id),
):
    """The party who raised it drops it; the escrow goes back to held."""
    return disputes.withdraw_dispute(db, actor_user_id, dispute_id)


@router.get("/disputes/{dispute_id}")
def get_dispute(
    dispute_id: str,
    db: Session = Depends(get_db),
    viewer: tuple[str, bool] = Depends(get_case_viewer),
):
    """The whole case: claim, thread with evidence urls, and the escrow."""
    viewer_id, is_admin = viewer
    return disputes.get_dispute(db, viewer_id, is_admin, dispute_id)


@router.get("/escrow/by-contract/{contract_id}", response_model=schemas.EscrowOut)
def escrow_by_contract(
    contract_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Find the escrow for a contract, if it has been funded."""
    return service.get_escrow_by_contract(db, user_id, contract_id)


@router.get("/escrow/{escrow_id}", response_model=schemas.EscrowOut)
def get_escrow(
    escrow_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return service.get_escrow(db, user_id, escrow_id)


@router.post("/escrow/{escrow_id}/resolve", response_model=schemas.DisputeOut)
def resolve_dispute(
    escrow_id: str,
    payload: schemas.ResolveIn,
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """Admin settles a disputed escrow by splitting it, logged. KOL-37.

    released_amount and refunded_amount must add up to the escrow exactly.
    Either may be zero. Commission is charged on the released part only.
    Returns the closed dispute with the settled escrow on it.
    """
    return resolution.resolve_dispute(db, admin_id, escrow_id, payload)


@router.post("/escrow/auto-release")
def run_auto_release(db: Session = Depends(get_db), admin_id: str = Depends(get_current_admin)):
    """Release escrows past their auto release deadline. Runs the timeout path for KOL-36."""
    count = service.run_due_auto_releases(db)
    return {"released": count}

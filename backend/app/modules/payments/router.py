"""Epic G (KOL-7): Payments and Escrow."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.admin.router import get_current_admin
from app.modules.auth.deps import get_current_user_id
from app.modules.payments import disputes, schemas, service

router = APIRouter()


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


@router.post("/escrow/{escrow_id}/resolve", response_model=schemas.EscrowOut)
def resolve_dispute(
    escrow_id: str,
    payload: schemas.ResolveIn,
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """Admin resolves a dispute by releasing or refunding, logged. KOL-37."""
    return service.resolve_dispute(db, admin_id, escrow_id, payload.decision)


@router.post("/escrow/auto-release")
def run_auto_release(db: Session = Depends(get_db), admin_id: str = Depends(get_current_admin)):
    """Release escrows past their auto release deadline. Runs the timeout path for KOL-36."""
    count = service.run_due_auto_releases(db)
    return {"released": count}

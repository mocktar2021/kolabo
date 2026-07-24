"""Epic E (KOL-5): Contracts."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import get_current_user_id
from app.modules.contracts import schemas, service

router = APIRouter()


@router.post("/from-proposal/{proposal_id}", response_model=schemas.ContractOut, status_code=status.HTTP_201_CREATED)
def generate_from_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Accept a proposal and auto-generate a contract from its terms. KOL-24."""
    return service.generate_from_proposal(db, business_user_id, proposal_id)


@router.get("/by-proposal/{proposal_id}", response_model=schemas.ContractOut)
def contract_by_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Find the contract generated from a proposal, if any."""
    return service.get_contract_by_proposal(db, proposal_id, user_id)


@router.get("/{contract_id}", response_model=schemas.ContractDetailOut)
def get_contract(
    contract_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Read a contract you are a party to, including the generated body."""
    return service.get_contract(db, contract_id, user_id)


@router.post("/{contract_id}/sign", response_model=schemas.ContractOut)
def sign_contract(
    contract_id: str,
    payload: schemas.SignIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """E-sign the contract. Both signatures are required and it is then immutable. KOL-25."""
    return service.sign_contract(db, contract_id, user_id, payload.signature)

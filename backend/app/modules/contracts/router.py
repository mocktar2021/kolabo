"""Epic E (KOL-5): Contracts."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import get_current_user_id
from app.modules.contracts import cancellation, schemas, service

router = APIRouter()


@router.post("/from-proposal/{proposal_id}", response_model=schemas.ContractOut, status_code=status.HTTP_201_CREATED)
def generate_from_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Accept a proposal and auto-generate a contract from its terms. KOL-24."""
    return service.generate_from_proposal(db, business_user_id, proposal_id)


@router.get("/mine", response_model=list[schemas.ContractListItem])
def my_contracts(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """List contracts the current user is a party to (business or influencer).

    Each row carries the campaign title and the other party's name so the card
    reads without opening it; see service.list_my_contracts.
    """
    return service.list_my_contracts(db, user_id)


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


@router.post("/{contract_id}/cancel", response_model=schemas.ContractOut)
def cancel_contract(
    contract_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Either party calls off a contract before it binds anybody.

    Allowed only while the contract is NOT fully signed (400 otherwise — both
    parties agreed to it and it is immutable) and while NO escrow exists
    against it (409 otherwise — funded money is the dispute and refund path's
    business, not a button).

    The other party is notified and a contract_events row records who ended it.
    """
    return cancellation.cancel_contract(db, contract_id, user_id)

"""Epic E (KOL-5): Contracts."""
from fastapi import APIRouter

router = APIRouter()


@router.post("/generate/{proposal_id}")
def generate_contract(proposal_id: str):
    """See KOL-24. Requires legal-reviewed template per country."""
    raise NotImplementedError


@router.post("/{contract_id}/sign")
def sign_contract(contract_id: str):
    """See KOL-25. Both signatures required before payment unlocks."""
    raise NotImplementedError

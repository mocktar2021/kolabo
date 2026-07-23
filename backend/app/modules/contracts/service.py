"""Contracts business logic (Epic E).

KOL-24: generate a contract from an accepted proposal, populating all agreed
terms without manual re-entry. Legal reviewed templates per country are not
available yet, so the body is built from a clearly labeled placeholder template
per language, and the PR flags that legal review is required before production.
KOL-25: e-sign the contract. Signatures are timestamped and attributable, both
signatures are required before the contract is fully signed (which is what
Epic G will check before unlocking payment), and once signed the contract is
immutable. A ContractEvent audit row is written for every lifecycle event.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.campaigns import models as campaigns
from app.modules.contracts import models
from app.modules.notifications.service import notify

# Language per country. Kept local to avoid coupling to optional country_config
# fields; Cameroon defaults to French for the contract body for now.
FRENCH_COUNTRIES = {"BJ", "TG", "CI", "SN", "CM"}


def _language_for(country_code: str) -> str:
    return "fr" if country_code in FRENCH_COUNTRIES else "en"


def _build_body(language: str, campaign: campaigns.Campaign, proposal: campaigns.Proposal, business: User, influencer: User) -> str:
    banner_en = "PLACEHOLDER TEMPLATE. NOT LEGALLY REVIEWED. Do not use in production until reviewed by qualified counsel per country."
    banner_fr = "MODELE PROVISOIRE. NON REVISE JURIDIQUEMENT. Ne pas utiliser en production avant revision par un conseil juridique qualifie par pays."
    deliverables = ", ".join(f"{d.get('quantity')} x {d.get('type')} on {d.get('platform')}" for d in (campaign.deliverables or []))
    banner = banner_fr if language == "fr" else banner_en
    lines = [
        banner,
        "",
        f"Contract for campaign: {campaign.title}",
        f"Business party (user id): {business.id}",
        f"Influencer party (user id): {influencer.id}",
        f"Deliverables: {deliverables}",
        f"Agreed rate: {proposal.rate_amount} {proposal.rate_currency} (minor units)",
        f"Timeline: {proposal.timeline_days} days",
        f"Campaign deadline: {campaign.deadline}",
        "",
        "Both parties must sign electronically. Payment is unlocked only after both signatures are recorded.",
    ]
    return "\n".join(lines)


def _out(contract: models.Contract) -> dict:
    business_signed = contract.business_signed_at is not None
    influencer_signed = contract.influencer_signed_at is not None
    return {
        "id": contract.id,
        "campaign_id": contract.campaign_id,
        "proposal_id": contract.proposal_id,
        "business_user_id": contract.business_user_id,
        "influencer_user_id": contract.influencer_user_id,
        "language": contract.language,
        "status": contract.status,
        "rate_amount": contract.rate_amount,
        "rate_currency": contract.rate_currency,
        "timeline_days": contract.timeline_days,
        "business_signed": business_signed,
        "influencer_signed": influencer_signed,
        "fully_signed": contract.status == models.SIGNED,
    }


def generate_from_proposal(db: Session, business_user_id: str, proposal_id: str) -> dict:
    proposal = db.query(campaigns.Proposal).filter(campaigns.Proposal.id == proposal_id).first()
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    campaign = db.query(campaigns.Campaign).filter(campaigns.Campaign.id == proposal.campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.business_user_id != business_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your campaign")
    existing = db.query(models.Contract).filter(models.Contract.proposal_id == proposal_id).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A contract already exists for this proposal")
    if proposal.status != campaigns.SUBMITTED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only a submitted proposal can be accepted")

    business = db.query(User).filter(User.id == business_user_id).first()
    influencer = db.query(User).filter(User.id == proposal.influencer_user_id).first()
    language = _language_for(business.country_code)

    # Accepting the proposal is what triggers contract generation.
    proposal.status = campaigns.PROPOSAL_ACCEPTED

    contract = models.Contract(
        campaign_id=campaign.id,
        proposal_id=proposal.id,
        business_user_id=business.id,
        influencer_user_id=influencer.id,
        language=language,
        body=_build_body(language, campaign, proposal, business, influencer),
        rate_amount=proposal.rate_amount,
        rate_currency=proposal.rate_currency,
        timeline_days=proposal.timeline_days,
        deliverables=campaign.deliverables,
        status=models.PENDING,
    )
    db.add(contract)
    db.flush()
    db.add(models.ContractEvent(contract_id=contract.id, actor_user_id=business_user_id, event="generated"))
    notify(db, influencer.id, "contract_ready", f"A contract is ready to sign for {campaign.title}")
    db.commit()
    db.refresh(contract)
    return _out(contract)


def get_contract(db: Session, contract_id: str, user_id: str) -> dict:
    contract = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if contract is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
    if user_id not in (contract.business_user_id, contract.influencer_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this contract")
    out = _out(contract)
    out["body"] = contract.body
    return out


def sign_contract(db: Session, contract_id: str, user_id: str, signature: str) -> dict:
    contract = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if contract is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
    if user_id not in (contract.business_user_id, contract.influencer_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this contract")
    if contract.status == models.SIGNED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contract is fully signed and immutable")

    now = models.utcnow()
    if user_id == contract.business_user_id:
        if contract.business_signed_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already signed")
        contract.business_signature = signature
        contract.business_signed_at = now
        db.add(models.ContractEvent(contract_id=contract.id, actor_user_id=user_id, event="signed_business"))
    else:
        if contract.influencer_signed_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already signed")
        contract.influencer_signature = signature
        contract.influencer_signed_at = now
        db.add(models.ContractEvent(contract_id=contract.id, actor_user_id=user_id, event="signed_influencer"))

    if contract.business_signed_at is not None and contract.influencer_signed_at is not None:
        contract.status = models.SIGNED
        db.add(models.ContractEvent(contract_id=contract.id, actor_user_id=user_id, event="fully_signed"))
        notify(db, contract.business_user_id, "contract_signed", "Your contract is fully signed")
        notify(db, contract.influencer_user_id, "contract_signed", "Your contract is fully signed")

    db.commit()
    db.refresh(contract)
    return _out(contract)

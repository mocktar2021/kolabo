"""Payments and escrow business logic (Epic G). Highest-risk module.

KOL-28: fund an escrow via Mobile Money. Funding requires a fully signed
contract (the Epic E gate), moves money into a held state through the provider
abstraction, and never handles raw PINs.
KOL-36: release the escrow to the influencer once the business confirms
delivery, deducting commission at release, or auto release after a timeout if
the business does not respond.
KOL-37: a dispute freezes the escrow; an admin resolves it (release or refund),
the decision is logged, and both parties are notified.

No real money moves: all provider calls go through the mock provider until a real
Mobile Money provider is contracted.
"""
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.admin.models import AdminActionLog
from app.modules.auth.models import User
from app.modules.contracts import models as contracts
from app.modules.notifications.service import notify
from app.modules.payments import models, provider

payment_provider: provider.MobileMoneyProvider = provider.default_provider


def _out(escrow: models.Escrow) -> dict:
    return {
        "id": escrow.id,
        "contract_id": escrow.contract_id,
        "campaign_id": escrow.campaign_id,
        "business_user_id": escrow.business_user_id,
        "influencer_user_id": escrow.influencer_user_id,
        "amount": escrow.amount,
        "currency": escrow.currency,
        "commission_amount": escrow.commission_amount,
        "status": escrow.status,
    }


def _event(db: Session, escrow: models.Escrow, actor_id: str, event: str) -> None:
    db.add(models.EscrowEvent(escrow_id=escrow.id, actor_id=actor_id, event=event))


def fund_escrow(db: Session, business_user_id: str, contract_id: str) -> dict:
    contract = db.query(contracts.Contract).filter(contracts.Contract.id == contract_id).first()
    if contract is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
    if contract.business_user_id != business_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your contract")
    if contract.status != contracts.SIGNED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contract must be fully signed before funding")
    if db.query(models.Escrow).filter(models.Escrow.contract_id == contract_id).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This contract is already funded")

    business = db.query(User).filter(User.id == business_user_id).first()
    fund_ref = payment_provider.collect(business.phone, contract.rate_amount, contract.rate_currency)

    now = models.utcnow()
    escrow = models.Escrow(
        contract_id=contract.id,
        campaign_id=contract.campaign_id,
        business_user_id=contract.business_user_id,
        influencer_user_id=contract.influencer_user_id,
        amount=contract.rate_amount,
        currency=contract.rate_currency,
        provider="mock",
        provider_fund_ref=fund_ref,
        status=models.HELD,
        held_at=now,
        due_release_at=now + timedelta(days=settings.auto_release_days),
    )
    db.add(escrow)
    db.flush()
    _event(db, escrow, business_user_id, "funded")
    notify(db, escrow.influencer_user_id, "payment", "Funds are held in escrow for your collaboration")
    notify(db, escrow.business_user_id, "payment", "Your payment is held in escrow")
    db.commit()
    db.refresh(escrow)
    return _out(escrow)


def _release(db: Session, escrow: models.Escrow, actor_id: str) -> None:
    influencer = db.query(User).filter(User.id == escrow.influencer_user_id).first()
    commission = escrow.amount * settings.commission_bps // 10000
    payout_amount = escrow.amount - commission
    payout_ref = payment_provider.payout(influencer.phone, payout_amount, escrow.currency)
    escrow.commission_amount = commission
    escrow.provider_payout_ref = payout_ref
    escrow.status = models.RELEASED
    escrow.resolved_at = models.utcnow()
    _event(db, escrow, actor_id, "released")
    notify(db, escrow.influencer_user_id, "payment", "Escrow released, your payout is on the way")
    notify(db, escrow.business_user_id, "payment", "Escrow released to the influencer")


def release_escrow(db: Session, business_user_id: str, escrow_id: str) -> dict:
    escrow = db.query(models.Escrow).filter(models.Escrow.id == escrow_id).first()
    if escrow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escrow not found")
    if escrow.business_user_id != business_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the business can confirm delivery")
    if escrow.status != models.HELD:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Escrow is not in a held state")
    _release(db, escrow, business_user_id)
    db.commit()
    db.refresh(escrow)
    return _out(escrow)


def run_due_auto_releases(db: Session, now=None) -> int:
    now = now or models.utcnow()
    due = (
        db.query(models.Escrow)
        .filter(models.Escrow.status == models.HELD, models.Escrow.due_release_at <= now)
        .all()
    )
    for escrow in due:
        _release(db, escrow, "system_auto_release")
    db.commit()
    return len(due)


def dispute_escrow(db: Session, actor_user_id: str, escrow_id: str) -> dict:
    escrow = db.query(models.Escrow).filter(models.Escrow.id == escrow_id).first()
    if escrow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escrow not found")
    if actor_user_id not in (escrow.business_user_id, escrow.influencer_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this escrow")
    if escrow.status != models.HELD:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only a held escrow can be disputed")
    escrow.status = models.DISPUTED
    _event(db, escrow, actor_user_id, "disputed")
    notify(db, escrow.business_user_id, "dispute", "A dispute was opened on your escrow")
    notify(db, escrow.influencer_user_id, "dispute", "A dispute was opened on your escrow")
    db.commit()
    db.refresh(escrow)
    return _out(escrow)


def resolve_dispute(db: Session, admin_id: str, escrow_id: str, decision: str) -> dict:
    if decision not in ("release", "refund"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="decision must be release or refund")
    escrow = db.query(models.Escrow).filter(models.Escrow.id == escrow_id).first()
    if escrow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escrow not found")
    if escrow.status != models.DISPUTED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Escrow is not under dispute")

    if decision == "release":
        _release(db, escrow, admin_id)
    else:
        business = db.query(User).filter(User.id == escrow.business_user_id).first()
        refund_ref = payment_provider.payout(business.phone, escrow.amount, escrow.currency)
        escrow.provider_payout_ref = refund_ref
        escrow.status = models.REFUNDED
        escrow.resolved_at = models.utcnow()
        _event(db, escrow, admin_id, "refunded")
        notify(db, escrow.business_user_id, "payment", "Your escrow was refunded")
        notify(db, escrow.influencer_user_id, "payment", "The disputed escrow was refunded to the business")

    db.add(AdminActionLog(admin_id=admin_id, action=f"dispute_{decision}", target_type="escrow", target_id=escrow.id, reason=None))
    db.commit()
    db.refresh(escrow)
    return _out(escrow)


def get_escrow(db: Session, user_id: str, escrow_id: str) -> dict:
    escrow = db.query(models.Escrow).filter(models.Escrow.id == escrow_id).first()
    if escrow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escrow not found")
    if user_id not in (escrow.business_user_id, escrow.influencer_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this escrow")
    return _out(escrow)


def get_escrow_by_contract(db: Session, user_id: str, contract_id: str) -> dict:
    escrow = db.query(models.Escrow).filter(models.Escrow.contract_id == contract_id).first()
    if escrow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No escrow for this contract")
    if user_id not in (escrow.business_user_id, escrow.influencer_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this escrow")
    return _out(escrow)

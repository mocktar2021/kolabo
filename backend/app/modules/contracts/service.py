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
from fastapi import status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.identity import creator_identities
from app.modules.auth.models import User
from app.modules.campaigns import models as campaigns
from app.modules.campaigns import service as campaigns_service
from app.modules.contracts import models
from app.modules.notifications.service import notify
# MODELS ONLY. payments.service imports contracts.models, so reaching for its
# service here would close the circle; its models import nothing but Base.
# contracts/cancellation.py reads the escrow the same way for the same reason.
from app.modules.payments import models as payments
from app.modules.profiles.models import BusinessProfile

# Language per country. Kept local to avoid coupling to optional country_config
# fields; Cameroon defaults to French for the contract body for now.
FRENCH_COUNTRIES = {"BJ", "TG", "CI", "SN", "CM"}

# What signing a cancelled contract is refused with. Its own sentence rather
# than the fully-signed one, because the two refusals point somewhere
# different: a signed contract is finished and unchangeable, a cancelled one
# is over, and the way forward is a new agreement rather than a retry. Named
# for the same reason cancellation.SIGNED_DETAIL is — the sentence is long
# enough that it reads better out of the raise.
CANCELLED_SIGN_DETAIL = (
    "This contract was cancelled and can no longer be signed. Agree new terms "
    "and generate a new contract."
)


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


def generate_from_proposal(
    db: Session,
    business_user_id: str,
    proposal_id: str,
    *,
    allow_business_offer: bool = False,
) -> dict:
    """Accept the live offer in a negotiation and write the contract from it.

    `allow_business_offer` is for ONE caller: campaigns/orders.accept_direct_order,
    where the creator is the one accepting and the offer on the table is
    legitimately the buyer's. Everywhere else the rule below holds. It is a
    parameter rather than something inferred from the actor because the actor
    is the business on both paths — accept_direct_order passes the buyer's id
    deliberately, so identity cannot tell the two apart.
    """
    proposal = db.query(campaigns.Proposal).filter(campaigns.Proposal.id == proposal_id).first()
    if proposal is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="contract_proposal_not_found",
            detail="Proposal not found",
        )
    campaign = db.query(campaigns.Campaign).filter(campaigns.Campaign.id == proposal.campaign_id).first()
    if campaign is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="contract_campaign_not_found",
            detail="Campaign not found",
        )
    if campaign.business_user_id != business_user_id:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            # campaigns' code, not a contract one: the rule is that this
            # campaign is not yours, and it is enforced identically in
            # campaigns/service.py. Two codes for one rule is two sentences to
            # keep in step in two languages.
            code="campaign_not_yours",
            detail="Not your campaign",
        )

    # A dead campaign has no deal left in it to write down. campaigns/editing.py
    # cancel_campaign only refuses when a contract ALREADY exists, and it does
    # not touch the proposals hanging off the brief — so after a cancellation
    # every proposal on it is still `submitted`, and without this guard the
    # buyer could turn one into a contract afterwards. The creators were
    # notified the brief was off; the contract would be written against them
    # anyway, and payments.assert_fundable asks only about the contract's own
    # status, never about the campaign behind it, so it would fund normally.
    #
    # Written as "must be PUBLISHED" rather than "must not be CANCELLED"
    # because the set of states that are not open is going to grow — a
    # completed state is coming — and only the open one is worth naming.
    if campaign.status != campaigns.PUBLISHED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="contract_campaign_not_open",
            detail="This campaign is no longer open, so no new contract can be created from it.",
        )

    # A proposal id names a negotiation, not a frozen offer. Since the business
    # can now counter, the chain moves on — sometimes by the business's own
    # hand — and the id on the page can be a round or two behind. The contract
    # is written from the LAST version in the chain, so nobody ever signs terms
    # that were already replaced.
    latest = campaigns_service.latest_in_chain(db, proposal.campaign_id, proposal.influencer_user_id) or proposal

    existing = (
        db.query(models.Contract)
        .filter(models.Contract.proposal_id.in_({proposal_id, latest.id}))
        .first()
    )
    if existing is not None:
        raise AppError(
            status.HTTP_409_CONFLICT,
            code="contract_already_exists",
            detail="A contract already exists for this proposal",
        )
    if latest.status != campaigns.SUBMITTED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="contract_proposal_not_submitted",
            detail="Only a submitted proposal can be accepted",
        )

    # Accepting is ANSWERING, so the live version has to be the other side's.
    # The caller here is the business, so it has to be the creator's. Without
    # this the buyer can accept its own direct order, or its own counter on a
    # brief: that marks the chain accepted and writes a contract the creator
    # never agreed to, and the creator's decline then fails with
    # order_not_open (campaigns/orders.py) — they cannot even turn it down.
    # campaigns/orders.py::_require_business_offer is this same rule facing
    # the other way, and order_own_counter is its refusal for the creator.
    if not allow_business_offer and latest.author_role != campaigns.AUTHOR_INFLUENCER:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="contract_own_offer",
            detail="You cannot accept your own offer. The other party has to accept it.",
        )

    # The window the order was placed under. Only a direct order carries an
    # expires_at — NULL for anything born of a brief, deliberately — and a
    # counter INHERITS it rather than restarting the clock, so a negotiated
    # order can lapse mid-chain and still be sitting here as `submitted`:
    # expire_stale_orders is admin-triggered and may not have run.
    #
    # order_expired rather than a contract-prefixed code of its own. It is the
    # same rule on the same column as campaigns/orders.py, and this refusal can
    # only ever fire on a direct order, so "order" is the right noun on both
    # surfaces — the same reasoning that has campaign_not_yours shared above.
    if latest.expires_at is not None and latest.expires_at <= models.utcnow():
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="order_expired",
            detail="This order has expired.",
        )

    business = db.query(User).filter(User.id == business_user_id).first()
    influencer = db.query(User).filter(User.id == latest.influencer_user_id).first()
    language = _language_for(business.country_code)

    # Accepting the proposal is what triggers contract generation.
    latest.status = campaigns.PROPOSAL_ACCEPTED

    contract = models.Contract(
        campaign_id=campaign.id,
        proposal_id=latest.id,
        business_user_id=business.id,
        influencer_user_id=influencer.id,
        language=language,
        body=_build_body(language, campaign, latest, business, influencer),
        rate_amount=latest.rate_amount,
        rate_currency=latest.rate_currency,
        timeline_days=latest.timeline_days,
        deliverables=campaign.deliverables,
        status=models.PENDING,
    )
    db.add(contract)
    db.flush()
    db.add(models.ContractEvent(contract_id=contract.id, actor_user_id=business_user_id, event="generated"))
    notify(db, influencer.id, "contract_ready", f"A contract is ready to sign for {campaign.title}",
           link=f"/contracts/{contract.id}", params={"key": "contract_ready", "campaign": campaign.title})
    db.commit()
    db.refresh(contract)
    return _out(contract)


def get_contract(db: Session, contract_id: str, user_id: str) -> dict:
    contract = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if contract is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="contract_not_found",
            detail="Contract not found",
        )
    if user_id not in (contract.business_user_id, contract.influencer_user_id):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="contract_not_a_party",
            detail="Not a party to this contract",
        )
    out = _out(contract)
    out["body"] = contract.body
    return out


def sign_contract(db: Session, contract_id: str, user_id: str, signature: str) -> dict:
    contract = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if contract is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="contract_not_found",
            detail="Contract not found",
        )
    if user_id not in (contract.business_user_id, contract.influencer_user_id):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="contract_not_a_party",
            detail="Not a party to this contract",
        )
    # Refused HERE, and not only in contracts/cancellation.py. A signature
    # completes the pair, the pair flips the status to SIGNED, and SIGNED is
    # the only thing payments.assert_fundable asks about before an escrow is
    # funded. So without this guard a contract cancelled after one party had
    # signed is brought back by the other party's signature and becomes
    # collectable in real money — an ended deal, funded, with a
    # contract_events trail saying it was called off.
    if contract.status == models.CANCELLED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="contract_sign_cancelled",
            detail=CANCELLED_SIGN_DETAIL,
        )
    if contract.status == models.SIGNED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="contract_signed_immutable",
            detail="Contract is fully signed and immutable",
        )

    now = models.utcnow()
    if user_id == contract.business_user_id:
        if contract.business_signed_at is not None:
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                # One code for both sides. It is the same rule — you sign once —
                # and which half of the contract the caller is on is not
                # something the sentence says or needs to.
                code="contract_you_already_signed",
                detail="You have already signed",
            )
        contract.business_signature = signature
        contract.business_signed_at = now
        db.add(models.ContractEvent(contract_id=contract.id, actor_user_id=user_id, event="signed_business"))
    else:
        if contract.influencer_signed_at is not None:
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                # One code for both sides. It is the same rule — you sign once —
                # and which half of the contract the caller is on is not
                # something the sentence says or needs to.
                code="contract_you_already_signed",
                detail="You have already signed",
            )
        contract.influencer_signature = signature
        contract.influencer_signed_at = now
        db.add(models.ContractEvent(contract_id=contract.id, actor_user_id=user_id, event="signed_influencer"))

    if contract.business_signed_at is not None and contract.influencer_signed_at is not None:
        contract.status = models.SIGNED
        db.add(models.ContractEvent(contract_id=contract.id, actor_user_id=user_id, event="fully_signed"))
        notify(db, contract.business_user_id, "contract_signed", "Your contract is fully signed",
               link=f"/contracts/{contract.id}", params={"key": "contract_signed"})
        notify(db, contract.influencer_user_id, "contract_signed", "Your contract is fully signed",
               link=f"/contracts/{contract.id}", params={"key": "contract_signed"})

    db.commit()
    db.refresh(contract)
    return _out(contract)


def get_contract_by_proposal(db: Session, proposal_id: str, user_id: str) -> dict:
    contract = db.query(models.Contract).filter(models.Contract.proposal_id == proposal_id).first()
    if contract is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="contract_none_for_proposal",
            detail="No contract for this proposal",
        )
    if user_id not in (contract.business_user_id, contract.influencer_user_id):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="contract_not_a_party",
            detail="Not a party to this contract",
        )
    return _out(contract)


def list_my_contracts(db: Session, user_id: str) -> list[dict]:
    """Every contract the caller is a party to, newest first, each carrying the
    campaign it is for and the OTHER party by name.

    A card that shows only a rate and a timeline makes somebody open each
    contract to remember which job it was. So the list resolves, in batch, the
    campaign title and the counterparty the same way every other list names a
    person: a creator by display name and photo (core.identity), a business by
    its company name and no photo, and null rather than a phone number when the
    other side has written no profile yet.

    THE COUNTERPARTY IS WHICHEVER PARTY THE CALLER IS NOT, derived per row
    rather than from the caller's role. A user has one role, so a business
    always reads creators here and a creator always reads businesses — but
    deriving it from the row means the two can never fall out of step.

    IT ALSO CARRIES THE ESCROW STATUS, because that is the only thing that
    says whether a contract is FINISHED. A contract's own status never becomes
    "completed" — it stops at signed — so a list that showed only that had no
    way to separate the three jobs somebody is still working on from the
    thirty they finished last quarter. Released or refunded is an ending;
    held or disputed is not; null means nobody has funded it yet. The web app
    splits Active from Completed on exactly that (web/src/lib/lifecycle.ts).

    Batched, not per row: the titles are one query, the escrow statuses one,
    the creator identities two (core.identity), the company names one. A page
    of contracts is a handful of campaigns and a handful of counterparties,
    and this keeps it that way however long the list grows.
    """
    rows = (
        db.query(models.Contract)
        .filter(or_(models.Contract.business_user_id == user_id, models.Contract.influencer_user_id == user_id))
        .order_by(models.Contract.created_at.desc())
        .all()
    )
    if not rows:
        return []

    campaign_titles = dict(
        db.query(campaigns.Campaign.id, campaigns.Campaign.title)
        .filter(campaigns.Campaign.id.in_({c.campaign_id for c in rows}))
        .all()
    )
    # escrows.contract_id is UNIQUE, so this is at most one row per contract
    # and the dict cannot lose one.
    escrow_statuses = dict(
        db.query(payments.Escrow.contract_id, payments.Escrow.status)
        .filter(payments.Escrow.contract_id.in_({c.id for c in rows}))
        .all()
    )
    # Split the counterparties by which kind of name they need. When the caller
    # is the business the other party is a creator, with an identity; when the
    # caller is the creator it is a business, with a company name and no avatar.
    creator_ids = {c.influencer_user_id for c in rows if c.business_user_id == user_id}
    business_ids = {c.business_user_id for c in rows if c.business_user_id != user_id}
    identities = creator_identities(db, creator_ids)
    company_names = (
        dict(
            db.query(BusinessProfile.user_id, BusinessProfile.company_name)
            .filter(BusinessProfile.user_id.in_(business_ids))
            .all()
        )
        if business_ids
        else {}
    )

    result = []
    for c in rows:
        item = _out(c)
        item["campaign_title"] = campaign_titles.get(c.campaign_id)
        item["created_at"] = c.created_at
        # None when the contract has never been funded, which is a live state
        # and not an ending — the brand simply has not paid in yet.
        item["escrow_status"] = escrow_statuses.get(c.id)
        if c.business_user_id == user_id:
            identity = identities.get(c.influencer_user_id) or {}
            item["counterparty_name"] = identity.get("display_name")
            item["counterparty_avatar_url"] = identity.get("avatar_url")
        else:
            # A business has a company name and no avatar in this system.
            item["counterparty_name"] = company_names.get(c.business_user_id)
            item["counterparty_avatar_url"] = None
        result.append(item)
    return result

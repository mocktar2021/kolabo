"""Tests for Epic E (KOL-5): contract generation and e-signature.

The party-details block at the bottom of the file covers slice 1 of
claude/kolabo-contract-parties-spec.md: a generated contract has to say WHO
signed it, from a snapshot taken at generation, and it has to be able to prove
afterwards that the text has not moved.

The licence block after it covers Article 10 of the approved model
(claude/kolabo-contrat-collaboration-modele-fr.md): the parties have to choose
how the brand may use the content, the brand states that choice before the
contract exists, and the contract freezes it.
"""
import hashlib
import re
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.errors import AppError, app_error_handler
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.campaigns import models as campaigns
from app.modules.contracts import service as contracts_service
from app.modules.contracts.router import router as contracts_router
from app.modules.profiles.models import BusinessProfile, InfluencerProfile


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    # The REAL AppError handler, registered from app.core.errors the way
    # app/main.py does it, so a refusal reaches the client carrying its `code`.
    # Without it FastAPI's default HTTPException handler answers with `detail`
    # alone and a test cannot assert WHICH rule refused — which is the thing
    # both clients key their translated sentence off. Same reasoning, and the
    # same handler, as test_error_codes.py's fixture.
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(contracts_router, prefix="/contracts")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = testing_session
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


# What each side states about itself, which is the whole of what a contract has
# to name its parties with. Deliberately not tidied: a real RCCM number carries
# slashes and a space, an Ifu is not the registration number, and the accents
# are there because a Beninese company's name and a Togolese address have them.
#
# The business is a registered company and the creator a sole trader, which is
# the ordinary pairing. The tests further down use the other combinations,
# because the field set follows party_type and NOT which side of the contract
# the block sits on.
COMPANY_NAME = "Maison Zinsou SARL"

BUSINESS_PARTY = {
    "party_type": "registered_company",
    "display_label": COMPANY_NAME,
    "legal_name": COMPANY_NAME,
    "legal_form": "SARL",
    "registration_number": "RB/COT/23 B 12345",
    "tax_identifier": "3201234567890",
    "address": "Lot 42, Haie Vive, Cotonou",
    "country": "BJ",
    "representative_name": "Adeline Zinsou",
    "representative_capacity": "Gérante",
}

CREATOR_PARTY = {
    "party_type": "sole_trader",
    "display_label": "Kossi Amegan",
    "legal_name": "Kossi Amegan",
    "address": "Quartier Tokoin, Lomé",
    "country": "TG",
}

ASSOCIATION_PARTY = {
    "party_type": "association",
    "display_label": "Collectif Jeunesse Numérique",
    "legal_name": "Collectif Jeunesse Numérique",
    "registration_number": "2019/ASSOC/0041",
    "address": "Rue 12.034, Abidjan",
    "country": "CI",
    "representative_name": "Sarah Koné",
    "representative_capacity": "Présidente",
}

AGENCY_PARTY = {
    "party_type": "registered_company",
    "display_label": "Studio Lagune SAS",
    "legal_name": "Studio Lagune SAS",
    "legal_form": "SAS",
    "registration_number": "CI/ABJ/18 B 9981",
    "tax_identifier": "CI-9981-TVA",
    "address": "Boulevard Latrille, Abidjan",
    "country": "CI",
    "representative_name": "Yao Brou",
    "representative_capacity": "Directeur",
}

# And how the brand says it may use the content: the three options of Article
# 10, each one COMPLETE for its own option and carrying no key that belongs to
# another.
#
# Written out as stored blocks rather than built from a helper, for the reason
# the party blocks above are: a reader of a failing assertion needs to see the
# exact value, and the point of several of these cases is that a block holds
# the keys its option requires AND NO OTHERS.
#
# The French is real French, accents included, because these values are quoted
# into a contract verbatim. Nothing on the way in or the way out normalises,
# folds or translates them, and a fixture written in ASCII would hide that.
LICENCE_CREATOR_ONLY = {"licence_option": "1"}

LICENCE_REDISTRIBUTION = {
    "licence_option": "2",
    "licence_duration": "douze (12) mois à compter de la première publication",
    "licence_territories": "Bénin, Togo et Côte d'Ivoire",
    "licence_media": "réseaux sociaux de la marque, son site web et la publicité payante en ligne",
}

LICENCE_ASSIGNMENT = {
    "licence_option": "3",
    "licence_duration": "toute la durée légale de protection",
    "licence_territories": "monde entier",
    "licence_consideration": "contrepartie distincte de 150 000 XOF convenue entre les Parties",
}


def _setup(
    client,
    proposal_status=campaigns.SUBMITTED,
    country="BJ",
    business_party=BUSINESS_PARTY,
    creator_party=CREATOR_PARTY,
    licence_terms=LICENCE_REDISTRIBUTION,
):
    """Create a business, an influencer, a published campaign, and a proposal.

    BOTH PROFILES NOW CARRY PARTY DETAILS, because generation refuses without
    them: a contract that cannot name its parties is not one this product
    writes. Pass None for either side to get a profile row with an empty block,
    which is what a user who has not filled the form yet looks like.

    AND THE BRIEF CARRIES A LICENCE, for the same reason: generation refuses
    without one too (contract_licence_terms_missing). Option 2 by default
    because it is the one with the longest required set and the one the model's
    own annex calls the most frequent in practice; pass another block to
    generate under a different option, or None for a brief that states none.

    The creator's profile deliberately has NO display_name. party_details and
    display_name answer different questions and neither is derived from the
    other: display_name is a storefront name that enrichment sometimes writes
    from a social platform's API, so it is often a handle. A creator who has
    stated who they are for a contract and has not chosen a storefront name is
    a real state, and the contract list is tested against it below.

    The dicts are copied in rather than handed over, so a test that mutates a
    stored block cannot reach back into the module constants above.
    """
    db = client.session_factory()
    try:
        biz = User(phone="+22990000001", email="22990000001@kolabo.test", password_hash="x", country_code=country, role="business", is_verified=True)
        inf = User(phone="+22990000002", email="22990000002@kolabo.test", password_hash="x", country_code=country, role="influencer", is_verified=True)
        db.add_all([biz, inf]); db.commit(); db.refresh(biz); db.refresh(inf)
        db.add(BusinessProfile(
            user_id=biz.id,
            company_name=COMPANY_NAME,
            party_details=dict(business_party) if business_party else None,
        ))
        db.add(InfluencerProfile(
            user_id=inf.id,
            display_name=None,
            party_details=dict(creator_party) if creator_party else None,
        ))
        db.commit()
        camp = campaigns.Campaign(
            business_user_id=biz.id, title="Launch push", budget_amount=50000, budget_currency="XOF",
            deliverables=[{"platform": "instagram", "type": "post", "quantity": 2}],
            licence_terms=dict(licence_terms) if licence_terms else None,
            deadline=None, status=campaigns.PUBLISHED,
        )
        db.add(camp); db.commit(); db.refresh(camp)
        prop = campaigns.Proposal(
            campaign_id=camp.id, influencer_user_id=inf.id, version=1,
            rate_amount=10000, rate_currency="XOF", timeline_days=7, status=proposal_status,
        )
        db.add(prop); db.commit(); db.refresh(prop)
        return biz.id, inf.id, camp.id, prop.id
    finally:
        db.close()


def test_generate_contract_from_submitted_proposal(client):
    biz, inf, camp, prop = _setup(client)
    r = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending_signatures"
    assert body["rate_amount"] == 10000
    assert body["fully_signed"] is False
    # Proposal is now accepted.
    db = client.session_factory()
    p = db.query(campaigns.Proposal).filter(campaigns.Proposal.id == prop).first()
    db.close()
    assert p.status == "accepted"


def test_generated_body_is_french_placeholder_for_bj(client):
    biz, inf, camp, prop = _setup(client, country="BJ")
    contract = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()
    detail = client.get(f"/contracts/{contract['id']}", headers=_headers(biz)).json()
    assert detail["language"] == "fr"
    assert "MODELE PROVISOIRE" in detail["body"]


def test_generate_requires_ownership(client):
    biz, inf, camp, prop = _setup(client)
    r = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(inf))
    assert r.status_code == 403


def test_cannot_generate_twice_for_same_proposal(client):
    biz, inf, camp, prop = _setup(client)
    assert client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).status_code == 201
    assert client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).status_code == 409


def test_both_signatures_required_then_immutable(client):
    biz, inf, camp, prop = _setup(client)
    contract = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()
    cid = contract["id"]
    r = client.post(f"/contracts/{cid}/sign", json={"signature": "Business Rep"}, headers=_headers(biz))
    assert r.json()["business_signed"] is True
    assert r.json()["fully_signed"] is False
    r = client.post(f"/contracts/{cid}/sign", json={"signature": "The Creator"}, headers=_headers(inf))
    assert r.json()["fully_signed"] is True
    assert r.json()["status"] == "signed"
    # Immutable once fully signed.
    r = client.post(f"/contracts/{cid}/sign", json={"signature": "again"}, headers=_headers(biz))
    assert r.status_code == 400


def test_non_party_cannot_sign(client):
    biz, inf, camp, prop = _setup(client)
    contract = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()
    other = "outsider-user-id"
    r = client.post(f"/contracts/{contract['id']}/sign", json={"signature": "x"}, headers=_headers(other))
    assert r.status_code == 403


def test_double_sign_by_same_party_rejected(client):
    biz, inf, camp, prop = _setup(client)
    contract = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()
    cid = contract["id"]
    client.post(f"/contracts/{cid}/sign", json={"signature": "Business Rep"}, headers=_headers(biz))
    r = client.post(f"/contracts/{cid}/sign", json={"signature": "Business Rep again"}, headers=_headers(biz))
    assert r.status_code == 400


def test_signing_a_cancelled_contract_is_refused_and_writes_nothing(client):
    """A cancelled contract is not signable, and the refusal leaves no trace.

    Its own code rather than contract_signed_immutable: this contract is not
    signed, it is over, and the two refusals point somewhere different. The
    second half matters more than the first — a refusal that still stamped the
    signature would be the worse bug, because the stamps are exactly what
    sign_contract reads to decide the contract is fully signed.
    """
    from app.modules.contracts import models as contracts

    biz, inf, camp, prop = _setup(client)
    cid = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()["id"]
    assert client.post(f"/contracts/{cid}/cancel", headers=_headers(biz)).status_code == 200

    db = client.session_factory()
    before = db.query(contracts.ContractEvent).filter(contracts.ContractEvent.contract_id == cid).count()
    db.close()

    r = client.post(f"/contracts/{cid}/sign", json={"signature": "Business Rep"}, headers=_headers(biz))
    assert r.status_code == 400
    assert r.json()["code"] == "contract_sign_cancelled"

    db = client.session_factory()
    contract = db.query(contracts.Contract).filter(contracts.Contract.id == cid).first()
    after = db.query(contracts.ContractEvent).filter(contracts.ContractEvent.contract_id == cid).count()
    db.close()
    assert contract.status == contracts.CANCELLED
    assert contract.business_signature is None
    assert contract.business_signed_at is None
    # No signed_business row was added on the way out of the refusal.
    assert after == before


def test_a_cancelled_contract_cannot_be_signed_back_to_life_by_the_other_party(client):
    """The actual exploit, end to end: sign, cancel, then sign anyway.

    The business signs, the creator calls the deal off — allowed, because it
    is not fully signed and no escrow exists against it — and then the creator
    signs after all. Without the guard that second signature completes the
    pair, the pair sets the status to signed, and payments.assert_fundable
    asks nothing except whether the status is signed: an ended deal becomes
    fundable, and the money is real.
    """
    from app.modules.contracts import models as contracts

    biz, inf, camp, prop = _setup(client)
    cid = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()["id"]
    assert client.post(f"/contracts/{cid}/sign", json={"signature": "Business Rep"},
                       headers=_headers(biz)).status_code == 200
    assert client.post(f"/contracts/{cid}/cancel", headers=_headers(inf)).status_code == 200

    r = client.post(f"/contracts/{cid}/sign", json={"signature": "The Creator"}, headers=_headers(inf))
    assert r.status_code == 400
    assert r.json()["code"] == "contract_sign_cancelled"

    db = client.session_factory()
    contract = db.query(contracts.Contract).filter(contracts.Contract.id == cid).first()
    events = [
        e.event
        for e in db.query(contracts.ContractEvent).filter(contracts.ContractEvent.contract_id == cid).all()
    ]
    db.close()
    # Still cancelled. The first signature stands as a record; the contract
    # does not become signed because of it.
    assert contract.status == contracts.CANCELLED
    assert contract.influencer_signature is None
    assert contract.influencer_signed_at is None
    assert "signed_influencer" not in events
    assert "fully_signed" not in events


def test_endpoints_require_auth(client):
    biz, inf, camp, prop = _setup(client)
    assert client.post(f"/contracts/from-proposal/{prop}").status_code == 401


def test_audit_trail_recorded(client):
    biz, inf, camp, prop = _setup(client)
    contract = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()
    cid = contract["id"]
    client.post(f"/contracts/{cid}/sign", json={"signature": "Business Rep"}, headers=_headers(biz))
    client.post(f"/contracts/{cid}/sign", json={"signature": "The Creator"}, headers=_headers(inf))
    from app.modules.contracts.models import ContractEvent
    db = client.session_factory()
    events = [e.event for e in db.query(ContractEvent).filter(ContractEvent.contract_id == cid).all()]
    db.close()
    assert "generated" in events
    assert "signed_business" in events
    assert "signed_influencer" in events
    assert "fully_signed" in events


def test_contract_by_proposal_lookup(client):
    biz, inf, camp, prop = _setup(client)
    created = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()
    found = client.get(f"/contracts/by-proposal/{prop}", headers=_headers(biz))
    assert found.status_code == 200
    assert found.json()["id"] == created["id"]
    # The influencer, a party, can also find it.
    assert client.get(f"/contracts/by-proposal/{prop}", headers=_headers(inf)).status_code == 200
    # A non-party cannot.
    assert client.get(f"/contracts/by-proposal/{prop}", headers=_headers("stranger")).status_code == 403


def test_contract_by_proposal_404_when_none(client):
    biz, inf, camp, prop = _setup(client)
    assert client.get(f"/contracts/by-proposal/{prop}", headers=_headers(biz)).status_code == 404


def test_list_my_contracts_for_both_parties(client):
    biz, inf, camp, prop = _setup(client)
    created = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()
    biz_list = client.get("/contracts/mine", headers=_headers(biz)).json()
    inf_list = client.get("/contracts/mine", headers=_headers(inf)).json()
    assert [c["id"] for c in biz_list] == [created["id"]]
    assert [c["id"] for c in inf_list] == [created["id"]]
    # A non-party sees none.
    assert client.get("/contracts/mine", headers=_headers("stranger")).json() == []


def test_list_my_contracts_carries_campaign_and_counterparty(client):
    """The card reads without opening the contract: the campaign it is for, and
    the OTHER party.

    The creator here has stated who they are for a contract and has chosen no
    storefront name, so the business's card still has no name for them: it
    carries the key as NULL rather than dropping it or falling back to a user
    id or a phone number. The creator's own card names the business by its
    company name, and never carries an avatar for it, because a business has a
    company name and no photo in this system.

    BOTH NAMES ARE RESOLVED LIVE, which is now a known inconsistency rather
    than an oversight: the contract BODY names its parties from the snapshot
    frozen at generation, and this card does not, so a rename shows here and
    not there. See contracts/service.py::list_my_contracts.
    """
    biz, inf, camp, prop = _setup(client)
    client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))

    biz_row = client.get("/contracts/mine", headers=_headers(biz)).json()[0]
    assert biz_row["campaign_title"] == "Launch push"
    assert biz_row["counterparty_name"] is None
    assert biz_row["counterparty_avatar_url"] is None
    assert biz_row["created_at"]

    inf_row = client.get("/contracts/mine", headers=_headers(inf)).json()[0]
    assert inf_row["campaign_title"] == "Launch push"
    assert inf_row["counterparty_name"] == COMPANY_NAME
    assert inf_row["counterparty_avatar_url"] is None


# --------------------------------------------------------------------------
# W2: what may be turned into a contract at all
#
# generate_from_proposal used to ask two questions — is the live version
# `submitted`, and does a contract already exist — and three it did not, all
# of them upstream of money: whose offer is on the table, whether the campaign
# is still open, and whether the offer has lapsed.
#
# Every case below asserts the refusal AND that nothing was written. That
# second half is the one that matters: generation marks the chain `accepted`
# before it writes the contract, and an `accepted` chain is exactly what makes
# the creator's decline fail with order_not_open — so a refusal that still
# wrote would take the creator's way out with it.
# --------------------------------------------------------------------------


def _counter_from_business(client, camp, inf, rate_amount=8000):
    """Add a business-authored version to the chain, superseding the one below.

    What a buyer's counter-offer looks like on a brief, and the shape a direct
    order carries from the moment it is placed.
    """
    db = client.session_factory()
    try:
        previous = (
            db.query(campaigns.Proposal)
            .filter(campaigns.Proposal.campaign_id == camp)
            .order_by(campaigns.Proposal.version.desc())
            .first()
        )
        previous.status = campaigns.SUPERSEDED
        counter = campaigns.Proposal(
            campaign_id=camp,
            influencer_user_id=inf,
            version=previous.version + 1,
            rate_amount=rate_amount,
            rate_currency="XOF",
            timeline_days=7,
            author_role=campaigns.AUTHOR_BUSINESS,
            status=campaigns.SUBMITTED,
            # Carried forward, the way reply_to_proposal carries them.
            expires_at=previous.expires_at,
            licence_terms=previous.licence_terms,
        )
        db.add(counter)
        db.commit()
        db.refresh(counter)
        return counter.id
    finally:
        db.close()


def _contracts_for(client, camp):
    from app.modules.contracts import models as contracts

    db = client.session_factory()
    try:
        return db.query(contracts.Contract).filter(contracts.Contract.campaign_id == camp).all()
    finally:
        db.close()


def _proposal_status(client, proposal_id):
    db = client.session_factory()
    try:
        return (
            db.query(campaigns.Proposal)
            .filter(campaigns.Proposal.id == proposal_id)
            .first()
            .status
        )
    finally:
        db.close()


def test_business_cannot_generate_a_contract_from_its_own_counter(client):
    """The buyer accepting its own offer, which is not an acceptance at all.

    Once the business counters, the live version is the business's own. Taking
    it through the contracts endpoint marked the chain accepted and wrote a
    contract on terms the creator never said yes to — and with the chain then
    `accepted`, the creator's decline came back order_not_open, so they could
    not turn the offer down through the order flow either.
    """
    biz, inf, camp, prop = _setup(client)
    counter = _counter_from_business(client, camp, inf)

    r = client.post(f"/contracts/from-proposal/{counter}", headers=_headers(biz))
    assert r.status_code == 400
    assert r.json()["code"] == "contract_own_offer"

    # The same refusal through the stale id the buyer's page may still hold:
    # generation resolves the chain to its latest version either way.
    stale = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))
    assert stale.status_code == 400
    assert stale.json()["code"] == "contract_own_offer"

    assert _contracts_for(client, camp) == []
    # Still an open offer, still waiting on the creator to answer it.
    assert _proposal_status(client, counter) == campaigns.SUBMITTED


def test_the_order_accept_path_still_generates_a_contract(client):
    """The one caller that may accept a business-authored offer.

    A direct order IS business-authored — the buyer named the terms — and the
    creator is the one saying yes. accept_direct_order passes the BUYER as the
    actor, because contract generation is written from the buyer's side, so
    the exemption has to be an explicit argument: who is calling cannot be
    read off the actor. This is the regression case proving the guard above
    did not close the real flow.
    """
    from app.modules.campaigns import orders
    from app.modules.contracts import models as contracts

    biz, inf, camp, prop = _setup(client)
    db = client.session_factory()
    try:
        campaign = db.query(campaigns.Campaign).filter(campaigns.Campaign.id == camp).first()
        campaign.is_direct = True
        db.add(
            campaigns.CampaignInvitation(
                campaign_id=camp, influencer_user_id=inf, status=campaigns.INVITED
            )
        )
        offer = db.query(campaigns.Proposal).filter(campaigns.Proposal.id == prop).first()
        offer.author_role = campaigns.AUTHOR_BUSINESS
        offer.expires_at = campaigns.utcnow() + timedelta(hours=48)
        db.commit()
    finally:
        db.close()

    db = client.session_factory()
    try:
        contract = orders.accept_direct_order(db, inf, prop)
    finally:
        db.close()

    assert contract["campaign_id"] == camp
    assert contract["status"] == contracts.PENDING
    assert [c.proposal_id for c in _contracts_for(client, camp)] == [prop]
    assert _proposal_status(client, prop) == campaigns.PROPOSAL_ACCEPTED


def test_a_cancelled_campaign_cannot_be_turned_into_a_contract(client):
    """The brief is off, and its proposals are still sitting there `submitted`.

    campaigns/editing.py cancel_campaign changes the campaign's status and
    leaves the proposals alone — it refuses only when a contract already
    exists. So without this guard a buyer could cancel a brief, let every
    invited creator be told it was cancelled, and then accept one of their
    proposals anyway. payments.assert_fundable never looks at the campaign, so
    the contract would sign and fund like any other.
    """
    biz, inf, camp, prop = _setup(client)
    db = client.session_factory()
    try:
        campaign = db.query(campaigns.Campaign).filter(campaigns.Campaign.id == camp).first()
        campaign.status = campaigns.CANCELLED
        db.commit()
    finally:
        db.close()

    r = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))
    assert r.status_code == 400
    assert r.json()["code"] == "contract_campaign_not_open"

    assert _contracts_for(client, camp) == []
    assert _proposal_status(client, prop) == campaigns.SUBMITTED


def test_an_expired_offer_cannot_be_turned_into_a_contract(client):
    """A lapsed direct order the sweep has not reached yet.

    expires_at bounds a direct order's accept window, and every counter in the
    chain inherits it rather than restarting the clock, so a negotiated order
    can lapse while still sitting at `submitted` — expire_stale_orders runs
    only when an admin triggers it.

    order_expired, not a contract-prefixed code of its own: it is the same
    rule on the same column as campaigns/orders.py, and it can only ever fire
    on a direct order, because a brief's proposals carry NULL there.
    """
    biz, inf, camp, prop = _setup(client)
    db = client.session_factory()
    try:
        offer = db.query(campaigns.Proposal).filter(campaigns.Proposal.id == prop).first()
        offer.expires_at = campaigns.utcnow() - timedelta(hours=1)
        db.commit()
    finally:
        db.close()

    r = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))
    assert r.status_code == 400
    assert r.json()["code"] == "order_expired"

    assert _contracts_for(client, camp) == []
    assert _proposal_status(client, prop) == campaigns.SUBMITTED


def test_the_ordinary_brief_acceptance_is_untouched(client):
    """Creator-authored, campaign published, no expiry: still a contract.

    All three guards have to stay false at once for the normal path, so this
    pins that they do — including that a brief's NULL expires_at is read as
    "never expires" rather than as a date already past.
    """
    biz, inf, camp, prop = _setup(client)
    db = client.session_factory()
    try:
        offer = db.query(campaigns.Proposal).filter(campaigns.Proposal.id == prop).first()
        assert offer.author_role == campaigns.AUTHOR_INFLUENCER
        assert offer.expires_at is None
    finally:
        db.close()

    r = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))
    assert r.status_code == 201
    assert [c.proposal_id for c in _contracts_for(client, camp)] == [prop]
    assert _proposal_status(client, prop) == campaigns.PROPOSAL_ACCEPTED


# --------------------------------------------------------------------------
# Party details: who signed this, and how we know the text has not moved
#
# Slice 1 of claude/kolabo-contract-parties-spec.md, sections 5, 6 and 7.8.
#
# What the body said before this pass was "Business party (user id): <uuid>"
# and the same line for the creator. Two consequences, and both are what the
# cases below pin. A signature validated against nothing, because there was no
# legal name in this database for the signature string to be a signature OF.
# And every name shown around a contract was resolved live from a profile its
# owner can rename at any time, so a rename silently restated history.
#
# NOTHING IN A PARTY BLOCK IS VERIFIED, and no test here should be read as
# checking that it is. These are self declared, exactly as they would be on
# paper: the platform records what each party states about itself.
# --------------------------------------------------------------------------


def _contract_row(client, contract_id):
    from app.modules.contracts import models as contracts

    db = client.session_factory()
    try:
        return (
            db.query(contracts.Contract)
            .filter(contracts.Contract.id == contract_id)
            .first()
        )
    finally:
        db.close()


def _generate(client, biz, prop):
    r = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_generation_refuses_when_the_business_has_not_stated_who_it_is(client):
    """The buyer's own block is empty, and the refusal names the buyer's side.

    Two codes rather than one for the same rule, because the person who has to
    act is different in each case: a sentence that said only "party details
    are missing" would leave the buyer guessing which profile to go and fill.

    And nothing is written on the way out. Generation marks the chain
    `accepted` before it writes the contract, and an `accepted` chain is what
    makes the creator's decline fail with order_not_open, so a refusal that
    still wrote would take the creator's way out with it. That is why the gate
    sits with the other guards and above that assignment.
    """
    biz, inf, camp, prop = _setup(client, business_party=None)

    r = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))
    assert r.status_code == 400
    assert r.json()["code"] == "contract_business_party_missing"

    assert _contracts_for(client, camp) == []
    assert _proposal_status(client, prop) == campaigns.SUBMITTED


def test_generation_refuses_when_the_creator_has_not_stated_who_they_are(client):
    """The creator never filled their block, and the refusal lands on the buyer.

    Which is the whole argument for making party details a precondition
    earlier, on the creator's own onboarding, rather than leaving this as the
    only gate: by the time this fires the buyer has chosen a creator, agreed
    terms and is trying to close, and there is nothing they can do about
    somebody else's profile. The gate stays as the backstop either way.
    """
    biz, inf, camp, prop = _setup(client, creator_party=None)

    r = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))
    assert r.status_code == 400
    assert r.json()["code"] == "contract_creator_party_missing"

    assert _contracts_for(client, camp) == []
    assert _proposal_status(client, prop) == campaigns.SUBMITTED


def test_generation_refuses_when_a_side_has_no_profile_row_at_all(client):
    """No profile, as opposed to a profile with an empty block.

    Two different database states reaching the same refusal, and worth pinning
    separately: the gate reads the column through a scalar query, which comes
    back None both when the row is missing and when the block is null. A buyer
    who registered and went straight to hiring has no business_profiles row at
    all, and that must refuse with the same code rather than fall through.
    """
    biz, inf, camp, prop = _setup(client)
    db = client.session_factory()
    try:
        db.query(BusinessProfile).filter(BusinessProfile.user_id == biz).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()

    r = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))
    assert r.status_code == 400
    assert r.json()["code"] == "contract_business_party_missing"
    assert _contracts_for(client, camp) == []


def test_both_party_blocks_are_snapshotted_and_equal_the_profile_values(client):
    """The snapshot is taken at generation and is a faithful copy of each block.

    Stored on the contract as well as rendered into the body, because the body
    is prose for a person to read and these are the same facts in a shape an
    admin console or a dispute can read field by field.
    """
    biz, inf, camp, prop = _setup(client)
    cid = _generate(client, biz, prop)

    row = _contract_row(client, cid)
    assert row.business_party == BUSINESS_PARTY
    assert row.influencer_party == CREATOR_PARTY

    # And they are the values the profiles held at that moment, read back
    # independently rather than compared against the fixture alone.
    db = client.session_factory()
    try:
        business_block = (
            db.query(BusinessProfile.party_details)
            .filter(BusinessProfile.user_id == biz)
            .scalar()
        )
        creator_block = (
            db.query(InfluencerProfile.party_details)
            .filter(InfluencerProfile.user_id == inf)
            .scalar()
        )
    finally:
        db.close()
    assert row.business_party == business_block
    assert row.influencer_party == creator_block


def test_editing_a_profile_after_generation_leaves_the_snapshot_alone(client):
    """A rename changes the NEXT contract and nothing about this one.

    This is the reason the blocks are copied rather than joined, and it is the
    same reason PaymentIntent copies amounts off the contract instead of
    reading them through a join at settlement. With money a join settles the
    new number against the old payment; with identities it silently restates
    who signed a document months ago, including one already in dispute.

    Both the stored snapshot AND the rendered body are checked, because they
    are two places the old name could leak back in from.
    """
    biz, inf, camp, prop = _setup(client)
    cid = _generate(client, biz, prop)

    db = client.session_factory()
    try:
        business = db.query(BusinessProfile).filter(BusinessProfile.user_id == biz).first()
        business.party_details = {
            **BUSINESS_PARTY,
            "legal_name": "Maison Zinsou SA",
            "display_label": "Maison Zinsou SA",
            "legal_form": "SA",
            "address": "Immeuble Tokpa, Cotonou",
        }
        creator = db.query(InfluencerProfile).filter(InfluencerProfile.user_id == inf).first()
        creator.party_details = {
            **CREATOR_PARTY,
            "legal_name": "Kossi Amegan Junior",
            "display_label": "Kossi Amegan Junior",
            "address": "Avenue de la Liberation, Lomé",
        }
        db.commit()
    finally:
        db.close()

    row = _contract_row(client, cid)
    assert row.business_party == BUSINESS_PARTY
    assert row.influencer_party == CREATOR_PARTY
    assert COMPANY_NAME in row.body
    assert "Kossi Amegan" in row.body
    assert "Maison Zinsou SA\n" not in row.body
    assert "Kossi Amegan Junior" not in row.body
    assert "Immeuble Tokpa, Cotonou" not in row.body


def test_the_french_body_names_both_parties_the_way_the_approved_model_does(client):
    """The party identification block, asserted whole and in order.

    Field for field against the block headed ENTRE LES SOUSSIGNES in
    claude/kolabo-contrat-collaboration-modele-fr.md, which is the model
    counsel approved. Asserted as one contiguous string rather than as a dozen
    substring checks, because the ORDER is part of what was approved and a set
    of `in` assertions would pass on a block that printed the registration
    number under the address.

    The uuids stay, as the last field of each side. They are the only stable
    unique identifier either party has, and they are what an admin searches
    by; a legal name is free text that one company can change and two can
    share.

    NO IDENTITY DOCUMENT LINE. The approved model has one and it is
    deliberately not rendered: no personal identity document is collected, so
    a line asking for one would contradict that and imply a check that does
    not happen.
    """
    biz, inf, camp, prop = _setup(client, country="BJ")
    cid = _generate(client, biz, prop)
    body = _contract_row(client, cid).body

    expected = "\n".join([
        "ENTRE LES SOUSSIGNÉS",
        "",
        "D'une part, l'Entreprise :",
        "Raison sociale : Maison Zinsou SARL",
        "Forme juridique : SARL",
        "Immatriculation (RCCM ou équivalent) : RB/COT/23 B 12345",
        "Identifiant fiscal : 3201234567890",
        "Siège : Lot 42, Haie Vive, Cotonou",
        "Pays : BJ",
        "Représentée par : Adeline Zinsou, en qualité de Gérante",
        f"Identifiant du compte Kolabo : {biz}",
        "Ci-après dénommée « l'Entreprise ».",
        "",
        "D'autre part, le Créateur :",
        "Nom et prénoms : Kossi Amegan",
        "Adresse : Quartier Tokoin, Lomé",
        "Pays de résidence : TG",
        f"Identifiant du compte Kolabo : {inf}",
        "Ci-après dénommé « le Créateur ».",
        "",
        "Ci-après dénommés ensemble « les Parties » et individuellement « une Partie ».",
    ])
    assert expected in body

    # The two lines this replaced, gone from both languages.
    assert "Business party (user id)" not in body
    assert "Influencer party (user id)" not in body
    # And the warning label stays. Naming the parties is what makes the
    # document worth reviewing; it is not the review.
    assert "MODELE PROVISOIRE" in body
    assert "pièce d'identité" not in body.lower()


def test_the_english_body_names_both_parties(client):
    """The same block in English, for the markets that contract in it.

    The party's `country` is the country it contracts FROM and is independent
    of the contract's language and of the account's own country: a Beninese
    company hiring through a Ghanaian account is an ordinary case, and the
    block below says BJ inside an English document on purpose.

    So is the representative's capacity, which stays "Gerante" in the English
    document because that is the word the company used about itself. The
    labels are translated; what a party stated is quoted.
    """
    biz, inf, camp, prop = _setup(client, country="GH")
    cid = _generate(client, biz, prop)
    row = _contract_row(client, cid)
    assert row.language == "en"

    expected = "\n".join([
        "BETWEEN THE UNDERSIGNED",
        "",
        "Of the one part, the Business:",
        "Legal name: Maison Zinsou SARL",
        "Legal form: SARL",
        "Registration number (RCCM or equivalent): RB/COT/23 B 12345",
        "Tax identifier: 3201234567890",
        "Registered office: Lot 42, Haie Vive, Cotonou",
        "Country: BJ",
        "Represented by: Adeline Zinsou, in the capacity of Gérante",
        f"Kolabo account id: {biz}",
        'Hereinafter "the Business".',
        "",
        "Of the other part, the Creator:",
        "Full name: Kossi Amegan",
        "Address: Quartier Tokoin, Lomé",
        "Country of residence: TG",
        f"Kolabo account id: {inf}",
        'Hereinafter "the Creator".',
        "",
        'Hereinafter together "the Parties" and individually "a Party".',
    ])
    assert expected in row.body
    assert "PLACEHOLDER TEMPLATE" in row.body


def test_the_party_type_decides_the_fields_and_the_side_decides_the_heading(client):
    """An NGO buying from an agency, which is neither side's default shape.

    The renderer answers two independent questions and this is the case that
    proves it. WHICH SIDE a block is on fixes the heading above it and the
    designation under it, because that is fixed by the contract. WHAT KIND of
    entity it is fixes which fields print, because that is party_type.

    Both unusual directions at once, deliberately. A business is explicitly
    not required to be a registered company, so an association on the buyer's
    side is a supported case and not a defect; and an agency holding a creator
    account can state a company, so a registered company on the creator's side
    is too. Neither may fall back to the other side's field set.
    """
    biz, inf, camp, prop = _setup(
        client, country="BJ", business_party=ASSOCIATION_PARTY, creator_party=AGENCY_PARTY
    )
    cid = _generate(client, biz, prop)
    body = _contract_row(client, cid).body

    assert "\n".join([
        "D'une part, l'Entreprise :",
        "Dénomination : Collectif Jeunesse Numérique",
        "Immatriculation : 2019/ASSOC/0041",
        "Siège : Rue 12.034, Abidjan",
        "Pays : CI",
        "Représentée par : Sarah Koné, en qualité de Présidente",
        f"Identifiant du compte Kolabo : {biz}",
        "Ci-après dénommée « l'Entreprise ».",
    ]) in body

    assert "\n".join([
        "D'autre part, le Créateur :",
        "Raison sociale : Studio Lagune SAS",
        "Forme juridique : SAS",
        "Immatriculation (RCCM ou équivalent) : CI/ABJ/18 B 9981",
        "Identifiant fiscal : CI-9981-TVA",
        "Siège : Boulevard Latrille, Abidjan",
        "Pays : CI",
        "Représentée par : Yao Brou, en qualité de Directeur",
        f"Identifiant du compte Kolabo : {inf}",
        "Ci-après dénommé « le Créateur ».",
    ]) in body

    # An association has no legal form worth printing and this one states no
    # tax identifier, so neither line appears, empty or otherwise. A blank
    # "Forme juridique :" on a signed document reads as a field somebody was
    # meant to fill in and did not.
    assert "Forme juridique : SARL" not in body
    assert "Nom et prénoms" not in body
    assert "Identifiant fiscal :\n" not in body


def test_a_display_label_that_disagrees_with_the_legal_name_cannot_rename_a_party(client):
    """display_label is derived, so the document never takes its name from it.

    The derivation itself happens at capture, server side, in the profiles
    module: display_label is written from legal_name and is never accepted
    from a client. This is the renderer's half of that guarantee, and it is
    the half that would matter if the other one were ever loosened. The block
    below holds a label nobody could have derived, and the document still
    names the party from legal_name.

    The snapshot is NOT sanitised, and that is correct: it is a faithful copy
    of what the profile held, and rewriting it at generation would make the
    snapshot a different thing from the record it is supposed to be.
    """
    tampered = {**BUSINESS_PARTY, "display_label": "Kolabo Verified Partner"}
    biz, inf, camp, prop = _setup(client, business_party=tampered)
    cid = _generate(client, biz, prop)
    row = _contract_row(client, cid)

    assert row.business_party["display_label"] == "Kolabo Verified Partner"
    assert "Raison sociale : Maison Zinsou SARL" in row.body
    assert "Kolabo Verified Partner" not in row.body


def test_body_sha256_matches_a_fresh_hash_of_the_body(client):
    """The one thing that later proves the text has not moved since signature.

    What signing records is a free text string beside a server timestamp,
    which says somebody signed SOMETHING. This says what. It is computed once
    at generation and never recomputed: a hash refreshed from the current body
    would agree with it by definition and prove nothing.
    """
    biz, inf, camp, prop = _setup(client)
    cid = _generate(client, biz, prop)
    row = _contract_row(client, cid)

    assert row.body_sha256 == hashlib.sha256(row.body.encode("utf-8")).hexdigest()
    # 64 hex characters, so a truncated or hex-less value cannot pass.
    assert re.fullmatch(r"[0-9a-f]{64}", row.body_sha256)

    # Signing does not touch it. The hash is about the document, and the
    # document is finished before anybody signs it.
    client.post(f"/contracts/{cid}/sign", json={"signature": "Adeline Zinsou"}, headers=_headers(biz))
    client.post(f"/contracts/{cid}/sign", json={"signature": "Kossi Amegan"}, headers=_headers(inf))
    after = _contract_row(client, cid)
    assert after.body_sha256 == row.body_sha256
    assert after.body == row.body


def test_legal_version_records_the_terms_that_were_in_force(client):
    biz, inf, camp, prop = _setup(client)
    cid = _generate(client, biz, prop)

    row = _contract_row(client, cid)
    assert row.legal_version == contracts_service.LEGAL_EFFECTIVE_DATE
    assert row.legal_version == "2026-10-03"


def test_the_backend_and_the_published_terms_agree_on_the_effective_date(client):
    """The two copies of LEGAL_EFFECTIVE_DATE, checked against each other.

    There is no terms acceptance record anywhere in this backend and no shared
    constant, so the effective date on the published legal pages is the only
    version marker that exists and the backend keeps a second literal of it.
    A contract stamped 2026-10-03 while the site publishes a later date is
    claiming to have been signed under Terms nobody was showing that day, and
    nothing except this test would notice.

    Skipped rather than failed where the web tree is not checked out, so a
    backend-only image does not fail on a file it was never given.
    """
    legal_page = Path(__file__).resolve().parents[2] / "web" / "src" / "pages" / "LegalPage.tsx"
    if not legal_page.exists():
        pytest.skip("web tree not present in this checkout")
    published = re.search(
        r'LEGAL_EFFECTIVE_DATE\s*=\s*"([^"]+)"', legal_page.read_text(encoding="utf-8")
    )
    assert published, "LEGAL_EFFECTIVE_DATE not found in LegalPage.tsx"
    assert contracts_service.LEGAL_EFFECTIVE_DATE == published.group(1)


@pytest.mark.parametrize(
    "country,sentence",
    [
        (
            "BJ",
            "Tout document que les Parties annexent à la présente collaboration "
            "constitue une annexe entre elles et ne modifie pas les conditions de "
            "paiement énoncées ci-dessus.",
        ),
        (
            "GH",
            "Any document the parties attach to this collaboration is an annex "
            "between them and does not modify the payment terms recorded above.",
        ),
    ],
)
def test_the_annex_sentence_is_on_every_contract_in_both_languages(client, country, sentence):
    """Unconditional, with no annex feature built and nothing attached.

    This is the one part of the pass that cannot be added later. The body is
    hashed at generation and never rehashed, so a contract cannot be amended;
    a sentence introduced the day an upload button ships would be absent from
    every contract signed before it, which is exactly the set the first
    dispute will come from.

    The wording is the spec's and says only what the approved design says.
    Counsel approved the design; her review of this wording is still open, so
    the string here is expected to change and this test is expected to change
    with it.
    """
    biz, inf, camp, prop = _setup(client, country=country)
    cid = _generate(client, biz, prop)
    body = _contract_row(client, cid).body

    assert sentence in body
    # After the payment terms, because it says it does not modify them.
    assert body.index(sentence) > body.index("Agreed rate:")


def test_the_campaign_title_locks_once_a_contract_exists(client):
    """Spec section 5: the body freezes the title, so the brief has to as well.

    Lives in this file rather than in test_campaign_edit.py, where the rest of
    the edit rules are, because the thing that triggers the lock is a contract
    and this is the suite that can make one honestly. It drives
    editing.update_campaign directly, since the fixture here mounts the
    contracts router alone.

    Before a contract the title is editable and must stay that way: nobody
    priced against the words at the top of a brief, and a brand that cannot
    fix a typo deletes and re-posts, which loses the proposals. Afterwards,
    contracts/service.py has copied it into a body that is hashed at
    generation and can never be amended, while the contract card joins the
    live title beside it. A rename leaves the two disagreeing with no way to
    bring the document into line.
    """
    from app.modules.campaigns import editing
    from app.modules.campaigns import schemas as campaigns_schemas

    biz, inf, camp, prop = _setup(client)

    db = client.session_factory()
    try:
        out = editing.update_campaign(
            db, camp, biz, campaigns_schemas.CampaignPatch(title="Launch push v2")
        )
        assert out["title"] == "Launch push v2"
    finally:
        db.close()

    _generate(client, biz, prop)

    db = client.session_factory()
    try:
        with pytest.raises(AppError) as refused:
            editing.update_campaign(
                db, camp, biz, campaigns_schemas.CampaignPatch(title="Something else entirely")
            )
        assert refused.value.code == "campaign_field_locked"
        assert refused.value.values == {"field": "title"}

        # Sending the title back unchanged is not a change, so a client that
        # posts the whole form can still edit everything else on it.
        out = editing.update_campaign(
            db,
            camp,
            biz,
            campaigns_schemas.CampaignPatch(title="Launch push v2", description="Clearer brief"),
        )
        assert out["title"] == "Launch push v2"
        assert out["description"] == "Clearer brief"
    finally:
        db.close()

    # And the frozen copy in the document still says what it said.
    db = client.session_factory()
    try:
        campaign = db.query(campaigns.Campaign).filter(campaigns.Campaign.id == camp).first()
        assert campaign.title == "Launch push v2"
    finally:
        db.close()
    assert "Contract for campaign: Launch push v2" in _contract_row(
        client, _contracts_for(client, camp)[0].id
    ).body


# --------------------------------------------------------------------------
# The content licence: Article 10 of the approved model
#
# The parties have to choose how the brand may use the content, and the model
# offers three options with "Option retenue : [ 1 / 2 / 3 ]" left to be filled
# in per contract. The founder decided the BRAND states that choice before the
# contract exists, with all three kept on offer, and that Kolabo captures it.
#
# What this suite owns is the contract end of it: what a complete statement
# looks like per option, what generation freezes, and what happens when
# nobody stated one. Where a brand states it, and how it reaches a creator
# before they price, is pinned in test_campaigns_negotiation.py (the brief, on
# the board and on the invitation), test_orders.py and
# test_orders_negotiated.py (the order, on the offer row) and test_cart.py.
#
# NOTHING IN A LICENCE BLOCK IS CHECKED AGAINST ANYTHING, and no test here may
# be read as saying otherwise. These are the parties' own words, quoted into a
# contract verbatim; whether a given wording achieves what they want in a
# given market is counsel's question and question 6 of the annex to the model
# already puts it to her.
#
# ARTICLE 10 IS NOT PRINTED INTO THE BODY, deliberately, so no case below
# looks for it there. contracts/service.py::_build_body carries the reasoning:
# the approved model is French only, the body is generated in two languages,
# and inventing an English clause counsel has not seen would be frozen into
# every early contract by the body hash. The column is filled from the first
# contract that carries it precisely because that half cannot be added later.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "block",
    [LICENCE_CREATOR_ONLY, LICENCE_REDISTRIBUTION, LICENCE_ASSIGNMENT],
    ids=["creator_only", "redistribution", "assignment"],
)
def test_a_contract_is_generated_under_any_of_the_three_options(client, block):
    """All three, and the snapshot is the block byte for byte.

    OPTION 1 IS A FIRST-CLASS CHOICE and this is where that is proved: a block
    holding nothing but the option generates a contract exactly as the other
    two do. It is also the shortest possible licence, so a gate that tested
    the block's SIZE rather than its presence would pass the other two and
    refuse this one.

    The values come back unchanged, accents and spacing included, because they
    are quoted into a contract verbatim: nothing between the request and the
    column lower-cases, folds or reorders them.
    """
    biz, inf, camp, prop = _setup(client, licence_terms=block)
    cid = _generate(client, biz, prop)

    assert _contract_row(client, cid).licence_terms == block


def test_a_block_carries_only_the_keys_its_option_requires(client):
    """The required set per option, read off the module that owns it.

    DRIVEN AT campaigns.licence DIRECTLY, for the reason the title-lock test
    above drives editing.update_campaign directly: this fixture mounts the
    contracts router alone, so there is no POST /campaigns here to send a
    form to. The endpoint path is covered in test_orders.py, which does have
    one; what is pinned here is the TABLE, because it is the thing that
    decides what both clients' forms have to ask for.

    Asserted against REQUIRED_BY_OPTION rather than against a literal list, so
    a field moving between required and optional fails in this file rather
    than in a brand's form at the end of a long evening.
    """
    from app.modules.campaigns import licence
    from app.modules.campaigns import schemas as campaigns_schemas

    # Option 1 asks for nothing beyond the choice. The whole point of having
    # three options is that the creator publishing on their own accounts is a
    # complete answer and not a reduced one.
    assert licence.REQUIRED_BY_OPTION["1"] == ()
    assert licence.REQUIRED_BY_OPTION["2"] == (
        "licence_duration",
        "licence_territories",
        "licence_media",
    )
    assert licence.REQUIRED_BY_OPTION["3"] == ("licence_duration", "licence_territories")
    # And a separate consideration belongs to the assignment alone, because
    # that is the only option the model mentions one under.
    assert licence.OPTIONAL_BY_OPTION["3"] == ("licence_consideration",)
    assert licence.OPTIONAL_BY_OPTION["2"] == ()

    # Everything that does not belong to the stated option is DROPPED rather
    # than stored, so a reader can trust that a key's presence means the brand
    # stated it. A consideration sitting on an option 2 licence would read, to
    # a creator or to counsel, as money agreed outside the escrow.
    stored = licence.validated_block(
        campaigns_schemas.LicenceTermsIn(
            licence_option="1",
            licence_duration="douze mois",
            licence_territories="Bénin",
            licence_media="télévision",
            licence_consideration="500 000 XOF",
        )
    )
    assert stored == {"licence_option": "1"}


@pytest.mark.parametrize(
    "payload,missing",
    [
        (
            {"licence_option": "2", "licence_territories": "Bénin", "licence_media": "web"},
            "licence_duration",
        ),
        (
            {"licence_option": "2", "licence_duration": "12 mois", "licence_media": "web"},
            "licence_territories",
        ),
        (
            {"licence_option": "2", "licence_duration": "12 mois", "licence_territories": "Bénin"},
            "licence_media",
        ),
        (
            {"licence_option": "3", "licence_territories": "monde entier"},
            "licence_duration",
        ),
        (
            {"licence_option": "3", "licence_duration": "20 ans"},
            "licence_territories",
        ),
    ],
)
def test_a_sub_field_the_option_requires_cannot_be_left_out(client, payload, missing):
    """One case per required field per option, and the refusal names it.

    THE DURATION IS THE ONE WORTH READING. A redistribution licence with no
    stated duration is a licence of unbounded duration: the brand may run the
    creator's face in paid advertising for as long as it likes, which is not
    what either side agreed and is the single most expensive blank on the
    page. The other two are the same argument one step down.

    licence_terms_invalid for all of them, with the missing fields in `values`,
    which is the trade party_details_invalid already makes: both clients render
    one sentence per code, and a code per field would be ten more sentences to
    keep in step in two languages for what is, to the reader, one message about
    one form.
    """
    from app.modules.campaigns import licence
    from app.modules.campaigns import schemas as campaigns_schemas

    with pytest.raises(AppError) as refused:
        licence.validated_block(campaigns_schemas.LicenceTermsIn(**payload))
    assert refused.value.status_code == 400
    assert refused.value.code == "licence_terms_invalid"
    assert refused.value.values["fields"] == missing


def test_a_value_that_is_only_whitespace_counts_as_missing(client):
    """Blank after trimming is blank.

    A form every input of which is sent posts "" for a field nobody typed in,
    and a textarea somebody tabbed through returns a newline. Storing either
    would put a key on the block saying this brand stated an empty territory,
    and a contract would then quote a clause with a hole in it.
    """
    from app.modules.campaigns import licence
    from app.modules.campaigns import schemas as campaigns_schemas

    with pytest.raises(AppError) as refused:
        licence.validated_block(
            campaigns_schemas.LicenceTermsIn(
                licence_option="2",
                licence_duration="   ",
                licence_territories="Bénin",
                licence_media="web",
            )
        )
    assert refused.value.values["fields"] == "licence_duration"

    # And a licence nobody has stated at all is None rather than a refusal:
    # the columns are nullable because every brief written before they existed
    # has nothing in them, and generation is the gate.
    assert licence.validated_block(campaigns_schemas.LicenceTermsIn()) is None
    assert licence.validated_block(None) is None


def test_sub_fields_with_no_option_are_refused_rather_than_stored(client):
    """A duration and no option is a form half filled in.

    Storing the duration against no option would record a licence nobody can
    read while silently losing the only part that decides what the other
    fields mean. The refusal names all three options, because the caller has
    to choose one before any of the rest means anything.
    """
    from app.modules.campaigns import licence
    from app.modules.campaigns import schemas as campaigns_schemas

    with pytest.raises(AppError) as refused:
        licence.validated_block(
            campaigns_schemas.LicenceTermsIn(licence_duration="douze (12) mois")
        )
    assert refused.value.code == "licence_terms_invalid"
    assert refused.value.values["options"] == "1, 2, 3"


def test_editing_the_brief_after_generation_leaves_the_licence_snapshot_alone(client):
    """The reason the licence is a copy and not a join.

    The same argument the party blocks make, with a sharper consequence. A
    rename restates WHO signed; a rewritten licence restates WHAT THE BRAND
    MAY DO with the creator's face, retroactively, on a document somebody has
    already signed. A join would add a redistribution right nobody agreed to
    and nothing anywhere would record that it had been added.

    The brief is edited directly here rather than through the API, because
    campaigns.editing refuses this edit outright once a proposal exists
    (campaign_field_locked, licence_terms being one of the locked terms, which
    the test below pins). The lock and the snapshot are two independent
    defences and this is the one that holds when the lock is bypassed: a
    backfill, a support fix, or any future path that writes the column.
    """
    biz, inf, camp, prop = _setup(client, licence_terms=LICENCE_REDISTRIBUTION)
    cid = _generate(client, biz, prop)

    db = client.session_factory()
    try:
        campaign = db.query(campaigns.Campaign).filter(campaigns.Campaign.id == camp).first()
        campaign.licence_terms = {
            "licence_option": "3",
            "licence_duration": "toute la durée légale de protection",
            "licence_territories": "monde entier",
        }
        db.commit()
    finally:
        db.close()

    # The contract still says what it said, field for field.
    assert _contract_row(client, cid).licence_terms == LICENCE_REDISTRIBUTION

    # And the brief did change, so this is a real divergence rather than an
    # edit that silently failed.
    db = client.session_factory()
    try:
        assert (
            db.query(campaigns.Campaign)
            .filter(campaigns.Campaign.id == camp)
            .first()
            .licence_terms["licence_option"]
            == "3"
        )
    finally:
        db.close()


def test_the_licence_locks_once_a_creator_has_priced_against_it(client):
    """A bid is a price for the licence as much as for the deliverables.

    licence_terms sits in campaigns.editing.LOCKED_FIELDS with budget,
    currency, deliverables and deadline, because a creator who bid on a brief
    saying the brand would not redistribute the content did not bid on one
    saying the brand may run it in paid advertising for a year. Clearing it is
    a change too, and falls out of the same comparison.

    THE OTHER HALF MATTERS JUST AS MUCH. Re-sending the SAME licence is not a
    change, and that is what keeps the rest of the form editable for any
    client that posts all of it — which both of these do. It is also the only
    thing standing between a nested payload and a field that is permanently
    locked, because the comparison is against the stored block: a raw model
    dump carries all five keys with nulls, the column carries only the keys
    its option needs, and update_campaign converts before it compares.

    Driven at editing.update_campaign directly, for the reason the title-lock
    test above gives: this fixture mounts the contracts router alone.
    """
    from app.modules.campaigns import editing
    from app.modules.campaigns import schemas as campaigns_schemas

    # A proposal exists from the moment _setup returns, which is what arms the
    # lock: this brief has been priced against.
    biz, inf, camp, prop = _setup(client, licence_terms=LICENCE_REDISTRIBUTION)

    db = client.session_factory()
    try:
        out = editing.update_campaign(
            db,
            camp,
            biz,
            campaigns_schemas.CampaignPatch(
                licence_terms=campaigns_schemas.LicenceTermsIn(**LICENCE_REDISTRIBUTION),
                description="Clearer brief",
            ),
        )
        assert out["licence_terms"] == LICENCE_REDISTRIBUTION
        assert out["description"] == "Clearer brief"

        with pytest.raises(AppError) as refused:
            editing.update_campaign(
                db,
                camp,
                biz,
                campaigns_schemas.CampaignPatch(
                    licence_terms=campaigns_schemas.LicenceTermsIn(**LICENCE_CREATOR_ONLY)
                ),
            )
        assert refused.value.code == "campaign_field_locked"
        assert refused.value.values == {"field": "licence_terms"}

        # Taking the clause back out is a change like any other.
        with pytest.raises(AppError) as cleared:
            editing.update_campaign(
                db, camp, biz, campaigns_schemas.CampaignPatch(licence_terms=None)
            )
        assert cleared.value.values == {"field": "licence_terms"}
    finally:
        db.close()

    # Nothing moved on the brief the creator priced.
    db = client.session_factory()
    try:
        assert (
            db.query(campaigns.Campaign).filter(campaigns.Campaign.id == camp).first().licence_terms
            == LICENCE_REDISTRIBUTION
        )
    finally:
        db.close()


def test_the_offer_s_own_licence_wins_over_the_campaign_s(client):
    """The precedence _licence_snapshot exists for, which is how an order works.

    A brief states its licence on the brief; a direct order states it on the
    brand's own offer row, because there the proposal IS the offer and the
    campaign behind it is a wrapper nobody reads terms from. So a proposal that
    states one wins, and that is the only rule in that function.

    Both are set here, which cannot happen through any endpoint today — an
    order's campaign carries no licence and a brief's proposals carry none —
    and that is the point: the rule is asserted directly rather than inferred
    from a path that happens to only ever set one of the two.
    """
    biz, inf, camp, prop = _setup(client, licence_terms=LICENCE_REDISTRIBUTION)

    db = client.session_factory()
    try:
        offer = db.query(campaigns.Proposal).filter(campaigns.Proposal.id == prop).first()
        offer.licence_terms = dict(LICENCE_CREATOR_ONLY)
        db.commit()
    finally:
        db.close()

    cid = _generate(client, biz, prop)
    assert _contract_row(client, cid).licence_terms == LICENCE_CREATOR_ONLY


def test_generation_refuses_when_nobody_has_stated_a_licence(client):
    """No licence on the brief and none on the offer, so there is nothing to freeze.

    IT REFUSES RATHER THAN DEFAULTING, and option 1 is why that is worth a
    test. Option 1 grants the brand least, so assuming it looks conservative
    and is not: recorded against a brief whose brand meant to redistribute, it
    is a statement nobody made, frozen into a document two people sign, and
    the first anybody would hear of it is a brand running content it believes
    it licensed.

    And nothing is written on the way out, for the reason the party gate gives:
    marking the chain accepted is what makes the creator's decline fail with
    order_not_open, so a refusal below that line would take the creator's way
    out with it. Both gates therefore sit above it, with the other guards.
    """
    biz, inf, camp, prop = _setup(client, licence_terms=None)

    r = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))
    assert r.status_code == 400
    assert r.json()["code"] == "contract_licence_terms_missing"
    # The sentence names the brand as the party who has to act, because the
    # creator reads this one too on a direct order and it is not theirs to fix.
    assert "brand" in r.json()["detail"]

    assert _contracts_for(client, camp) == []
    assert _proposal_status(client, prop) == campaigns.SUBMITTED


def test_the_detail_response_carries_all_three_snapshots(client):
    """What the clients read, because the body prints none of these three.

    The party blocks ARE rendered into the text as well; Article 10 is not, so
    this payload is the only way either client can show a party the licence
    their contract was generated under. It is also the fix for the two party
    blocks, which were declared on ContractDetailOut and never put on the dict
    the service returns, so they had been arriving null on every read.

    Read off the row and not through a join: what this says is what the
    contract said when it was generated, whatever the profiles and the brief
    say now.
    """
    biz, inf, camp, prop = _setup(client)
    cid = _generate(client, biz, prop)

    detail = client.get(f"/contracts/{cid}", headers=_headers(biz)).json()
    assert detail["business_party"] == BUSINESS_PARTY
    assert detail["influencer_party"] == CREATOR_PARTY
    assert detail["licence_terms"] == LICENCE_REDISTRIBUTION

    # The creator, the other party, reads the same three.
    creator_side = client.get(f"/contracts/{cid}", headers=_headers(inf)).json()
    assert creator_side["licence_terms"] == LICENCE_REDISTRIBUTION
    assert creator_side["business_party"] == BUSINESS_PARTY

    # And Article 10 is still not in the document itself. If this assertion
    # ever fails it is because somebody rendered the clause, which is a change
    # counsel has to have answered for first (contracts/service.py::_build_body).
    assert "licence" not in detail["body"].lower()
    assert LICENCE_REDISTRIBUTION["licence_duration"] not in detail["body"]

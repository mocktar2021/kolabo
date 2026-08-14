"""Tests for Epic E (KOL-5): contract generation and e-signature."""
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
from app.modules.contracts.router import router as contracts_router


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


def _setup(client, proposal_status=campaigns.SUBMITTED, country="BJ"):
    """Create a business, an influencer, a published campaign, and a proposal."""
    db = client.session_factory()
    try:
        biz = User(phone="+22990000001", password_hash="x", country_code=country, role="business", is_verified=True)
        inf = User(phone="+22990000002", password_hash="x", country_code=country, role="influencer", is_verified=True)
        db.add_all([biz, inf]); db.commit(); db.refresh(biz); db.refresh(inf)
        camp = campaigns.Campaign(
            business_user_id=biz.id, title="Launch push", budget_amount=50000, budget_currency="XOF",
            deliverables=[{"platform": "instagram", "type": "post", "quantity": 2}],
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
    the OTHER party. No profiles exist in this setup, so the counterparty has
    no name yet — the row still carries the keys, as null, rather than dropping
    them or falling back to a user id or a phone number."""
    biz, inf, camp, prop = _setup(client)
    client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))

    biz_row = client.get("/contracts/mine", headers=_headers(biz)).json()[0]
    assert biz_row["campaign_title"] == "Launch push"
    assert biz_row["counterparty_name"] is None
    assert biz_row["counterparty_avatar_url"] is None
    assert biz_row["created_at"]

    # The creator's own view names the business as the counterparty (null here,
    # no profile) and never carries an avatar for it — a business has a company
    # name and no photo in this system.
    inf_row = client.get("/contracts/mine", headers=_headers(inf)).json()[0]
    assert inf_row["campaign_title"] == "Launch push"
    assert inf_row["counterparty_name"] is None
    assert inf_row["counterparty_avatar_url"] is None

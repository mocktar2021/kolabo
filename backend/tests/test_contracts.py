"""Tests for Epic E (KOL-5): contract generation and e-signature."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
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

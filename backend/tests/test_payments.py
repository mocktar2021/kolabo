"""Tests for Epic G (KOL-7): escrow funding, release, dispute, resolution."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.contracts import models as contracts
from app.modules.payments import provider as provider_module
from app.modules.payments import service as pay_service
from app.modules.payments import models as pay_models
from app.modules.payments.router import router as payments_router


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    # Fresh mock provider per test so we can inspect collections and payouts.
    pay_service.payment_provider = provider_module.MockProvider()

    app = FastAPI()
    app.include_router(payments_router, prefix="/payments")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


ADMIN = {"X-Admin-Id": "admin-1"}


def _signed_contract(client, signed=True, amount=10000):
    db = client.session_factory()
    try:
        biz = User(phone="+22990000001", password_hash="x", country_code="BJ", role="business", is_verified=True)
        inf = User(phone="+22990000002", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add_all([biz, inf]); db.commit(); db.refresh(biz); db.refresh(inf)
        c = contracts.Contract(
            campaign_id="camp-1", proposal_id="prop-1", business_user_id=biz.id, influencer_user_id=inf.id,
            language="fr", body="body", rate_amount=amount, rate_currency="XOF", timeline_days=7,
            status=contracts.SIGNED if signed else contracts.PENDING,
        )
        db.add(c); db.commit(); db.refresh(c)
        return biz.id, inf.id, c.id
    finally:
        db.close()


def test_fund_requires_signed_contract(client):
    biz, inf, cid = _signed_contract(client, signed=False)
    r = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz))
    assert r.status_code == 400


def test_fund_holds_money_and_calls_provider(client):
    biz, inf, cid = _signed_contract(client)
    r = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz))
    assert r.status_code == 201
    assert r.json()["status"] == "held"
    assert len(pay_service.payment_provider.collections) == 1
    assert pay_service.payment_provider.collections[0]["amount"] == 10000


def test_fund_requires_ownership_and_no_double_fund(client):
    biz, inf, cid = _signed_contract(client)
    assert client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(inf)).status_code == 403
    assert client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).status_code == 201
    assert client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).status_code == 409


def test_release_deducts_commission(client):
    biz, inf, cid = _signed_contract(client, amount=10000)
    escrow = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).json()
    r = client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "released"
    # 15 percent of 10000 is 1500 commission; payout is 8500.
    assert body["commission_amount"] == 1500
    assert pay_service.payment_provider.payouts[0]["amount"] == 8500


def test_only_business_can_release(client):
    biz, inf, cid = _signed_contract(client)
    escrow = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).json()
    assert client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(inf)).status_code == 403


def test_auto_release_after_timeout(client):
    biz, inf, cid = _signed_contract(client)
    escrow = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).json()
    # Force the due date into the past.
    db = client.session_factory()
    e = db.query(pay_models.Escrow).filter(pay_models.Escrow.id == escrow["id"]).first()
    e.due_release_at = pay_models.utcnow().replace(year=2020)
    db.commit(); db.close()
    r = client.post("/payments/escrow/auto-release", headers=ADMIN)
    assert r.json()["released"] == 1
    assert client.get(f"/payments/escrow/{escrow['id']}", headers=_headers(biz)).json()["status"] == "released"


def test_dispute_freezes_then_admin_refunds(client):
    biz, inf, cid = _signed_contract(client, amount=20000)
    escrow = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).json()
    eid = escrow["id"]
    r = client.post(f"/payments/escrow/{eid}/dispute", headers=_headers(inf))
    assert r.json()["status"] == "disputed"
    # A disputed escrow cannot be released by the business directly.
    assert client.post(f"/payments/escrow/{eid}/release", headers=_headers(biz)).status_code == 400
    r = client.post(f"/payments/escrow/{eid}/resolve", json={"decision": "refund"}, headers=ADMIN)
    assert r.json()["status"] == "refunded"
    assert pay_service.payment_provider.payouts[-1]["amount"] == 20000
    # Admin decision is logged.
    from app.modules.admin.models import AdminActionLog
    db = client.session_factory()
    log = db.query(AdminActionLog).filter(AdminActionLog.target_id == eid).first()
    db.close()
    assert log is not None and log.action == "dispute_refund"


def test_admin_can_resolve_dispute_by_releasing(client):
    biz, inf, cid = _signed_contract(client, amount=10000)
    escrow = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).json()
    eid = escrow["id"]
    client.post(f"/payments/escrow/{eid}/dispute", headers=_headers(biz))
    r = client.post(f"/payments/escrow/{eid}/resolve", json={"decision": "release"}, headers=ADMIN)
    assert r.json()["status"] == "released"
    assert r.json()["commission_amount"] == 1500


def test_resolve_requires_admin_header(client):
    biz, inf, cid = _signed_contract(client)
    escrow = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).json()
    client.post(f"/payments/escrow/{escrow['id']}/dispute", headers=_headers(biz))
    assert client.post(f"/payments/escrow/{escrow['id']}/resolve", json={"decision": "release"}).status_code == 401


def test_fund_requires_auth(client):
    biz, inf, cid = _signed_contract(client)
    assert client.post("/payments/escrow/fund", json={"contract_id": cid}).status_code == 401


def test_escrow_by_contract_lookup(client):
    biz, inf, cid = _signed_contract(client)
    escrow = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).json()
    found = client.get(f"/payments/escrow/by-contract/{cid}", headers=_headers(biz))
    assert found.status_code == 200
    assert found.json()["id"] == escrow["id"]
    # The influencer, a party, can also find it.
    assert client.get(f"/payments/escrow/by-contract/{cid}", headers=_headers(inf)).status_code == 200


def test_escrow_by_contract_404_when_unfunded(client):
    biz, inf, cid = _signed_contract(client)
    assert client.get(f"/payments/escrow/by-contract/{cid}", headers=_headers(biz)).status_code == 404

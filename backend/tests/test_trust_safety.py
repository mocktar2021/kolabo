"""Tests for Epic H (KOL-8): reviews (KOL-31) and reports (KOL-32)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.payments import models as pay_models
from app.modules.trust_safety.router import router as ts_router


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

    app = FastAPI()
    app.include_router(ts_router, prefix="/trust-safety")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


ADMIN = {"X-Admin-Id": "admin-1"}


def _released_escrow(client, status=pay_models.RELEASED):
    """Create a business, an influencer, and an escrow in the given status."""
    db = client.session_factory()
    try:
        biz = User(phone="+22990000001", password_hash="x", country_code="BJ", role="business", is_verified=True)
        inf = User(phone="+22990000002", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add_all([biz, inf]); db.commit(); db.refresh(biz); db.refresh(inf)
        e = pay_models.Escrow(
            contract_id="c-1", campaign_id="camp-1", business_user_id=biz.id, influencer_user_id=inf.id,
            amount=10000, currency="XOF", provider="mock", provider_fund_ref="f-1", status=status,
            held_at=pay_models.utcnow(), due_release_at=pay_models.utcnow(),
        )
        db.add(e); db.commit(); db.refresh(e)
        return biz.id, inf.id, e.id
    finally:
        db.close()


# ---- Reviews (KOL-31) ----

def test_cannot_review_before_escrow_released(client):
    biz, inf, eid = _released_escrow(client, status=pay_models.HELD)
    r = client.post("/trust-safety/reviews", json={"escrow_id": eid, "stars": 5}, headers=_headers(biz))
    assert r.status_code == 400


def test_non_party_cannot_review(client):
    biz, inf, eid = _released_escrow(client)
    r = client.post("/trust-safety/reviews", json={"escrow_id": eid, "stars": 5}, headers=_headers("stranger"))
    assert r.status_code == 403


def test_first_review_is_hidden_until_both_submit(client):
    biz, inf, eid = _released_escrow(client)
    r = client.post("/trust-safety/reviews", json={"escrow_id": eid, "stars": 5, "comment": "great"}, headers=_headers(biz))
    assert r.status_code == 201
    assert r.json()["revealed"] is False
    # The influencer's public reviews are still empty (double blind).
    assert client.get(f"/trust-safety/users/{inf}/reviews").json()["count"] == 0


def test_double_blind_reveal_when_both_submit(client):
    biz, inf, eid = _released_escrow(client)
    client.post("/trust-safety/reviews", json={"escrow_id": eid, "stars": 4}, headers=_headers(biz))
    r = client.post("/trust-safety/reviews", json={"escrow_id": eid, "stars": 5}, headers=_headers(inf))
    assert r.json()["revealed"] is True
    # Now both sides' public reputation is visible.
    inf_rep = client.get(f"/trust-safety/users/{inf}/reviews").json()
    biz_rep = client.get(f"/trust-safety/users/{biz}/reviews").json()
    assert inf_rep["count"] == 1 and inf_rep["average_stars"] == 4.0
    assert biz_rep["count"] == 1 and biz_rep["average_stars"] == 5.0


def test_cannot_review_twice(client):
    biz, inf, eid = _released_escrow(client)
    assert client.post("/trust-safety/reviews", json={"escrow_id": eid, "stars": 5}, headers=_headers(biz)).status_code == 201
    assert client.post("/trust-safety/reviews", json={"escrow_id": eid, "stars": 3}, headers=_headers(biz)).status_code == 409


def test_stars_out_of_range_rejected(client):
    biz, inf, eid = _released_escrow(client)
    assert client.post("/trust-safety/reviews", json={"escrow_id": eid, "stars": 0}, headers=_headers(biz)).status_code == 422
    assert client.post("/trust-safety/reviews", json={"escrow_id": eid, "stars": 6}, headers=_headers(biz)).status_code == 422


def test_review_requires_auth(client):
    biz, inf, eid = _released_escrow(client)
    assert client.post("/trust-safety/reviews", json={"escrow_id": eid, "stars": 5}).status_code == 401


# ---- Reports (KOL-32) ----

def test_report_creates_open_case(client):
    r = client.post(
        "/trust-safety/reports",
        json={"target_type": "user", "target_id": "u-9", "reason_code": "fake_followers", "details": "bought"},
        headers=_headers("reporter-1"),
    )
    assert r.status_code == 201
    assert r.json()["status"] == "open"
    assert r.json()["reason_code"] == "fake_followers"


def test_report_rejects_unknown_reason(client):
    r = client.post(
        "/trust-safety/reports",
        json={"target_type": "user", "target_id": "u-9", "reason_code": "banana"},
        headers=_headers("reporter-1"),
    )
    assert r.status_code == 400


def test_report_appears_in_admin_queue_and_resolves(client):
    rid = client.post(
        "/trust-safety/reports",
        json={"target_type": "campaign", "target_id": "camp-1", "reason_code": "fraud"},
        headers=_headers("reporter-1"),
    ).json()["id"]
    queue = client.get("/trust-safety/reports", headers=ADMIN).json()
    assert any(item["id"] == rid for item in queue)
    r = client.post(f"/trust-safety/reports/{rid}/resolve", json={"decision": "reviewed"}, headers=ADMIN)
    assert r.json()["status"] == "reviewed"
    # Resolving again fails; case is closed.
    assert client.post(f"/trust-safety/reports/{rid}/resolve", json={"decision": "dismissed"}, headers=ADMIN).status_code == 400
    # Admin decision is logged.
    from app.modules.admin.models import AdminActionLog
    db = client.session_factory()
    log = db.query(AdminActionLog).filter(AdminActionLog.target_id == rid).first()
    db.close()
    assert log is not None and log.action == "report_reviewed"


def test_admin_queue_requires_admin_header(client):
    assert client.get("/trust-safety/reports").status_code == 401


def test_report_requires_auth(client):
    assert client.post(
        "/trust-safety/reports",
        json={"target_type": "user", "target_id": "u-9", "reason_code": "spam"},
    ).status_code == 401

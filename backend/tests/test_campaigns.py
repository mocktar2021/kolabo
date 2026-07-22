"""Tests for Epic D (KOL-11): campaigns, invitations, proposals."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.campaigns.router import router as campaigns_router


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
    app.include_router(campaigns_router, prefix="/campaigns")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = testing_session
    return c


def _user(client, phone, role, verified=True):
    db = client.session_factory()
    try:
        u = User(phone=phone, password_hash="x", country_code="BJ", role=role, is_verified=verified)
        db.add(u); db.commit(); db.refresh(u)
        return u.id, {"Authorization": f"Bearer {create_access_token(u.id)}"}
    finally:
        db.close()


def _published_campaign(client, headers):
    return client.post("/campaigns/", json={
        "title": "Launch push",
        "budget_amount": 50000,
        "budget_currency": "XOF",
        "deliverables": [{"platform": "instagram", "type": "post", "quantity": 2}],
        "deadline": "2026-09-01",
        "publish": True,
    }, headers=headers)


def test_draft_save_allows_missing_fields(client):
    _, headers = _user(client, "+22990000001", "business")
    r = client.post("/campaigns/", json={"title": "Idea only"}, headers=headers)
    assert r.status_code == 201
    assert r.json()["status"] == "draft"


def test_publish_requires_budget_deliverables_deadline(client):
    _, headers = _user(client, "+22990000002", "business")
    r = client.post("/campaigns/", json={"title": "Incomplete", "publish": True}, headers=headers)
    assert r.status_code == 400


def test_create_published_with_all_fields(client):
    _, headers = _user(client, "+22990000003", "business")
    r = _published_campaign(client, headers)
    assert r.status_code == 201
    assert r.json()["status"] == "published"


def test_invite_verified_influencer_notifies(client):
    _, biz = _user(client, "+22990000004", "business")
    inf_id, _ = _user(client, "+22990000005", "influencer", verified=True)
    camp = _published_campaign(client, biz).json()
    r = client.post(f"/campaigns/{camp['id']}/invitations", json={"influencer_id": inf_id}, headers=biz)
    assert r.status_code == 201
    from app.modules.notifications.models import Notification
    db = client.session_factory()
    note = db.query(Notification).filter(Notification.user_id == inf_id).first()
    db.close()
    assert note is not None and note.type == "campaign_invitation"


def test_invite_unverified_influencer_blocked(client):
    _, biz = _user(client, "+22990000006", "business")
    inf_id, _ = _user(client, "+22990000007", "influencer", verified=False)
    camp = _published_campaign(client, biz).json()
    r = client.post(f"/campaigns/{camp['id']}/invitations", json={"influencer_id": inf_id}, headers=biz)
    assert r.status_code == 400


def test_invite_requires_ownership(client):
    _, biz = _user(client, "+22990000008", "business")
    _, other = _user(client, "+22990000009", "business")
    inf_id, _ = _user(client, "+22990000010", "influencer")
    camp = _published_campaign(client, biz).json()
    r = client.post(f"/campaigns/{camp['id']}/invitations", json={"influencer_id": inf_id}, headers=other)
    assert r.status_code == 403


def test_proposal_versions_and_supersede(client):
    _, biz = _user(client, "+22990000011", "business")
    inf_id, inf = _user(client, "+22990000012", "influencer")
    camp = _published_campaign(client, biz).json()
    r1 = client.post(f"/campaigns/{camp['id']}/proposals", json={"rate_amount": 10000, "rate_currency": "xof", "timeline_days": 7}, headers=inf)
    assert r1.status_code == 201
    assert r1.json()["version"] == 1
    assert r1.json()["rate_currency"] == "XOF"
    r2 = client.post(f"/campaigns/{camp['id']}/proposals", json={"rate_amount": 12000, "rate_currency": "XOF", "timeline_days": 10}, headers=inf)
    assert r2.json()["version"] == 2
    from app.modules.notifications.models import Notification
    from app.modules.campaigns.models import Proposal
    db = client.session_factory()
    notes = db.query(Notification).filter(Notification.type == "proposal_submitted").all()
    v1 = db.query(Proposal).filter(Proposal.version == 1).first()
    db.close()
    assert len(notes) == 2
    assert v1.status == "superseded"


def test_endpoints_require_auth(client):
    r = client.post("/campaigns/", json={"title": "x"})
    assert r.status_code == 401

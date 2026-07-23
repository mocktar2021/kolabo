"""Tests for Epic F (KOL-26): campaign-scoped messaging."""
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
from app.modules.messaging.router import router as messaging_router


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
    app.include_router(messaging_router, prefix="/messaging")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _setup(client, invited=True, proposed=False):
    db = client.session_factory()
    try:
        biz = User(phone="+22990000001", password_hash="x", country_code="BJ", role="business", is_verified=True)
        inf = User(phone="+22990000002", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add_all([biz, inf]); db.commit(); db.refresh(biz); db.refresh(inf)
        camp = campaigns.Campaign(business_user_id=biz.id, title="Launch", budget_amount=1000, budget_currency="XOF",
                                  deliverables=[{"platform": "instagram", "type": "post", "quantity": 1}], status=campaigns.PUBLISHED)
        db.add(camp); db.commit(); db.refresh(camp)
        if invited:
            db.add(campaigns.CampaignInvitation(campaign_id=camp.id, influencer_user_id=inf.id, status=campaigns.INVITED))
        if proposed:
            db.add(campaigns.Proposal(campaign_id=camp.id, influencer_user_id=inf.id, version=1, rate_amount=100, rate_currency="XOF", timeline_days=5, status=campaigns.SUBMITTED))
        db.commit()
        return biz.id, inf.id, camp.id
    finally:
        db.close()


def test_message_allowed_when_invited(client):
    biz, inf, camp = _setup(client, invited=True)
    r = client.post(f"/messaging/campaigns/{camp}/messages", json={"to_user_id": inf, "body": "Hi, keen to work with you"}, headers=_headers(biz))
    assert r.status_code == 201
    assert r.json()["sender_user_id"] == biz


def test_message_allowed_when_proposal_exists(client):
    biz, inf, camp = _setup(client, invited=False, proposed=True)
    r = client.post(f"/messaging/campaigns/{camp}/messages", json={"to_user_id": biz, "body": "Thanks for the brief"}, headers=_headers(inf))
    assert r.status_code == 201


def test_message_locked_without_relationship(client):
    biz, inf, camp = _setup(client, invited=False, proposed=False)
    r = client.post(f"/messaging/campaigns/{camp}/messages", json={"to_user_id": inf, "body": "Hello"}, headers=_headers(biz))
    assert r.status_code == 403


def test_message_must_involve_campaign_owner(client):
    biz, inf, camp = _setup(client, invited=True)
    db = client.session_factory()
    outsider = User(phone="+22990000003", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
    db.add(outsider); db.commit(); db.refresh(outsider)
    oid = outsider.id
    db.close()
    r = client.post(f"/messaging/campaigns/{camp}/messages", json={"to_user_id": oid, "body": "Hey"}, headers=_headers(inf))
    assert r.status_code == 403


def test_thread_returns_conversation(client):
    biz, inf, camp = _setup(client, invited=True)
    client.post(f"/messaging/campaigns/{camp}/messages", json={"to_user_id": inf, "body": "one"}, headers=_headers(biz))
    client.post(f"/messaging/campaigns/{camp}/messages", json={"to_user_id": biz, "body": "two"}, headers=_headers(inf))
    thread = client.get(f"/messaging/campaigns/{camp}/messages", params={"with_user_id": inf}, headers=_headers(biz)).json()
    assert [m["body"] for m in thread] == ["one", "two"]


def test_message_requires_auth(client):
    biz, inf, camp = _setup(client, invited=True)
    assert client.post(f"/messaging/campaigns/{camp}/messages", json={"to_user_id": inf, "body": "x"}).status_code == 401

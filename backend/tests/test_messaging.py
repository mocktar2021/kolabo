"""Tests for Epic F (KOL-26): campaign-scoped messaging.

The gate — a thread opens only once a contract does — has a file of its own
(test_messaging_gate.py). What is left here is the mechanics: a message goes
from one party to the other, the thread reads back in order, auth is required.

Every setup therefore writes a contract. It used to write an invitation or a
proposal, because an invitation or a proposal was what unlocked messaging;
that rule is gone, so the fixtures that relied on it had to move with it.
"""
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
from app.modules.contracts import models as contracts
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


def _setup(client, contract=True):
    """A brand, a creator, a campaign, and (by default) the contract on it."""
    db = client.session_factory()
    try:
        biz = User(phone="+22990000001", password_hash="x", country_code="BJ", role="business", is_verified=True)
        inf = User(phone="+22990000002", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add_all([biz, inf]); db.commit(); db.refresh(biz); db.refresh(inf)
        camp = campaigns.Campaign(business_user_id=biz.id, title="Launch", budget_amount=1000, budget_currency="XOF",
                                  deliverables=[{"platform": "instagram", "type": "post", "quantity": 1}], status=campaigns.PUBLISHED)
        db.add(camp); db.commit(); db.refresh(camp)
        db.add(campaigns.CampaignInvitation(campaign_id=camp.id, influencer_user_id=inf.id, status=campaigns.INVITED))
        proposal = campaigns.Proposal(campaign_id=camp.id, influencer_user_id=inf.id, version=1, rate_amount=100,
                                      rate_currency="XOF", timeline_days=5, status=campaigns.SUBMITTED)
        db.add(proposal); db.commit(); db.refresh(proposal)
        if contract:
            db.add(contracts.Contract(
                campaign_id=camp.id, proposal_id=proposal.id, business_user_id=biz.id,
                influencer_user_id=inf.id, language="fr", body="placeholder", rate_amount=100,
                rate_currency="XOF", timeline_days=5, deliverables=[], status=contracts.PENDING,
            ))
        db.commit()
        return biz.id, inf.id, camp.id
    finally:
        db.close()


def test_message_allowed_when_a_contract_exists(client):
    biz, inf, camp = _setup(client)
    r = client.post(f"/messaging/campaigns/{camp}/messages", json={"to_user_id": inf, "body": "Shot list attached"}, headers=_headers(biz))
    assert r.status_code == 201
    assert r.json()["sender_user_id"] == biz
    # Nobody has opened it yet.
    assert r.json()["read_at"] is None


def test_the_creator_can_write_back(client):
    biz, inf, camp = _setup(client)
    r = client.post(f"/messaging/campaigns/{camp}/messages", json={"to_user_id": biz, "body": "Filming Thursday"}, headers=_headers(inf))
    assert r.status_code == 201


def test_message_locked_without_a_contract(client):
    """An invitation and a proposal are both on this campaign, and neither
    opens a thread any more: before a contract a message is a cold lead."""
    biz, inf, camp = _setup(client, contract=False)
    r = client.post(f"/messaging/campaigns/{camp}/messages", json={"to_user_id": inf, "body": "Hello"}, headers=_headers(biz))
    assert r.status_code == 403


def test_message_must_be_to_the_other_party_of_the_contract(client):
    biz, inf, camp = _setup(client)
    db = client.session_factory()
    outsider = User(phone="+22990000003", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
    db.add(outsider); db.commit(); db.refresh(outsider)
    oid = outsider.id
    db.close()
    r = client.post(f"/messaging/campaigns/{camp}/messages", json={"to_user_id": oid, "body": "Hey"}, headers=_headers(inf))
    assert r.status_code == 403


def test_message_to_yourself_is_refused(client):
    biz, inf, camp = _setup(client)
    r = client.post(f"/messaging/campaigns/{camp}/messages", json={"to_user_id": biz, "body": "note to self"}, headers=_headers(biz))
    assert r.status_code == 400


def test_thread_returns_conversation(client):
    biz, inf, camp = _setup(client)
    client.post(f"/messaging/campaigns/{camp}/messages", json={"to_user_id": inf, "body": "one"}, headers=_headers(biz))
    client.post(f"/messaging/campaigns/{camp}/messages", json={"to_user_id": biz, "body": "two"}, headers=_headers(inf))
    thread = client.get(f"/messaging/campaigns/{camp}/messages", params={"with_user_id": inf}, headers=_headers(biz)).json()
    assert [m["body"] for m in thread] == ["one", "two"]


def test_unknown_campaign_is_404(client):
    biz, inf, camp = _setup(client)
    r = client.post("/messaging/campaigns/nope/messages", json={"to_user_id": inf, "body": "x"}, headers=_headers(biz))
    assert r.status_code == 404


def test_message_requires_auth(client):
    biz, inf, camp = _setup(client)
    assert client.post(f"/messaging/campaigns/{camp}/messages", json={"to_user_id": inf, "body": "x"}).status_code == 401
    assert client.get("/messaging/threads").status_code == 401

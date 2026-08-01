"""Direct orders: a brand buys a creator's package at the published price.

The order is a hidden, single-creator campaign carrying one invitation and one
business-authored proposal, so the rest of the platform (contracts, escrow,
reviews) needs no second code path. These tests pin that shape down, plus the
rules about who may place an order and who may see one.
"""
from datetime import datetime, timedelta

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
from app.modules.campaigns import service as campaigns_service
from app.modules.campaigns.router import router as campaigns_router
from app.modules.contracts.router import router as contracts_router
from app.modules.notifications.models import Notification
from app.modules.profiles.models import Package


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(campaigns_router, prefix="/campaigns")
    # Mounted from the start: accepting an order goes through the existing
    # contracts path, and the tests for that live in this same file.
    app.include_router(contracts_router, prefix="/contracts")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _setup(client, price=25000, currency="XOF", active=True, quantity=2):
    """A brand, a creator, and one package on the creator's profile."""
    db = client.session_factory()
    try:
        biz = User(phone="+22990000001", password_hash="x", country_code="BJ", role="business", is_verified=True)
        creator = User(phone="+22990000002", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add_all([biz, creator]); db.commit(); db.refresh(biz); db.refresh(creator)
        pkg = Package(
            user_id=creator.id,
            platform="instagram",
            deliverable_type="reel",
            title="Two reels, shot and edited",
            price_amount=price,
            currency=currency,
            quantity=quantity,
            is_active=active,
        )
        db.add(pkg); db.commit(); db.refresh(pkg)
        return biz.id, creator.id, pkg.id
    finally:
        db.close()


def _order(client, buyer, package_id, note=None):
    body = {"package_id": package_id}
    if note is not None:
        body["note"] = note
    return client.post("/campaigns/orders", json=body, headers=_headers(buyer))


def _rows(client, model, **filters):
    db = client.session_factory()
    try:
        query = db.query(model)
        for field, value in filters.items():
            query = query.filter(getattr(model, field) == value)
        return query.all()
    finally:
        db.close()


def test_order_creates_campaign_invitation_and_proposal_from_package_terms(client):
    biz, creator, pkg = _setup(client, price=25000, currency="XOF", quantity=2)
    r = _order(client, biz, pkg, note="For the December launch")
    assert r.status_code == 201
    body = r.json()

    campaign = _rows(client, campaigns.Campaign, id=body["campaign_id"])[0]
    assert campaign.is_direct is True
    assert campaign.status == campaigns.PUBLISHED
    assert campaign.title == "Two reels, shot and edited"
    assert campaign.budget_amount == 25000
    assert campaign.budget_currency == "XOF"
    assert campaign.deadline is None
    assert campaign.deliverables == [{"platform": "instagram", "type": "reel", "quantity": 2}]

    invitations = _rows(client, campaigns.CampaignInvitation, campaign_id=campaign.id)
    assert len(invitations) == 1
    assert invitations[0].influencer_user_id == creator
    assert invitations[0].status == campaigns.INVITED

    proposal = _rows(client, campaigns.Proposal, id=body["proposal_id"])[0]
    assert proposal.version == 1
    # The BUSINESS is proposing here: the buyer picked a published price and
    # offered it back, which is what makes the creator's reply an answer.
    assert proposal.author_role == campaigns.AUTHOR_BUSINESS
    assert proposal.rate_amount == 25000
    assert proposal.rate_currency == "XOF"
    assert proposal.timeline_days == campaigns_service.DEFAULT_ORDER_TIMELINE_DAYS
    assert proposal.status == campaigns.SUBMITTED
    assert proposal.note == "For the December launch"


def test_order_expires_in_48_hours_and_notifies_the_creator(client):
    biz, creator, pkg = _setup(client)
    body = _order(client, biz, pkg).json()

    expected = campaigns.utcnow() + timedelta(hours=campaigns_service.ORDER_ACCEPT_WINDOW_HOURS)
    expires_at = datetime.fromisoformat(body["expires_at"])
    assert abs((expires_at - expected).total_seconds()) < 60

    kinds = [n.type for n in _rows(client, Notification, user_id=creator)]
    assert "direct_order" in kinds


def test_cannot_order_your_own_package(client):
    biz, creator, pkg = _setup(client)
    r = _order(client, creator, pkg)
    assert r.status_code == 400
    assert r.json()["detail"] == "You cannot order your own package."


def test_an_influencer_cannot_order_someone_elses_package(client):
    biz, creator, pkg = _setup(client)
    db = client.session_factory()
    other = User(phone="+22990000003", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
    db.add(other); db.commit(); db.refresh(other)
    other_id = other.id
    db.close()
    # Same rule as authoring a brief: buying is the brand side of the market.
    assert _order(client, other_id, pkg).status_code == 403


def test_an_inactive_package_cannot_be_ordered(client):
    biz, creator, pkg = _setup(client, active=False)
    r = _order(client, biz, pkg)
    assert r.status_code == 400
    assert "not available" in r.json()["detail"]


def test_unknown_package_is_404(client):
    biz, creator, pkg = _setup(client)
    assert _order(client, biz, "no-such-package").status_code == 404


def test_ordering_requires_auth(client):
    biz, creator, pkg = _setup(client)
    assert client.post("/campaigns/orders", json={"package_id": pkg}).status_code == 401


def test_a_direct_order_is_hidden_from_outsiders_but_visible_to_both_parties(client):
    """A direct order is a private transaction, not a brief anyone can bid on.

    There is no public campaign board today — every campaign listing is scoped
    to a participant — so "hidden" is tested as: a third party finds it
    nowhere, while the buyer and the invited creator each find it on their own
    surface.
    """
    biz, creator, pkg = _setup(client)
    body = _order(client, biz, pkg).json()
    campaign_id = body["campaign_id"]

    mine = client.get("/campaigns/mine", headers=_headers(biz)).json()
    assert [c["id"] for c in mine] == [campaign_id]
    assert mine[0]["is_direct"] is True

    invitations = client.get("/campaigns/invitations/mine", headers=_headers(creator)).json()
    assert [i["campaign_id"] for i in invitations] == [campaign_id]
    assert invitations[0]["campaign"]["is_direct"] is True

    # A stranger sees it on no listing and cannot open it.
    assert client.get("/campaigns/mine", headers=_headers("stranger")).json() == []
    assert client.get("/campaigns/invitations/mine", headers=_headers("stranger")).json() == []
    assert client.get(f"/campaigns/{campaign_id}", headers=_headers("stranger")).status_code == 403
    # Nor can the creator, who reaches it through their invitation instead:
    # campaign detail has always been the owner's view.
    assert client.get(f"/campaigns/{campaign_id}", headers=_headers(creator)).status_code == 403


def test_a_brief_is_not_marked_direct_and_its_proposals_never_expire(client):
    """The normal brief flow is untouched by any of this."""
    biz, creator, pkg = _setup(client)
    created = client.post(
        "/campaigns/",
        json={
            "title": "Ramadan push",
            "budget_amount": 500000,
            "budget_currency": "XOF",
            "deliverables": [{"platform": "instagram", "type": "post", "quantity": 3}],
            "deadline": "2026-12-01",
            "publish": True,
        },
        headers=_headers(biz),
    )
    assert created.status_code == 201
    assert created.json()["is_direct"] is False

    proposal = client.post(
        f"/campaigns/{created.json()['id']}/proposals",
        json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 5},
        headers=_headers(creator),
    )
    assert proposal.status_code == 201
    assert proposal.json()["expires_at"] is None

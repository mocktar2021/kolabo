"""Negotiated orders: a brand offering its own terms instead of a package.

The claim under test is that the terms are the ONLY thing that differs. A
negotiated order produces the same hidden campaign, the same invitation and
the same business-authored proposal v1 on the same 48 hour clock, and is
answered through the same endpoints — so nothing downstream (contracts,
escrow, disputes) has a second case to handle.

The other half is the validation a package no longer supplies: a package's
terms were checked when it was published, and typed-in terms have to be
checked here or "negotiate" becomes the way around the price floor.

A separate file from test_orders.py, which is already long and is about the
package form.
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
from app.modules.campaigns import negotiated
from app.modules.campaigns import service as campaigns_service
from app.modules.campaigns.router import router as campaigns_router
from app.modules.contracts import models as contracts
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
    # Accepting goes through the existing contracts path, which is most of the
    # point: the negotiated order has to arrive there indistinguishable.
    app.include_router(contracts_router, prefix="/contracts")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _parties(client):
    """A brand and a creator. No package: that is the whole point here."""
    db = client.session_factory()
    try:
        biz = User(phone="+22990010001", password_hash="x", country_code="BJ", role="business", is_verified=True)
        creator = User(phone="+22990010002", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add_all([biz, creator]); db.commit(); db.refresh(biz); db.refresh(creator)
        return biz.id, creator.id
    finally:
        db.close()


def _package(client, creator_id):
    db = client.session_factory()
    try:
        pkg = Package(
            user_id=creator_id, platform="instagram", deliverable_type="reel",
            title="Two reels", price_amount=25000, currency="XOF", quantity=2, is_active=True,
        )
        db.add(pkg); db.commit(); db.refresh(pkg)
        return pkg.id
    finally:
        db.close()


def _offer(client, buyer, creator, **overrides):
    body = {
        "creator_user_id": creator,
        "platform": "instagram",
        "deliverable_type": "reel",
        "quantity": 2,
        "rate_amount": 60000,
        "currency": "XOF",
        "timeline_days": 10,
    }
    body.update(overrides)
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


# --------------------------------------------------------------------------
# The offer produces an ordinary order
# --------------------------------------------------------------------------


def test_a_custom_offer_builds_exactly_what_a_package_order_builds(client):
    biz, creator = _parties(client)
    r = _offer(client, biz, creator, note="Same shoot as last time")
    assert r.status_code == 201
    body = r.json()

    campaign = _rows(client, campaigns.Campaign, id=body["campaign_id"])[0]
    assert campaign.is_direct is True
    assert campaign.status == campaigns.PUBLISHED
    # Derived from the terms, because there is no package title to borrow.
    assert campaign.title == "2 × Reel — Instagram"
    assert campaign.budget_amount == 60000
    assert campaign.budget_currency == "XOF"
    assert campaign.deadline is None
    assert campaign.deliverables == [{"platform": "instagram", "type": "reel", "quantity": 2}]

    invitations = _rows(client, campaigns.CampaignInvitation, campaign_id=campaign.id)
    assert len(invitations) == 1
    assert invitations[0].influencer_user_id == creator
    assert invitations[0].status == campaigns.INVITED

    proposal = _rows(client, campaigns.Proposal, id=body["proposal_id"])[0]
    assert proposal.version == 1
    # The BUSINESS is proposing: it named the terms, which is what makes the
    # creator's reply an answer rather than a second offer.
    assert proposal.author_role == campaigns.AUTHOR_BUSINESS
    assert proposal.rate_amount == 60000
    assert proposal.rate_currency == "XOF"
    assert proposal.timeline_days == 10
    assert proposal.status == campaigns.SUBMITTED
    assert proposal.note == "Same shoot as last time"

    # Same 48 hour window as a package order, from the same constant.
    expected = campaigns.utcnow() + timedelta(hours=campaigns_service.ORDER_ACCEPT_WINDOW_HOURS)
    assert abs((datetime.fromisoformat(body["expires_at"]) - expected).total_seconds()) < 60
    assert "direct_order" in [n.type for n in _rows(client, Notification, user_id=creator)]


def test_a_negotiated_order_is_accepted_through_the_same_path(client):
    """Nothing downstream knows the difference: one accept, one contract."""
    biz, creator = _parties(client)
    order = _offer(client, biz, creator).json()

    r = client.post(f"/campaigns/orders/{order['proposal_id']}/accept", headers=_headers(creator))
    assert r.status_code == 201
    contract = r.json()
    assert contract["campaign_id"] == order["campaign_id"]
    assert contract["rate_amount"] == 60000
    assert contract["timeline_days"] == 10
    assert contract["status"] == contracts.PENDING
    assert _rows(client, campaigns.Proposal, id=order["proposal_id"])[0].status == campaigns.PROPOSAL_ACCEPTED


# --------------------------------------------------------------------------
# Terms nobody validated before
# --------------------------------------------------------------------------


def test_a_deliverable_that_does_not_exist_on_that_platform_is_rejected(client):
    biz, creator = _parties(client)
    r = _offer(client, biz, creator, platform="tiktok", deliverable_type="carousel")
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "carousel is not available on tiktok" in detail
    # The message carries the fix, same as everywhere else in the codebase.
    assert "video" in detail


def test_an_unsupported_platform_is_rejected(client):
    biz, creator = _parties(client)
    r = _offer(client, biz, creator, platform="myspace", deliverable_type="post")
    assert r.status_code == 400
    assert "myspace is not a supported platform" in r.json()["detail"]


def test_a_rate_below_the_currency_floor_is_rejected(client):
    """A negotiated price cannot undercut the floor either — that is what a
    floor is for. Same message the packages module raises."""
    biz, creator = _parties(client)
    r = _offer(client, biz, creator, rate_amount=1000)
    assert r.status_code == 400
    assert r.json()["detail"] == "Minimum price for XOF is 5000."
    assert _rows(client, campaigns.Campaign) == []


def test_the_floor_is_applied_to_the_uppercased_currency(client):
    """"xof" is XOF. Lowercasing the currency must not lowercase the rule."""
    biz, creator = _parties(client)
    r = _offer(client, biz, creator, currency="xof", rate_amount=1000)
    assert r.status_code == 400
    assert r.json()["detail"] == "Minimum price for XOF is 5000."


def test_an_out_of_range_quantity_is_rejected(client):
    biz, creator = _parties(client)
    for quantity in (0, negotiated.MAX_OFFER_QUANTITY + 1):
        r = _offer(client, biz, creator, quantity=quantity)
        assert r.status_code == 400
        assert "quantity" in r.json()["detail"].lower()


def test_an_out_of_range_timeline_is_rejected(client):
    biz, creator = _parties(client)
    for days in (0, negotiated.MAX_OFFER_TIMELINE_DAYS + 1):
        r = _offer(client, biz, creator, timeline_days=days)
        assert r.status_code == 400
        assert "Timeline" in r.json()["detail"]


def test_the_target_must_exist_and_must_be_a_creator(client):
    biz, creator = _parties(client)
    assert _offer(client, biz, "nobody").status_code == 404

    db = client.session_factory()
    other_brand = User(phone="+22990010003", password_hash="x", country_code="BJ", role="business", is_verified=True)
    db.add(other_brand); db.commit(); db.refresh(other_brand)
    other_brand_id = other_brand.id
    db.close()

    r = _offer(client, biz, other_brand_id)
    assert r.status_code == 400
    assert r.json()["detail"] == "You can only send an offer to a creator."


def test_a_brand_cannot_offer_to_itself_and_a_creator_cannot_buy(client):
    biz, creator = _parties(client)
    r = _offer(client, biz, biz)
    assert r.status_code == 400
    assert r.json()["detail"] == "You cannot send an offer to yourself."
    # Same rule as authoring a brief or ordering a package: buying is the
    # brand side of the market.
    assert _offer(client, creator, creator).status_code == 400
    assert _rows(client, campaigns.Campaign) == []


# --------------------------------------------------------------------------
# One form per request
# --------------------------------------------------------------------------


def test_a_package_and_custom_terms_together_are_rejected(client):
    """Two orders in one envelope. Guessing which was meant is how somebody
    gets charged for the wrong thing."""
    biz, creator = _parties(client)
    pkg = _package(client, creator)
    r = _offer(client, biz, creator, package_id=pkg)
    assert r.status_code == 400
    assert "not both" in r.json()["detail"]
    assert _rows(client, campaigns.Campaign) == []


def test_an_order_with_neither_form_is_rejected(client):
    biz, creator = _parties(client)
    r = client.post("/campaigns/orders", json={"note": "hello"}, headers=_headers(biz))
    assert r.status_code == 400
    assert "package_id" in r.json()["detail"]


def test_a_half_filled_custom_offer_is_rejected_naming_what_is_missing(client):
    """There is no sensible default for a rate or a deliverable: an order with
    a blank in it is an order the creator cannot answer."""
    biz, creator = _parties(client)
    r = client.post(
        "/campaigns/orders",
        json={"creator_user_id": creator, "platform": "instagram", "deliverable_type": "reel"},
        headers=_headers(biz),
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "rate_amount" in detail and "currency" in detail and "timeline_days" in detail


# --------------------------------------------------------------------------
# Answering: the creator counters through the existing chain
# --------------------------------------------------------------------------


def test_the_creator_counters_a_negotiated_order_and_the_clock_is_preserved(client, admin_headers):
    """There is no creator-side counter endpoint by design — reply is
    business-only, and the creator's counter is simply the next version in the
    chain. It has to stay on the order's clock: an order that quietly stops
    expiring is an order the buyer waits on forever, and the expiry sweep only
    ever touches rows that have an expires_at.
    """
    biz, creator = _parties(client)
    order = _offer(client, biz, creator).json()
    original_expiry = _rows(client, campaigns.Proposal, id=order["proposal_id"])[0].expires_at

    r = client.post(
        f"/campaigns/{order['campaign_id']}/proposals",
        json={"rate_amount": 75000, "rate_currency": "XOF", "timeline_days": 14, "note": "14 days is realistic"},
        headers=_headers(creator),
    )
    assert r.status_code == 201
    counter = r.json()
    assert counter["version"] == 2
    assert counter["author_role"] == campaigns.AUTHOR_INFLUENCER
    assert counter["expires_at"] is not None
    assert abs((datetime.fromisoformat(counter["expires_at"]) - original_expiry).total_seconds()) < 1
    # The buyer's offer is no longer the live one.
    assert _rows(client, campaigns.Proposal, id=order["proposal_id"])[0].status == campaigns.SUPERSEDED

    # And because the clock survived, the order can still lapse. Without the
    # carried-forward expiry this counter would have sat open forever.
    db = client.session_factory()
    p = db.query(campaigns.Proposal).filter(campaigns.Proposal.id == counter["id"]).first()
    p.expires_at = campaigns.utcnow() - timedelta(hours=1)
    db.commit(); db.close()
    assert client.post("/campaigns/orders/expire", headers=admin_headers).json() == {"expired": 1}


def test_the_business_can_counter_back_on_a_negotiated_order(client):
    """The existing reply path, unchanged: same chain, next version, and the
    same clock again."""
    biz, creator = _parties(client)
    order = _offer(client, biz, creator).json()
    client.post(
        f"/campaigns/{order['campaign_id']}/proposals",
        json={"rate_amount": 75000, "rate_currency": "XOF", "timeline_days": 14},
        headers=_headers(creator),
    )
    latest = sorted(
        _rows(client, campaigns.Proposal, campaign_id=order["campaign_id"]), key=lambda p: p.version
    )[-1]

    r = client.post(
        f"/campaigns/{order['campaign_id']}/proposals/{latest.id}/reply",
        json={"note": "Meet at 68k", "rate_amount": 68000},
        headers=_headers(biz),
    )
    assert r.status_code == 201
    reply = r.json()
    assert reply["version"] == 3
    assert reply["author_role"] == campaigns.AUTHOR_BUSINESS
    assert reply["rate_amount"] == 68000
    # Timeline was not countered, so it repeats the creator's — every row in a
    # chain is a complete offer.
    assert reply["timeline_days"] == 14
    assert reply["expires_at"] is not None


def test_a_brief_proposal_still_has_no_expiry(client):
    """The carried-forward clock must not leak into the brief flow: a brief's
    proposals do not expire, because leaving one open promises nothing."""
    biz, creator = _parties(client)
    brief = client.post(
        "/campaigns/",
        json={
            "title": "Ramadan push",
            "budget_amount": 500000,
            "budget_currency": "XOF",
            "deliverables": [{"platform": "instagram", "type": "post", "quantity": 3}],
            "deadline": "2026-12-01",
            "publish": True,
            "is_open": True,
        },
        headers=_headers(biz),
    ).json()

    first = client.post(
        f"/campaigns/{brief['id']}/proposals",
        json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 5},
        headers=_headers(creator),
    )
    assert first.json()["expires_at"] is None
    # Including a re-submission, which is the path that now copies an expiry.
    second = client.post(
        f"/campaigns/{brief['id']}/proposals",
        json={"rate_amount": 45000, "rate_currency": "XOF", "timeline_days": 5},
        headers=_headers(creator),
    )
    assert second.json()["version"] == 2
    assert second.json()["expires_at"] is None

"""Checking out a basket of packages from several creators.

The claim under test is that a checkout FANS OUT rather than bundling: one
direct order per creator, each an ordinary order that the rest of the platform
(accept, decline, contract, escrow, the expiry sweep) cannot tell apart from
one placed alone. Which is why the last test here is the important one — one
creator declining must leave the others exactly where they were.

The other half is that it is all or nothing. A brand that half-orders does not
know which half happened, so a single bad line has to leave the database
untouched.

A separate file from test_orders.py (the package form) and
test_orders_negotiated.py (typed-in terms), both of which are about a single
order.
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
from app.modules.campaigns import cart as cart_module
from app.modules.campaigns import models as campaigns
from app.modules.campaigns.router import router as campaigns_router
from app.modules.contracts.router import router as contracts_router
from app.modules.notifications.models import Notification
from app.modules.profiles.models import Package

# The party details both sides have to have stated before a contract can be
# generated. Shared with the three other suites that reach contract
# generation; tests/party_fixtures.py carries the argument.
from tests.party_fixtures import seed_party_details


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
    # A cart's orders are answered through the ordinary paths, which is most
    # of the point.
    app.include_router(contracts_router, prefix="/contracts")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _user(client, phone, role):
    db = client.session_factory()
    try:
        u = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x", country_code="BJ", role=role, is_verified=True)
        db.add(u); db.commit(); db.refresh(u)
        # Everybody gets the block their side of the market states, because
        # the last test here accepts one of the cart's orders and contract
        # generation refuses unless both sides have stated who they are
        # contracting as (contract_business_party_missing /
        # contract_creator_party_missing). Done in the user helper rather than
        # in that one test: a cart fans out to several creators, and which of
        # them ends up answering is exactly the sort of thing a test here
        # rearranges.
        seed_party_details(db, u.id, role)
        return u.id
    finally:
        db.close()


def _package(client, creator_id, title, platform="instagram", deliverable_type="reel",
             price=25000, currency="XOF", quantity=2, active=True):
    db = client.session_factory()
    try:
        pkg = Package(
            user_id=creator_id, platform=platform, deliverable_type=deliverable_type,
            title=title, price_amount=price, currency=currency, quantity=quantity,
            is_active=active,
        )
        db.add(pkg); db.commit(); db.refresh(pkg)
        return pkg.id
    finally:
        db.close()


def _rows(client, model, **filters):
    db = client.session_factory()
    try:
        query = db.query(model)
        for field, value in filters.items():
            query = query.filter(getattr(model, field) == value)
        return query.all()
    finally:
        db.close()


def _checkout(client, buyer, items):
    return client.post("/campaigns/orders/checkout", json={"items": items}, headers=_headers(buyer))


def _nothing_was_created(client):
    return (
        _rows(client, campaigns.Campaign) == []
        and _rows(client, campaigns.Proposal) == []
        and _rows(client, campaigns.CampaignInvitation) == []
    )


@pytest.fixture()
def market(client):
    """A buyer and two creators, each with a package on their profile."""
    buyer = _user(client, "+22990030001", "business")
    ama = _user(client, "+22990030002", "influencer")
    kofi = _user(client, "+22990030003", "influencer")
    ama_pkg = _package(client, ama, "Two reels", price=25000, quantity=2)
    kofi_pkg = _package(
        client, kofi, "One TikTok video", platform="tiktok", deliverable_type="video",
        price=15000, quantity=1,
    )
    return {
        "buyer": buyer,
        "ama": ama, "ama_pkg": ama_pkg,
        "kofi": kofi, "kofi_pkg": kofi_pkg,
    }


# --------------------------------------------------------------------------
# Fanning out
# --------------------------------------------------------------------------


def test_two_creators_become_two_independent_orders(client, market):
    r = _checkout(client, market["buyer"], [
        {"package_id": market["ama_pkg"]},
        {"package_id": market["kofi_pkg"]},
    ])
    assert r.status_code == 201
    orders = r.json()["orders"]
    assert [o["creator_user_id"] for o in orders] == [market["ama"], market["kofi"]]

    ama_campaign = _rows(client, campaigns.Campaign, id=orders[0]["campaign_id"])[0]
    assert ama_campaign.is_direct is True
    assert ama_campaign.status == campaigns.PUBLISHED
    assert ama_campaign.budget_amount == 25000
    assert ama_campaign.budget_currency == "XOF"
    assert ama_campaign.deliverables == [{"platform": "instagram", "type": "reel", "quantity": 2}]

    kofi_campaign = _rows(client, campaigns.Campaign, id=orders[1]["campaign_id"])[0]
    assert kofi_campaign.budget_amount == 15000
    assert kofi_campaign.deliverables == [{"platform": "tiktok", "type": "video", "quantity": 1}]

    # Two separate campaigns, two invitations, two offers on two clocks.
    assert len({o["campaign_id"] for o in orders}) == 2
    assert len(_rows(client, campaigns.CampaignInvitation)) == 2
    assert len(_rows(client, campaigns.Proposal)) == 2
    assert all(o["expires_at"] is not None for o in orders)

    # Each creator hears about their own order and nothing else.
    assert len(_rows(client, Notification, user_id=market["ama"], type="direct_order")) == 1
    assert len(_rows(client, Notification, user_id=market["kofi"], type="direct_order")) == 1


def test_two_packages_from_one_creator_are_one_order_with_two_deliverables(client, market):
    """One creator, one answer, one contract, one escrow — so one order."""
    second = _package(
        client, market["ama"], "A story set", deliverable_type="story", price=10000, quantity=3,
    )
    r = _checkout(client, market["buyer"], [
        {"package_id": market["ama_pkg"]},
        {"package_id": second},
    ])
    assert r.status_code == 201
    orders = r.json()["orders"]
    assert len(orders) == 1
    assert orders[0]["creator_user_id"] == market["ama"]

    campaign = _rows(client, campaigns.Campaign, id=orders[0]["campaign_id"])[0]
    assert campaign.deliverables == [
        {"platform": "instagram", "type": "reel", "quantity": 2},
        {"platform": "instagram", "type": "story", "quantity": 3},
    ]
    # The budget is the sum, and the proposal quotes the same number.
    assert campaign.budget_amount == 35000
    proposal = _rows(client, campaigns.Proposal, id=orders[0]["proposal_id"])[0]
    assert proposal.rate_amount == 35000
    assert proposal.rate_currency == "XOF"
    assert proposal.author_role == campaigns.AUTHOR_BUSINESS
    assert proposal.version == 1
    # Both titles are in it, because the creator has to see what was bought.
    assert "Two reels" in campaign.title and "A story set" in campaign.title


def test_a_cart_takes_custom_terms_alongside_packages(client, market):
    """A basket line is an order body: the same two forms, the same rules."""
    r = _checkout(client, market["buyer"], [
        {"package_id": market["ama_pkg"]},
        {
            "creator_user_id": market["kofi"],
            "platform": "youtube",
            "deliverable_type": "short",
            "quantity": 1,
            "rate_amount": 60000,
            "currency": "XOF",
            "timeline_days": 12,
        },
    ])
    assert r.status_code == 201
    orders = r.json()["orders"]
    assert len(orders) == 2
    kofi_proposal = _rows(client, campaigns.Proposal, id=orders[1]["proposal_id"])[0]
    assert kofi_proposal.rate_amount == 60000
    assert kofi_proposal.timeline_days == 12


def test_the_order_promises_the_longest_of_its_timelines(client, market):
    """One order is one commitment, met when the slowest piece lands."""
    r = _checkout(client, market["buyer"], [
        {
            "creator_user_id": market["ama"], "platform": "instagram",
            "deliverable_type": "reel", "quantity": 1, "rate_amount": 30000,
            "currency": "XOF", "timeline_days": 5,
        },
        {
            "creator_user_id": market["ama"], "platform": "instagram",
            "deliverable_type": "story", "quantity": 2, "rate_amount": 20000,
            "currency": "XOF", "timeline_days": 21,
        },
    ])
    assert r.status_code == 201
    proposal = _rows(client, campaigns.Proposal, id=r.json()["orders"][0]["proposal_id"])[0]
    assert proposal.timeline_days == 21
    assert proposal.rate_amount == 50000


# --------------------------------------------------------------------------
# One escrow, one currency
# --------------------------------------------------------------------------


def test_mixed_currencies_for_one_creator_are_refused_naming_them(client, market):
    """There is no such thing as holding XOF and GHS against one agreement,
    and summing them needs a rate the platform does not set."""
    ghs = _package(client, market["ama"], "Ghana rate", price=400, currency="GHS", quantity=1)
    r = _checkout(client, market["buyer"], [
        {"package_id": market["ama_pkg"]},
        {"package_id": ghs},
    ])
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert market["ama"] in detail
    assert "GHS" in detail and "XOF" in detail
    assert "escrow" in detail
    assert _nothing_was_created(client)


def test_two_creators_in_two_currencies_are_fine(client, market):
    """They are two orders and two escrows already — the rule is per creator."""
    ghs = _package(client, market["kofi"], "Ghana rate", price=400, currency="GHS", quantity=1)
    r = _checkout(client, market["buyer"], [
        {"package_id": market["ama_pkg"]},
        {"package_id": ghs},
    ])
    assert r.status_code == 201
    currencies = {c.budget_currency for c in _rows(client, campaigns.Campaign)}
    assert currencies == {"XOF", "GHS"}


# --------------------------------------------------------------------------
# All or nothing
# --------------------------------------------------------------------------


def test_one_unknown_package_aborts_the_whole_checkout(client, market):
    r = _checkout(client, market["buyer"], [
        {"package_id": market["ama_pkg"]},
        {"package_id": "no-such-package"},
        {"package_id": market["kofi_pkg"]},
    ])
    assert r.status_code == 400
    assert r.json()["detail"].startswith("Item 1:")
    assert _nothing_was_created(client)
    # And nobody was told about an order that does not exist.
    assert _rows(client, Notification) == []


def test_one_item_under_the_price_floor_aborts_the_whole_checkout(client, market):
    """Every rule a lone order runs, run per line — "put it in a cart" must not
    become the way around the floor."""
    r = _checkout(client, market["buyer"], [
        {"package_id": market["ama_pkg"]},
        {
            "creator_user_id": market["kofi"], "platform": "instagram",
            "deliverable_type": "reel", "quantity": 1, "rate_amount": 1000,
            "currency": "XOF", "timeline_days": 7,
        },
    ])
    assert r.status_code == 400
    assert r.json()["detail"] == "Item 1: Minimum price for XOF is 5000."
    assert _nothing_was_created(client)


def test_an_inactive_package_aborts_the_whole_checkout(client, market):
    dead = _package(client, market["kofi"], "Retired bundle", price=9000, active=False)
    r = _checkout(client, market["buyer"], [
        {"package_id": market["ama_pkg"]},
        {"package_id": dead},
    ])
    assert r.status_code == 400
    assert "Item 1" in r.json()["detail"]
    assert _nothing_was_created(client)


def test_a_half_filled_line_aborts_the_whole_checkout(client, market):
    """A line is an order body, held to the same shape rule."""
    r = _checkout(client, market["buyer"], [
        {"package_id": market["ama_pkg"]},
        {"creator_user_id": market["kofi"], "platform": "instagram"},
    ])
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail.startswith("Item 1:") and "rate_amount" in detail
    assert _nothing_was_created(client)


def test_a_buyer_cannot_slip_their_own_package_into_a_cart(client, market):
    """The self-order rule is not a property of the single-order endpoint."""
    own = _package(client, market["buyer"], "My own package", price=9000)
    r = _checkout(client, market["buyer"], [{"package_id": own}])
    assert r.status_code == 400
    assert "Item 0" in r.json()["detail"]
    assert _nothing_was_created(client)


# --------------------------------------------------------------------------
# The bounds on a basket
# --------------------------------------------------------------------------


def test_an_empty_cart_is_refused(client, market):
    r = _checkout(client, market["buyer"], [])
    assert r.status_code == 400
    assert "at least one item" in r.json()["detail"]
    assert _nothing_was_created(client)


def test_a_cart_past_the_cap_is_refused(client, market):
    items = [{"package_id": market["ama_pkg"]}] * (cart_module.MAX_CART_ITEMS + 1)
    r = _checkout(client, market["buyer"], items)
    assert r.status_code == 400
    assert str(cart_module.MAX_CART_ITEMS) in r.json()["detail"]
    assert _nothing_was_created(client)


def test_checkout_requires_auth_and_a_buyer(client, market):
    assert client.post(
        "/campaigns/orders/checkout", json={"items": [{"package_id": market["ama_pkg"]}]}
    ).status_code == 401
    # Same rule as authoring a brief: buying is the brand side of the market.
    r = _checkout(client, market["kofi"], [{"package_id": market["ama_pkg"]}])
    assert r.status_code == 403
    assert _nothing_was_created(client)


# --------------------------------------------------------------------------
# The orders are independent afterwards, which is the whole reason to fan out
# --------------------------------------------------------------------------


def test_one_creator_declining_leaves_the_other_untouched(client, market):
    r = _checkout(client, market["buyer"], [
        {"package_id": market["ama_pkg"]},
        {"package_id": market["kofi_pkg"]},
    ])
    ama_order, kofi_order = r.json()["orders"]

    declined = client.post(
        f"/campaigns/orders/{ama_order['proposal_id']}/decline", headers=_headers(market["ama"])
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == campaigns.PROPOSAL_DECLINED
    assert _rows(client, campaigns.Campaign, id=ama_order["campaign_id"])[0].status == campaigns.CANCELLED

    # Kofi's order never noticed.
    assert _rows(client, campaigns.Proposal, id=kofi_order["proposal_id"])[0].status == campaigns.SUBMITTED
    assert _rows(client, campaigns.Campaign, id=kofi_order["campaign_id"])[0].status == campaigns.PUBLISHED
    # And he can still accept it, through the ordinary path.
    accepted = client.post(
        f"/campaigns/orders/{kofi_order['proposal_id']}/accept", headers=_headers(market["kofi"])
    )
    assert accepted.status_code == 201
    assert accepted.json()["campaign_id"] == kofi_order["campaign_id"]
    assert accepted.json()["rate_amount"] == 15000


def test_each_creator_only_ever_sees_their_own_order(client, market):
    """A cart is a private basket, not a shared campaign: nothing about it
    tells one creator who else the brand bought from."""
    r = _checkout(client, market["buyer"], [
        {"package_id": market["ama_pkg"]},
        {"package_id": market["kofi_pkg"]},
    ])
    ama_order, kofi_order = r.json()["orders"]

    ama_invites = client.get("/campaigns/invitations/mine", headers=_headers(market["ama"])).json()
    assert [i["campaign_id"] for i in ama_invites] == [ama_order["campaign_id"]]
    assert market["kofi"] not in str(ama_invites)

    # The buyer sees both, because they placed both.
    mine = client.get("/campaigns/mine", headers=_headers(market["buyer"])).json()
    assert {c["id"] for c in mine} == {ama_order["campaign_id"], kofi_order["campaign_id"]}

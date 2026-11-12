"""Blocks, on the three surfaces that LIST people.

Each of these asserts a disappearance, which is a harder thing to test than a
refusal: a missing row looks exactly like a row that was never there. So every
test here establishes the creator IS visible first, and only then blocks and
looks again. A test that only checked the second half would pass just as
happily against a search that was broken for everybody.

BOTH DIRECTIONS ARE TESTED SEPARATELY because the row only has one. A block
is one person's decision and two rows would be two decisions, but the EFFECT
has to be symmetric: if it only hid the blocker from the blocked, the brand
who pressed block would keep meeting that creator in their own search results,
which is the single face they pressed it to stop seeing.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db, import_all_models
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.discovery.router import router as discovery_router
from app.modules.profiles import models as pmodels
from app.modules.trust_safety.models import Block


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    import_all_models()
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(discovery_router, prefix="/discovery")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = testing_session
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _ig_packages(user_id, prices=(30000, 40000, 50000)):
    """The three active packages a profile needs to be searchable."""
    deliverables = ("post", "reel", "story")
    return [
        pmodels.Package(
            user_id=user_id, platform="instagram", deliverable_type=deliverables[i % 3],
            title=f"1 IG {deliverables[i % 3]}", price_amount=price, currency="XOF", is_active=True,
        )
        for i, price in enumerate(prices)
    ]


def _creator(client, phone, display_name):
    db = client.session_factory()
    try:
        user = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x",
                    country_code="BJ", role="influencer", is_verified=True)
        db.add(user); db.commit(); db.refresh(user)
        db.add(pmodels.InfluencerProfile(
            user_id=user.id, bio="Creator", categories=["fashion"],
            rate_card={}, follower_count=5000, display_name=display_name,
        ))
        db.add_all(_ig_packages(user.id))
        db.commit()
        return user.id
    finally:
        db.close()


def _business(client, phone):
    db = client.session_factory()
    try:
        user = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x",
                    country_code="BJ", role="business", is_verified=True)
        db.add(user); db.commit(); db.refresh(user)
        return user.id
    finally:
        db.close()


def _block(client, blocker, blocked):
    db = client.session_factory()
    try:
        db.add(Block(blocker_user_id=blocker, blocked_user_id=blocked))
        db.commit()
    finally:
        db.close()


def _unblock(client, blocker, blocked):
    db = client.session_factory()
    try:
        db.query(Block).filter(
            Block.blocker_user_id == blocker, Block.blocked_user_id == blocked
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _names(rows):
    return sorted(row["display_name"] for row in rows)


# ---- search ----

def test_a_brand_stops_seeing_a_creator_it_blocked(client):
    biz = _business(client, "+22990080001")
    _creator(client, "+22990080002", "Ama")
    blocked = _creator(client, "+22990080003", "Kofi")

    assert _names(client.get("/discovery/search", headers=_headers(biz)).json()) == ["Ama", "Kofi"]

    _block(client, biz, blocked)
    assert _names(client.get("/discovery/search", headers=_headers(biz)).json()) == ["Ama"]


def test_a_creator_who_blocks_a_brand_disappears_from_that_brands_search(client):
    """The other direction, and the one a one-sided filter would get wrong."""
    biz = _business(client, "+22990080010")
    _creator(client, "+22990080011", "Ama")
    blocker = _creator(client, "+22990080012", "Kofi")

    assert _names(client.get("/discovery/search", headers=_headers(biz)).json()) == ["Ama", "Kofi"]

    _block(client, blocker, biz)
    assert _names(client.get("/discovery/search", headers=_headers(biz)).json()) == ["Ama"]


def test_a_visitor_with_no_account_still_sees_the_whole_roster(client):
    """Search is public and stays public. A block is a fact about a
    relationship, and somebody who has not signed in has none."""
    biz = _business(client, "+22990080020")
    _creator(client, "+22990080021", "Ama")
    blocked = _creator(client, "+22990080022", "Kofi")
    _block(client, biz, blocked)

    r = client.get("/discovery/search")
    assert r.status_code == 200
    assert _names(r.json()) == ["Ama", "Kofi"]


def test_somebody_elses_block_does_not_shrink_my_results(client):
    other = _business(client, "+22990080030")
    me = _business(client, "+22990080031")
    _creator(client, "+22990080032", "Ama")
    blocked = _creator(client, "+22990080033", "Kofi")
    _block(client, other, blocked)

    assert _names(client.get("/discovery/search", headers=_headers(me)).json()) == ["Ama", "Kofi"]


def test_a_broken_token_is_treated_as_a_visitor_rather_than_refused(client):
    """get_optional_user_id never raises. A session that expired in another
    tab sees the public page, not a blank one."""
    _creator(client, "+22990080040", "Ama")
    r = client.get("/discovery/search", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 200
    assert _names(r.json()) == ["Ama"]


def test_blocking_everybody_leaves_an_empty_list_and_not_an_error(client):
    biz = _business(client, "+22990080050")
    only = _creator(client, "+22990080051", "Ama")
    _block(client, biz, only)

    r = client.get("/discovery/search", headers=_headers(biz))
    assert r.status_code == 200
    assert r.json() == []


def test_a_block_survives_the_other_filters(client):
    """The check sits at the top of the loop so no filter below it can let a
    blocked creator through. This asks with every filter engaged at once."""
    biz = _business(client, "+22990080060")
    blocked = _creator(client, "+22990080061", "Kofi")
    _block(client, biz, blocked)

    rows = client.get(
        "/discovery/search",
        params={"category": "fashion", "country": "BJ", "platform": "instagram",
                "min_followers": 1, "max_followers": 999999, "q": "Kofi"},
        headers=_headers(biz),
    ).json()
    assert rows == []


# ---- the landing page strip ----

def test_the_strip_drops_a_blocked_creator_for_a_signed_in_viewer(client):
    biz = _business(client, "+22990080100")
    _creator(client, "+22990080101", "Ama")
    blocked = _creator(client, "+22990080102", "Kofi")

    assert _names(client.get("/discovery/featured", headers=_headers(biz)).json()) == ["Ama", "Kofi"]

    _block(client, biz, blocked)
    assert _names(client.get("/discovery/featured", headers=_headers(biz)).json()) == ["Ama"]


def test_the_strip_is_whole_for_a_visitor(client):
    biz = _business(client, "+22990080110")
    _creator(client, "+22990080111", "Ama")
    blocked = _creator(client, "+22990080112", "Kofi")
    _block(client, biz, blocked)

    assert _names(client.get("/discovery/featured").json()) == ["Ama", "Kofi"]


def test_the_strip_is_shorter_rather_than_backfilled_from_nowhere(client):
    """Two creators, a strip of two, one blocked: one card comes back. Nothing
    tells the viewer a card was removed, which is the point."""
    biz = _business(client, "+22990080120")
    _creator(client, "+22990080121", "Ama")
    blocked = _creator(client, "+22990080122", "Kofi")
    _block(client, biz, blocked)

    rows = client.get("/discovery/featured", params={"limit": 2}, headers=_headers(biz)).json()
    assert _names(rows) == ["Ama"]


# ---- the favourites shortlist ----

def test_a_blocked_creator_leaves_the_shortlist_and_comes_back_on_unblock(client):
    """The favourite row is the brand's own note to itself. A block hides it;
    it does not destroy it, because the decision is reversible and the data
    is not."""
    biz = _business(client, "+22990080200")
    keep = _creator(client, "+22990080201", "Ama")
    drop = _creator(client, "+22990080202", "Kofi")

    for uid in (keep, drop):
        assert client.post(f"/discovery/favorites/{uid}", headers=_headers(biz)).status_code == 201
    assert len(client.get("/discovery/favorites", headers=_headers(biz)).json()) == 2

    _block(client, biz, drop)
    rows = client.get("/discovery/favorites", headers=_headers(biz)).json()
    assert [r["influencer_user_id"] for r in rows] == [keep]

    _unblock(client, biz, drop)
    assert len(client.get("/discovery/favorites", headers=_headers(biz)).json()) == 2


def test_a_creators_block_also_hides_them_from_the_brands_shortlist(client):
    biz = _business(client, "+22990080210")
    creator = _creator(client, "+22990080211", "Kofi")
    client.post(f"/discovery/favorites/{creator}", headers=_headers(biz))

    _block(client, creator, biz)
    assert client.get("/discovery/favorites", headers=_headers(biz)).json() == []

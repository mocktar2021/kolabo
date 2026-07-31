"""Tests for Epic C (KOL-3): discovery search and favorites."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.discovery.router import router as discovery_router
from app.modules.profiles import models as pmodels


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    from app.core.db import import_all_models
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
    test_client = TestClient(app)
    test_client.session_factory = testing_session
    return test_client


def _ig_packages(user_id, prices=(30000, 40000, 50000)):
    """Three active Instagram packages at floor-respecting prices: the
    storefront a profile needs to be searchable (MIN_LIVE_PACKAGES)."""
    deliverables = ("post", "reel", "story")
    return [
        pmodels.Package(
            user_id=user_id, platform="instagram", deliverable_type=deliverables[i % 3],
            title=f"1 IG {deliverables[i % 3]}", price_amount=price, currency="XOF", is_active=True,
        )
        for i, price in enumerate(prices)
    ]


def _make_influencer(client, phone, verified, categories, followers, country="BJ", bio="Creator"):
    db = client.session_factory()
    try:
        user = User(phone=phone, password_hash="x", country_code=country, role="influencer", is_verified=verified)
        db.add(user)
        db.commit()
        db.refresh(user)
        prof = pmodels.InfluencerProfile(
            user_id=user.id, bio=bio, categories=categories, rate_card={"post": 100}, follower_count=followers
        )
        db.add(prof)
        db.add_all(_ig_packages(user.id))
        db.commit()
        return user.id
    finally:
        db.close()


def _make_business_token(client, phone="+22990000100"):
    db = client.session_factory()
    try:
        user = User(phone=phone, password_hash="x", country_code="BJ", role="business", is_verified=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        uid = user.id
    finally:
        db.close()
    return uid, {"Authorization": f"Bearer {create_access_token(uid)}"}


def test_search_returns_only_searchable_and_matches_category(client):
    _make_influencer(client, "+22990000001", True, ["fashion"], 5000)
    _make_influencer(client, "+22990000002", True, ["tech"], 8000)
    # An incomplete profile (no bio) must not appear.
    db = client.session_factory()
    u = User(phone="+22990000003", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
    db.add(u); db.commit(); db.refresh(u)
    db.add(pmodels.InfluencerProfile(user_id=u.id, bio=None, categories=["fashion"], rate_card={"p": 1}))
    db.add_all(_ig_packages(u.id))
    db.commit(); db.close()

    r = client.get("/discovery/search", params={"category": "fashion"})
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["categories"] == ["fashion"]


def test_verified_profiles_rank_above_unverified(client):
    _make_influencer(client, "+22990000004", False, ["tech"], 9000)
    _make_influencer(client, "+22990000005", True, ["tech"], 1000)
    results = client.get("/discovery/search", params={"category": "tech"}).json()
    assert len(results) == 2
    assert results[0]["is_verified"] is True
    assert results[1]["is_verified"] is False


def test_follower_range_filter(client):
    _make_influencer(client, "+22990000006", True, ["food"], 2000)
    _make_influencer(client, "+22990000007", True, ["food"], 50000)
    results = client.get("/discovery/search", params={"category": "food", "min_followers": 10000}).json()
    assert len(results) == 1
    assert results[0]["follower_count"] == 50000


def test_platform_filter_matches_social_accounts(client):
    """The landing page platform selector filters on real presence: a creator
    with a TikTok account shows under tiktok and not under snapchat."""
    uid = _make_influencer(client, "+22990000210", True, ["fashion"], 8000)
    db = client.session_factory()
    db.add(pmodels.SocialAccount(
        user_id=uid, platform="tiktok", handle="ama", method="oauth", status="verified",
    ))
    db.commit(); db.close()

    results = client.get("/discovery/search", params={"platform": "tiktok"}).json()
    assert len(results) == 1
    assert results[0]["user_id"] == uid
    assert client.get("/discovery/search", params={"platform": "snapchat"}).json() == []


def test_platform_filter_matches_active_packages(client):
    """A UGC creator has no social account to connect: the package itself is
    what they sell on that platform, so it must count as presence."""
    uid = _profile_without_rate(client, "+22990000211", ["fashion"], 5000)
    db = client.session_factory()
    db.add_all([
        pmodels.Package(user_id=uid, platform="ugc", deliverable_type="ugc_video", title="1 UGC video",
                        price_amount=25000, currency="XOF", is_active=True),
        pmodels.Package(user_id=uid, platform="ugc", deliverable_type="ugc_photo", title="3 UGC photos",
                        price_amount=30000, currency="XOF", is_active=True),
        pmodels.Package(user_id=uid, platform="ugc", deliverable_type="ugc_video", title="UGC bundle",
                        price_amount=60000, currency="XOF", is_active=True),
    ])
    db.commit(); db.close()

    results = client.get("/discovery/search", params={"platform": "ugc"}).json()
    assert len(results) == 1
    assert results[0]["user_id"] == uid


def test_unknown_platform_matches_nothing(client):
    """An unknown platform behaves like an unknown category: quietly empty,
    never a 500 or a full unfiltered list."""
    _make_influencer(client, "+22990000212", True, ["fashion"], 8000)
    r = client.get("/discovery/search", params={"platform": "myspace"})
    assert r.status_code == 200
    assert r.json() == []


def test_favorites_require_auth(client):
    inf = _make_influencer(client, "+22990000008", True, ["fashion"], 3000)
    assert client.post(f"/discovery/favorites/{inf}").status_code == 401


def test_favorites_add_list_remove(client):
    inf = _make_influencer(client, "+22990000009", True, ["fashion"], 3000)
    _, headers = _make_business_token(client)
    assert client.post(f"/discovery/favorites/{inf}", headers=headers).status_code == 201
    # Idempotent add does not duplicate.
    client.post(f"/discovery/favorites/{inf}", headers=headers)
    favs = client.get("/discovery/favorites", headers=headers).json()
    assert len(favs) == 1
    assert favs[0]["influencer_user_id"] == inf
    assert client.delete(f"/discovery/favorites/{inf}", headers=headers).status_code == 204
    assert client.get("/discovery/favorites", headers=headers).json() == []


def test_favorite_unknown_influencer_404(client):
    _, headers = _make_business_token(client, phone="+22990000200")
    assert client.post("/discovery/favorites/nope", headers=headers).status_code == 404


def _profile_without_rate(client, phone, categories, followers, bio="Creator"):
    """A creator who filled bio and categories but has no packages yet."""
    db = client.session_factory()
    try:
        user = User(phone=phone, password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add(user); db.commit(); db.refresh(user)
        prof = pmodels.InfluencerProfile(
            user_id=user.id, bio=bio, categories=categories, rate_card={}, follower_count=followers,
            display_name="Ama K.", headline="Lifestyle creator",
        )
        db.add(prof); db.commit()
        return user.id
    finally:
        db.close()


def test_profile_without_packages_is_not_searchable(client):
    _profile_without_rate(client, "+22990000201", ["fashion"], 5000)
    assert client.get("/discovery/search").json() == []


def test_rate_card_alone_is_not_searchable(client):
    """No grandfathering: a profile that was live on the legacy rate card
    drops out of search until it publishes real packages."""
    uid = _profile_without_rate(client, "+22990000206", ["fashion"], 5000)
    db = client.session_factory()
    prof = db.query(pmodels.InfluencerProfile).filter(pmodels.InfluencerProfile.user_id == uid).first()
    prof.rate_card = {"post": 30000}
    db.commit(); db.close()
    assert client.get("/discovery/search").json() == []


def test_three_active_packages_make_profile_searchable(client):
    """One package reads as a placeholder; MIN_LIVE_PACKAGES active ones are
    the storefront a profile needs to appear in search."""
    uid = _profile_without_rate(client, "+22990000202", ["fashion"], 5000)
    db = client.session_factory()
    db.add_all(_ig_packages(uid, prices=(30000, 45000, 60000)))
    db.commit(); db.close()

    results = client.get("/discovery/search").json()
    assert len(results) == 1
    assert results[0]["user_id"] == uid
    assert results[0]["starting_price_amount"] == 30000
    assert results[0]["starting_price_currency"] == "XOF"
    assert results[0]["display_name"] == "Ama K."


def test_fewer_than_three_active_packages_is_not_searchable(client):
    """Two active packages stay short of the bar, and an inactive third does
    not count toward it."""
    uid = _profile_without_rate(client, "+22990000203", ["fashion"], 5000)
    db = client.session_factory()
    db.add_all([
        pmodels.Package(user_id=uid, platform="instagram", deliverable_type="post", title="1 IG Post",
                        price_amount=30000, currency="XOF", is_active=True),
        pmodels.Package(user_id=uid, platform="instagram", deliverable_type="reel", title="1 IG Reel",
                        price_amount=45000, currency="XOF", is_active=True),
        pmodels.Package(user_id=uid, platform="instagram", deliverable_type="story", title="Hidden",
                        price_amount=30000, currency="XOF", is_active=False),
    ])
    db.commit(); db.close()
    assert client.get("/discovery/search").json() == []


def test_starting_price_is_the_cheapest_active_package(client):
    uid = _profile_without_rate(client, "+22990000204", ["fashion"], 5000)
    db = client.session_factory()
    db.add_all([
        pmodels.Package(user_id=uid, platform="instagram", deliverable_type="reel", title="Reel",
                        price_amount=90000, currency="XOF", is_active=True),
        pmodels.Package(user_id=uid, platform="instagram", deliverable_type="story", title="Story",
                        price_amount=15000, currency="XOF", is_active=True),
        pmodels.Package(user_id=uid, platform="instagram", deliverable_type="post", title="Post",
                        price_amount=30000, currency="XOF", is_active=True),
    ])
    db.commit(); db.close()
    results = client.get("/discovery/search").json()
    assert results[0]["starting_price_amount"] == 15000


def test_search_is_public_and_returns_card_fields(client):
    _make_influencer(client, "+22990000205", True, ["fashion"], 8000)
    # No Authorization header at all: search must stay public.
    r = client.get("/discovery/search")
    assert r.status_code == 200
    body = r.json()[0]
    for key in ("display_name", "headline", "avatar_url", "starting_price_amount", "average_stars", "review_count"):
        assert key in body
    assert body["review_count"] == 0

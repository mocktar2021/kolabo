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
    db = client.session_factory()
    u = User(phone="+22990000003", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
    db.add(u); db.commit(); db.refresh(u)
    db.add(pmodels.InfluencerProfile(user_id=u.id, bio=None, categories=["fashion"], rate_card={"p": 1}))
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


def test_favorites_require_auth(client):
    inf = _make_influencer(client, "+22990000008", True, ["fashion"], 3000)
    assert client.post(f"/discovery/favorites/{inf}").status_code == 401


def test_favorites_add_list_remove(client):
    inf = _make_influencer(client, "+22990000009", True, ["fashion"], 3000)
    _, headers = _make_business_token(client)
    assert client.post(f"/discovery/favorites/{inf}", headers=headers).status_code == 201
    client.post(f"/discovery/favorites/{inf}", headers=headers)
    favs = client.get("/discovery/favorites", headers=headers).json()
    assert len(favs) == 1
    assert favs[0]["influencer_user_id"] == inf
    assert client.delete(f"/discovery/favorites/{inf}", headers=headers).status_code == 204
    assert client.get("/discovery/favorites", headers=headers).json() == []


def test_favorite_unknown_influencer_404(client):
    _, headers = _make_business_token(client, phone="+22990000200")
    assert client.post("/discovery/favorites/nope", headers=headers).status_code == 404

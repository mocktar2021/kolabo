"""Onboarding support: social account listing, enrichment, readiness status."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.modules.auth.models import User
from app.modules.profiles.router import router as profiles_router


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    from app.core.db import import_all_models
    import_all_models()
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(profiles_router, prefix="/profiles")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _user(client, phone):
    db = client.session_factory()
    try:
        u = User(phone=phone, password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add(u); db.commit(); db.refresh(u)
        return u.id
    finally:
        db.close()


def test_social_account_list_and_enrichment_flag(client):
    uid = _user(client, "+22990000020")
    r = client.post(f"/profiles/{uid}/social-accounts", json={
        "platform": "tiktok", "handle": "ama", "method": "manual", "proof_url": "https://p"
    })
    assert r.status_code == 201
    # No enrichment provider is configured, so nothing is auto filled and we say so.
    assert r.json()["enriched"] is False
    listed = client.get(f"/profiles/{uid}/social-accounts").json()
    assert len(listed) == 1
    assert listed[0]["handle"] == "ama"


def test_enricher_fills_only_empty_fields(client, monkeypatch):
    from app.modules.profiles import service as psvc

    class FakeEnricher:
        def fetch(self, platform, handle):
            return {"display_name": "From Platform", "follower_count": 4321, "bio": "Platform bio"}

    monkeypatch.setattr(psvc, "social_enricher", FakeEnricher())
    uid = _user(client, "+22990000021")
    # The creator already wrote their own bio; it must not be overwritten.
    client.put(f"/profiles/influencer/{uid}", json={"bio": "My own bio", "categories": [], "rate_card": {}})
    client.post(f"/profiles/{uid}/social-accounts", json={"platform": "youtube", "handle": "ama", "method": "oauth"})

    prof = client.get(f"/profiles/influencer/{uid}").json()
    assert prof["bio"] == "My own bio"               # preserved
    assert prof["display_name"] == "From Platform"   # filled, was empty
    assert prof["follower_count"] == 4321


def test_onboarding_status_tracks_readiness(client):
    uid = _user(client, "+22990000022")
    s0 = client.get(f"/profiles/{uid}/onboarding-status").json()
    assert s0["is_live"] is False and s0["has_social"] is False

    client.put(f"/profiles/influencer/{uid}", json={"bio": "Hi", "categories": ["fashion"], "rate_card": {}})
    s1 = client.get(f"/profiles/{uid}/onboarding-status").json()
    assert s1["has_bio"] and s1["has_categories"]
    assert s1["has_pricing"] is False and s1["is_live"] is False

    client.post(f"/profiles/{uid}/packages", json={
        "platform": "instagram", "deliverable_type": "post", "title": "1 IG Post",
        "price_amount": 30000, "currency": "XOF",
    })
    s2 = client.get(f"/profiles/{uid}/onboarding-status").json()
    assert s2["has_packages"] and s2["has_pricing"] and s2["is_live"] is True

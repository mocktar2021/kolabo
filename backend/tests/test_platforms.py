"""Platform to deliverable mapping and the validation it drives."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import platforms
from app.core.db import Base, get_db
from app.modules.auth.models import User
from app.modules.profiles.router import router as profiles_router


def test_deliverables_reflect_how_each_platform_actually_works():
    p = platforms.PLATFORM_DELIVERABLES
    # TikTok sells video, not a generic "post".
    assert "video" in p["tiktok"] and "post" not in p["tiktok"]
    # Shorts belong to YouTube, reels to Instagram and Facebook.
    assert "short" in p["youtube"] and "short" not in p["instagram"]
    assert "reel" in p["instagram"] and "reel" in p["facebook"]
    # Snapchat has snaps and spotlight rather than posts.
    assert {"snap", "spotlight"} <= set(p["snapchat"]) and "post" not in p["snapchat"]
    # A thread is its own deliverable on X.
    assert "thread" in p["x"]
    # WhatsApp only has status.
    assert p["whatsapp"] == ["status"]
    # UGC is platform agnostic content made for the brand.
    assert set(p["ugc"]) == {"ugc_video", "ugc_photo"}


def test_platforms_without_public_metrics_are_excluded_from_audience():
    assert "whatsapp" not in platforms.PLATFORMS_WITH_AUDIENCE
    assert "discord" not in platforms.PLATFORMS_WITH_AUDIENCE
    assert "ugc" not in platforms.PLATFORMS_WITH_AUDIENCE
    assert "instagram" in platforms.PLATFORMS_WITH_AUDIENCE


def test_every_catalog_platform_is_connectable(): 
    """SOCIAL_PLATFORMS is DERIVED from the catalog rather than listed beside
    it, which is what makes this true by construction: adding a platform to
    PLATFORM_DELIVERABLES makes it connectable in the same edit, and there is
    no second allow-list to forget. The ones with no public audience metric
    are in the catalog too — having no follower count is not the same as not
    existing."""
    assert platforms.SOCIAL_PLATFORMS == set(platforms.PLATFORM_DELIVERABLES)
    assert {"whatsapp", "discord", "ugc"} <= platforms.SOCIAL_PLATFORMS


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


def _user(client, phone="+22990000301"):
    db = client.session_factory()
    try:
        u = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add(u); db.commit(); db.refresh(u)
        return u.id
    finally:
        db.close()


def test_package_rejects_deliverable_not_on_that_platform(client):
    uid = _user(client)
    r = client.post(f"/profiles/{uid}/packages", json={
        "platform": "instagram", "deliverable_type": "short",
        "title": "Wrong", "price_amount": 1000, "currency": "XOF",
    })
    assert r.status_code == 400
    assert "not available on instagram" in r.json()["detail"]


def test_package_accepts_valid_pair(client):
    uid = _user(client, "+22990000302")
    r = client.post(f"/profiles/{uid}/packages", json={
        "platform": "tiktok", "deliverable_type": "video",
        "title": "1 TikTok video", "price_amount": 40000, "currency": "XOF",
    })
    assert r.status_code == 201


def test_follower_count_is_stored_per_platform(client):
    uid = _user(client, "+22990000303")
    client.post(f"/profiles/{uid}/social-accounts", json={
        "platform": "instagram", "handle": "ama", "method": "manual",
        "proof_url": "https://p", "follower_count": 6100,
    })
    client.post(f"/profiles/{uid}/social-accounts", json={
        "platform": "tiktok", "handle": "ama", "method": "manual",
        "proof_url": "https://p", "follower_count": 2100,
    })
    accounts = client.get(f"/profiles/{uid}/social-accounts").json()
    counts = {a["platform"]: a["follower_count"] for a in accounts}
    assert counts == {"instagram": 6100, "tiktok": 2100}


def test_a_creator_can_connect_a_whatsapp_account(client):
    """WhatsApp is a first-class platform to connect, and nothing in the path
    treats it as second class: SOCIAL_PLATFORMS is derived from the catalog so
    membership is automatic, and connect_social_account holds it to the same
    two rules as any other platform (a known platform, and a proof_url when
    the method is manual).

    WHAT IT DOES NOT GET IS A FOLLOWER COUNT, and dropping one is not the same
    as refusing the connection. WhatsApp Status exposes no public metric, so a
    number supplied for it is unverifiable, and showing a buyer a figure the
    platform itself cannot confirm is worse than showing none. The account
    connects, lists, and carries a null count — which is a real answer
    ("unknown"), not a zero.

    A creator who sells WhatsApp Status therefore appears with an audience of
    null rather than being unable to say they are on WhatsApp at all. Their
    packages price it; app.core.identity simply never picks it as the headline
    number.
    """
    uid = _user(client, "+22990000304")
    r = client.post(f"/profiles/{uid}/social-accounts", json={
        "platform": "whatsapp", "handle": "ama-studio", "method": "manual",
        "proof_url": "https://p", "follower_count": 5000,
    })
    assert r.status_code == 201, r.text
    assert r.json()["platform"] == "whatsapp"
    assert r.json()["status"] == "pending"
    assert r.json()["follower_count"] is None

    listed = client.get(f"/profiles/{uid}/social-accounts").json()
    assert [(a["platform"], a["follower_count"]) for a in listed] == [("whatsapp", None)]


def test_a_whatsapp_status_package_can_be_sold(client):
    """The other half of connecting one: status is WhatsApp's only deliverable
    and it is orderable like any other."""
    uid = _user(client, "+22990000305")
    r = client.post(f"/profiles/{uid}/packages", json={
        "platform": "whatsapp", "deliverable_type": "status",
        "title": "1 WhatsApp Status", "price_amount": 15000, "currency": "XOF",
    })
    assert r.status_code == 201, r.text
    r = client.post(f"/profiles/{uid}/packages", json={
        "platform": "whatsapp", "deliverable_type": "post",
        "title": "Not a thing", "price_amount": 15000, "currency": "XOF",
    })
    assert r.status_code == 400
    assert "not available on whatsapp" in r.json()["detail"]

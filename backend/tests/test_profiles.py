"""Tests for Epic B (KOL-2): profiles and verification."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.modules.admin.router import router as admin_router
from app.modules.auth.models import User
from app.modules.profiles.router import router as profiles_router


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
    app.include_router(profiles_router, prefix="/profiles")
    app.include_router(admin_router, prefix="/admin")
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    test_client.session_factory = testing_session
    return test_client


def _make_user(client, phone="+22990000001", role="influencer"):
    db = client.session_factory()
    try:
        user = User(phone=phone, password_hash="x", country_code="BJ", role=role, is_verified=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


ADMIN = {"X-Admin-Id": "admin-1"}


def test_influencer_profile_completion_and_searchable(client):
    uid = _make_user(client)
    # Partial profile is not searchable and under 100 percent.
    r = client.put(f"/profiles/influencer/{uid}", json={"bio": "Creator", "categories": [], "rate_card": {}})
    assert r.status_code == 200
    body = r.json()
    assert body["completion_percent"] == 33
    assert body["is_searchable"] is False
    # Complete profile is searchable at 100 percent.
    r = client.put(
        f"/profiles/influencer/{uid}",
        json={"bio": "Creator", "categories": ["fashion"], "rate_card": {"post": 100}},
    )
    body = r.json()
    assert body["completion_percent"] == 100
    assert body["is_searchable"] is True


def test_influencer_profile_requires_existing_user(client):
    r = client.put("/profiles/influencer/does-not-exist", json={"bio": "x", "categories": ["a"], "rate_card": {"p": 1}})
    assert r.status_code == 404


def test_business_profile_upsert(client):
    uid = _make_user(client, phone="+22990000002", role="business")
    r = client.put(f"/profiles/business/{uid}", json={"company_name": "Acme", "industry": "retail"})
    assert r.status_code == 200
    assert r.json()["company_name"] == "Acme"


def test_verification_document_stored_encrypted_and_pending(client):
    uid = _make_user(client, phone="+22990000003", role="business")
    r = client.post(
        f"/profiles/{uid}/verification-documents",
        data={"doc_type": "business_registration"},
        files={"file": ("reg.pdf", b"real-document-bytes", "application/pdf")},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    # The stored bytes must be ciphertext, never the raw document.
    from app.modules.profiles.models import VerificationDocument
    db = client.session_factory()
    doc = db.query(VerificationDocument).first()
    stored = bytes(doc.ciphertext)
    db.close()
    assert b"real-document-bytes" not in stored


def test_social_oauth_is_verified_manual_is_pending(client):
    uid = _make_user(client, phone="+22990000004")
    r = client.post(f"/profiles/{uid}/social-accounts", json={"platform": "instagram", "handle": "me", "method": "oauth"})
    assert r.status_code == 201
    assert r.json()["status"] == "verified"
    r = client.post(
        f"/profiles/{uid}/social-accounts",
        json={"platform": "tiktok", "handle": "me", "method": "manual", "proof_url": "https://proof"},
    )
    assert r.json()["status"] == "pending"


def test_manual_social_requires_proof(client):
    uid = _make_user(client, phone="+22990000005")
    r = client.post(f"/profiles/{uid}/social-accounts", json={"platform": "tiktok", "handle": "me", "method": "manual"})
    assert r.status_code == 400


def test_admin_queue_requires_admin_header(client):
    r = client.get("/admin/verification-queue")
    assert r.status_code == 401


def test_admin_can_approve_document_and_decision_is_logged(client):
    uid = _make_user(client, phone="+22990000006", role="business")
    client.post(
        f"/profiles/{uid}/verification-documents",
        data={"doc_type": "business_registration"},
        files={"file": ("reg.pdf", b"bytes", "application/pdf")},
    )
    queue = client.get("/admin/verification-queue", headers=ADMIN).json()
    assert len(queue["documents"]) == 1
    doc_id = queue["documents"][0]["id"]
    r = client.post(f"/admin/verification-documents/{doc_id}/decision", json={"decision": "approved"}, headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert r.json()["reviewer_id"] == "admin-1"
    # Decision is recorded in the audit log.
    from app.modules.admin.models import AdminActionLog
    db = client.session_factory()
    log = db.query(AdminActionLog).first()
    db.close()
    assert log.admin_id == "admin-1"
    assert log.target_id == doc_id


def test_document_rejection_requires_reason(client):
    uid = _make_user(client, phone="+22990000007", role="business")
    client.post(
        f"/profiles/{uid}/verification-documents",
        data={"doc_type": "identity"},
        files={"file": ("id.png", b"bytes", "image/png")},
    )
    queue = client.get("/admin/verification-queue", headers=ADMIN).json()
    doc_id = queue["documents"][0]["id"]
    r = client.post(f"/admin/verification-documents/{doc_id}/decision", json={"decision": "rejected"}, headers=ADMIN)
    assert r.status_code == 400
    r = client.post(
        f"/admin/verification-documents/{doc_id}/decision",
        json={"decision": "rejected", "reason": "Document unreadable"},
        headers=ADMIN,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


PNG_BYTES = b"\x89PNG\r\n\x1a\nfakepngdata"


def test_profile_saves_and_loads_new_fields(client):
    uid = _make_user(client)
    r = client.put(f"/profiles/influencer/{uid}", json={
        "display_name": "Ama K.", "headline": "Lifestyle creator", "location": "Cotonou, BJ",
        "bio": "Hi", "categories": ["fashion"], "rate_card": {}, "follower_count": 12000,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] == "Ama K."
    assert body["headline"] == "Lifestyle creator"
    # Reload returns the saved values.
    got = client.get(f"/profiles/influencer/{uid}").json()
    assert got["display_name"] == "Ama K."
    assert got["location"] == "Cotonou, BJ"


def test_saving_without_avatar_keeps_the_existing_one(client):
    """The onboarding wizard does not send avatar_media_id. Omitting the field
    must not delete the avatar that enrichment downloaded from YouTube."""
    uid = _make_user(client)
    media_id = client.post(f"/profiles/{uid}/media", files={"file": ("a.png", PNG_BYTES, "image/png")}).json()["id"]
    client.put(f"/profiles/influencer/{uid}", json={
        "display_name": "Ama K.", "avatar_media_id": media_id,
        "bio": "Hi", "categories": ["fashion"], "rate_card": {},
    })
    # A save that never mentions the avatar leaves it alone.
    r = client.put(f"/profiles/influencer/{uid}", json={
        "display_name": "Ama K.", "bio": "Hi again", "categories": ["fashion"], "rate_card": {},
    })
    assert r.status_code == 200
    assert r.json()["avatar_media_id"] == media_id
    assert client.get(f"/profiles/influencer/{uid}").json()["avatar_url"] == f"/profiles/media/{media_id}"


def test_explicit_null_avatar_still_clears_it(client):
    """Omission is a no-op, but an explicit null is how a creator removes their
    photo, so that must keep working."""
    uid = _make_user(client)
    media_id = client.post(f"/profiles/{uid}/media", files={"file": ("a.png", PNG_BYTES, "image/png")}).json()["id"]
    client.put(f"/profiles/influencer/{uid}", json={
        "avatar_media_id": media_id, "bio": "Hi", "categories": ["fashion"], "rate_card": {},
    })
    r = client.put(f"/profiles/influencer/{uid}", json={
        "avatar_media_id": None, "bio": "Hi", "categories": ["fashion"], "rate_card": {},
    })
    assert r.status_code == 200
    assert r.json()["avatar_media_id"] is None
    assert r.json()["avatar_url"] is None


def test_saving_without_bio_fr_keeps_the_existing_one(client):
    """Same class of bug as the avatar: a form that only knows the legacy `bio`
    column must not wipe the bilingual bios."""
    uid = _make_user(client)
    client.put(f"/profiles/influencer/{uid}", json={
        "bio_fr": "Bonjour, je suis créatrice à Cotonou.", "categories": ["fashion"], "rate_card": {"post": 100},
    })
    r = client.put(f"/profiles/influencer/{uid}", json={
        "bio": "Hi", "categories": ["fashion"], "rate_card": {"post": 100},
    })
    assert r.status_code == 200
    assert r.json()["bio_fr"] == "Bonjour, je suis créatrice à Cotonou."


def test_media_upload_and_serve(client):
    uid = _make_user(client)
    up = client.post(f"/profiles/{uid}/media", files={"file": ("a.png", PNG_BYTES, "image/png")})
    assert up.status_code == 201
    media_id = up.json()["id"]
    assert up.json()["url"] == f"/profiles/media/{media_id}"
    served = client.get(f"/profiles/media/{media_id}")
    assert served.status_code == 200
    assert served.content == PNG_BYTES
    assert served.headers["content-type"].startswith("image/png")


def test_media_rejects_non_image(client):
    uid = _make_user(client)
    r = client.post(f"/profiles/{uid}/media", files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_package_crud(client):
    uid = _make_user(client)
    created = client.post(f"/profiles/{uid}/packages", json={
        "platform": "instagram", "deliverable_type": "reel", "title": "1 IG Reel",
        "description": "A 30s reel", "price_amount": 50000, "currency": "xof",
    })
    assert created.status_code == 201
    pkg = created.json()
    assert pkg["currency"] == "XOF"  # normalized
    assert pkg["is_active"] is True
    # List
    assert len(client.get(f"/profiles/{uid}/packages").json()) == 1
    # Update
    upd = client.put(f"/profiles/{uid}/packages/{pkg['id']}", json={
        "platform": "instagram", "deliverable_type": "reel", "title": "1 IG Reel",
        "price_amount": 60000, "currency": "XOF", "is_active": False,
    })
    assert upd.json()["price_amount"] == 60000
    assert upd.json()["is_active"] is False
    # active_only filter hides it
    assert client.get(f"/profiles/{uid}/packages?active_only=true").json() == []
    # Delete
    assert client.delete(f"/profiles/{uid}/packages/{pkg['id']}").status_code == 204
    assert client.get(f"/profiles/{uid}/packages").json() == []


def test_package_update_requires_ownership(client):
    a = _make_user(client, phone="+22990000010")
    b = _make_user(client, phone="+22990000011")
    pkg = client.post(f"/profiles/{a}/packages", json={
        "platform": "tiktok", "deliverable_type": "video", "title": "TikTok",
        "price_amount": 40000, "currency": "XOF",
    }).json()
    r = client.put(f"/profiles/{b}/packages/{pkg['id']}", json={
        "platform": "tiktok", "deliverable_type": "video", "title": "TikTok",
        "price_amount": 1, "currency": "XOF",
    })
    assert r.status_code == 403


def test_portfolio_add_and_remove(client):
    uid = _make_user(client)
    media_id = client.post(f"/profiles/{uid}/media", files={"file": ("a.png", PNG_BYTES, "image/png")}).json()["id"]
    item = client.post(f"/profiles/{uid}/portfolio", json={"media_id": media_id})
    assert item.status_code == 201
    assert item.json()["url"] == f"/profiles/media/{media_id}"
    assert len(client.get(f"/profiles/{uid}/portfolio").json()) == 1
    assert client.delete(f"/profiles/{uid}/portfolio/{item.json()['id']}").status_code == 204
    assert client.get(f"/profiles/{uid}/portfolio").json() == []


def test_public_profile_aggregate(client):
    uid = _make_user(client)
    client.put(f"/profiles/influencer/{uid}", json={
        "display_name": "Ama K.", "bio": "Hi", "categories": ["fashion"], "rate_card": {"post": 1000},
    })
    client.post(f"/profiles/{uid}/packages", json={
        "platform": "instagram", "deliverable_type": "post", "title": "1 IG Post",
        "price_amount": 30000, "currency": "XOF",
    })
    pub = client.get(f"/profiles/influencer/{uid}/public")
    assert pub.status_code == 200
    body = pub.json()
    assert body["display_name"] == "Ama K."
    assert len(body["packages"]) == 1
    assert body["review_count"] == 0
    assert body["average_stars"] is None

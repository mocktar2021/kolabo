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
    r = client.put(f"/profiles/influencer/{uid}", json={"bio": "Creator", "categories": [], "rate_card": {}})
    assert r.status_code == 200
    body = r.json()
    assert body["completion_percent"] == 33
    assert body["is_searchable"] is False
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

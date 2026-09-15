"""Tests for Epic F (KOL-35): email delivery and unsubscribe."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.notifications import email as email_module
from app.modules.notifications import service as notif_service
from app.modules.notifications.router import router as notifications_router


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    notif_service.email_sender = email_module.LoggingEmailSender()

    app = FastAPI()
    app.include_router(notifications_router, prefix="/notifications")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _user(client, email="creator@example.com", phone=None):
    db = client.session_factory()
    try:
        u = User(phone=phone, email=email, password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add(u); db.commit(); db.refresh(u)
        return u.id
    finally:
        db.close()


def test_notify_records_in_app_and_sends_email(client):
    uid = _user(client)
    db = client.session_factory()
    notif_service.notify(db, uid, "proposal", "You have a new proposal")
    db.commit(); db.close()
    notes = client.get("/notifications/", headers=_headers(uid)).json()
    assert len(notes) == 1
    assert notif_service.email_sender.outbox[0]["target"] == "creator@example.com"


def test_an_account_with_no_address_gets_the_bell_and_no_email(client):
    """THE FALLBACK TO THE PHONE IS GONE, and this is what replaced it.

    notify() addressed to `user.email or user.phone` when the phone was the
    identity, which put a phone number into a mail API that ResendSender then
    had to learn to decline. It addresses the email and nothing else now.

    An account with no address is a row that predates the identity flip, since
    registration collects one. It still gets the in-app notification, because
    that is written before any of this, and it gets no email, because there is
    nowhere to send one. What must not happen is None reaching the sender:
    LoggingEmailSender would file it and ResendSender would post null as a
    recipient, and neither is visible from the call site.
    """
    uid = _user(client, email=None, phone="+22990000009")
    db = client.session_factory()
    notif_service.notify(db, uid, "proposal", "hi")
    db.commit(); db.close()
    assert notif_service.email_sender.outbox == []
    assert len(client.get("/notifications/", headers=_headers(uid)).json()) == 1


def test_unsubscribe_stops_non_critical_email(client):
    uid = _user(client)
    client.put("/notifications/preferences", json={"type": "proposal", "email_enabled": False}, headers=_headers(uid))
    db = client.session_factory()
    notif_service.notify(db, uid, "proposal", "muted one")
    db.commit(); db.close()
    assert notif_service.email_sender.outbox == []
    assert len(client.get("/notifications/", headers=_headers(uid)).json()) == 1


def test_critical_types_cannot_be_unsubscribed(client):
    uid = _user(client)
    r = client.put("/notifications/preferences", json={"type": "payment", "email_enabled": False}, headers=_headers(uid))
    assert r.status_code == 400
    db = client.session_factory()
    notif_service.notify(db, uid, "payment", "payment released")
    db.commit(); db.close()
    assert notif_service.email_sender.outbox[0]["type"] == "payment"


def test_mark_read(client):
    uid = _user(client)
    db = client.session_factory()
    notif_service.notify(db, uid, "proposal", "read me")
    db.commit(); db.close()
    note = client.get("/notifications/", headers=_headers(uid)).json()[0]
    assert note["is_read"] is False
    client.post(f"/notifications/{note['id']}/read", headers=_headers(uid))
    assert client.get("/notifications/", headers=_headers(uid)).json()[0]["is_read"] is True


def test_notifications_require_auth(client):
    assert client.get("/notifications/").status_code == 401

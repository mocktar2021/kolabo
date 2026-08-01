"""Disputes (KOL-37): raising one, what it freezes, and who may."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.contracts import models as contracts
from app.modules.notifications.models import Notification
from app.modules.payments import models as pay_models
from app.modules.payments import provider as provider_module
from app.modules.payments import service as pay_service
from app.modules.payments.router import router as payments_router
from app.modules.profiles import models as profiles


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

    pay_service.payment_provider = provider_module.MockProvider()

    app = FastAPI()
    app.include_router(payments_router, prefix="/payments")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


ADMIN = {"X-Admin-Id": "admin-1"}

STATEMENT = "The reel was never posted and the agreed date passed four days ago."


def _body(**overrides):
    body = {"reason": "not_delivered", "statement": STATEMENT, "media_ids": []}
    body.update(overrides)
    return body


def _user(db, phone, role):
    u = User(phone=phone, password_hash="x", country_code="BJ", role=role, is_verified=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _funded(client, amount=10000):
    """A held escrow between a business and a creator, plus a bystander."""
    db = client.session_factory()
    try:
        biz = _user(db, "+22990001001", "business")
        inf = _user(db, "+22990001002", "influencer")
        stranger = _user(db, "+22990001003", "influencer")
        c = contracts.Contract(
            campaign_id="camp-1", proposal_id="prop-1", business_user_id=biz.id,
            influencer_user_id=inf.id, language="fr", body="body", rate_amount=amount,
            rate_currency="XOF", timeline_days=7, status=contracts.SIGNED,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        ids = (biz.id, inf.id, stranger.id, c.id)
    finally:
        db.close()
    biz_id, inf_id, stranger_id, contract_id = ids
    escrow = client.post(
        "/payments/escrow/fund", json={"contract_id": contract_id}, headers=_headers(biz_id)
    ).json()
    return biz_id, inf_id, stranger_id, escrow


def _media(client, owner_id):
    db = client.session_factory()
    try:
        asset = profiles.MediaAsset(owner_user_id=owner_id, content_type="image/png", data=b"fake")
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset.id
    finally:
        db.close()


def _notices(client, user_id, type="dispute"):
    db = client.session_factory()
    try:
        return [
            n.message
            for n in db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.type == type)
            .all()
        ]
    finally:
        db.close()


def test_raising_a_dispute_freezes_the_escrow_and_starts_the_window(client):
    """The escrow freezes, the reason and statement are on record, and the
    evidence points at the image the creator already uploaded."""
    biz, inf, _, escrow = _funded(client)
    media_id = _media(client, inf)
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute",
        json=_body(reason="payment_issue", media_ids=[media_id]),
        headers=_headers(inf),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "awaiting_response"
    assert body["reason"] == "payment_issue"
    assert body["opened_by_user_id"] == inf
    assert body["attachments"] == [f"/profiles/media/{media_id}"]
    # The escrow itself is frozen, which is the whole point of raising one.
    assert body["escrow"]["status"] == "disputed"
    assert client.get(f"/payments/escrow/{escrow['id']}", headers=_headers(biz)).json()["status"] == "disputed"
    # respond_by is in the future: the window is open, nobody is queued yet.
    assert body["respond_by"] > pay_models.utcnow().isoformat()


def test_a_reason_outside_the_closed_set_is_refused(client):
    """The reason drives the admin queue and later the fraud counts. Free text
    would make both unreadable."""
    _, inf, _, escrow = _funded(client)
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute",
        json=_body(reason="i_just_do_not_like_it"),
        headers=_headers(inf),
    )
    assert r.status_code in (400, 422)


def test_a_statement_too_short_to_act_on_is_refused(client):
    _, inf, _, escrow = _funded(client)
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute",
        json=_body(statement="bad"),
        headers=_headers(inf),
    )
    assert r.status_code in (400, 422)


def test_someone_elses_image_cannot_be_attached(client):
    """Attaching an image you do not own would leak it into the dispute: the
    other party and every admin who reads the case would see it."""
    _, inf, stranger, escrow = _funded(client)
    theirs = _media(client, stranger)
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute",
        json=_body(media_ids=[theirs]),
        headers=_headers(inf),
    )
    assert r.status_code == 403
    # Nothing was written: the escrow is still held.
    assert client.get(f"/payments/escrow/{escrow['id']}", headers=_headers(inf)).json()["status"] == "held"


def test_a_third_party_cannot_raise_a_dispute(client):
    _, _, stranger, escrow = _funded(client)
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute", json=_body(), headers=_headers(stranger)
    )
    assert r.status_code == 403


def test_a_released_escrow_has_nothing_left_to_freeze(client):
    """The payout has already been made at the provider. Answering 200 would
    tell a creator their money was stopped when it was not."""
    biz, inf, _, escrow = _funded(client)
    assert client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz)).status_code == 200
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute", json=_body(), headers=_headers(inf)
    )
    assert r.status_code == 400


def test_a_second_dispute_on_the_same_escrow_is_a_conflict(client):
    biz, inf, _, escrow = _funded(client)
    assert client.post(
        f"/payments/escrow/{escrow['id']}/dispute", json=_body(), headers=_headers(inf)
    ).status_code == 201
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute", json=_body(), headers=_headers(biz)
    )
    assert r.status_code == 409


def test_the_other_party_is_notified_and_told_about_the_window(client):
    """That message, not an admin, is what usually ends the dispute."""
    biz, inf, _, escrow = _funded(client)
    client.post(f"/payments/escrow/{escrow['id']}/dispute", json=_body(), headers=_headers(inf))
    told = _notices(client, biz)
    assert len(told) == 1
    assert "72 hours" in told[0]
    # The opener is told too, so both sides know the money is frozen.
    assert len(_notices(client, inf)) == 1

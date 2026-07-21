"""Tests for Epic A (KOL-1): auth registration, verification, login, reset."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.modules.auth import models
from app.modules.auth.router import router as auth_router

PHONE = "+22990000001"
PASSWORD = "strongpass1"


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
    app.include_router(auth_router, prefix="/auth")
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    test_client.session_factory = testing_session
    return test_client


def _register(client, phone=PHONE, country="BJ", role="influencer", password=PASSWORD):
    return client.post(
        "/auth/register",
        json={"phone": phone, "password": password, "country_code": country, "role": role},
    )


def _latest_code(client, phone=PHONE):
    db = client.session_factory()
    try:
        user = db.query(models.User).filter(models.User.phone == phone).first()
        challenge = (
            db.query(models.OtpChallenge)
            .filter(models.OtpChallenge.user_id == user.id)
            .order_by(models.OtpChallenge.created_at.desc())
            .first()
        )
        return challenge.code
    finally:
        db.close()


def test_register_creates_unverified_account_and_blocks_login(client):
    assert _register(client).status_code == 201
    resp = client.post("/auth/login", json={"phone": PHONE, "password": PASSWORD})
    assert resp.status_code == 403


def test_country_must_be_enabled(client):
    # Nigeria is present in config but not enabled at pilot.
    assert _register(client, country="NG").status_code == 400


def test_invalid_role_rejected(client):
    assert _register(client, role="astronaut").status_code == 400


def test_verify_then_login_returns_token(client):
    _register(client)
    code = _latest_code(client)
    resp = client.post("/auth/verify-otp", json={"phone": PHONE, "code": code})
    assert resp.status_code == 200
    assert resp.json()["access_token"]
    resp = client.post("/auth/login", json={"phone": PHONE, "password": PASSWORD})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_wrong_otp_rejected(client):
    _register(client)
    resp = client.post("/auth/verify-otp", json={"phone": PHONE, "code": "000000"})
    assert resp.status_code == 401


def test_duplicate_verified_phone_blocked(client):
    _register(client)
    code = _latest_code(client)
    client.post("/auth/verify-otp", json={"phone": PHONE, "code": code})
    assert _register(client).status_code == 409


def test_password_reset_rate_limited_to_three_per_hour(client):
    _register(client)
    for _ in range(3):
        assert client.post("/auth/password-reset/request", json={"phone": PHONE}).status_code == 202
    assert client.post("/auth/password-reset/request", json={"phone": PHONE}).status_code == 429


def test_password_reset_confirm_updates_password(client):
    _register(client)
    code = _latest_code(client)
    client.post("/auth/verify-otp", json={"phone": PHONE, "code": code})
    client.post("/auth/password-reset/request", json={"phone": PHONE})

    db = client.session_factory()
    token = db.query(models.PasswordResetToken).first().token
    db.close()

    resp = client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": "newstrongpass2"},
    )
    assert resp.status_code == 200
    resp = client.post("/auth/login", json={"phone": PHONE, "password": "newstrongpass2"})
    assert resp.status_code == 200


def test_reset_request_for_unknown_phone_is_generic(client):
    resp = client.post("/auth/password-reset/request", json={"phone": "+22999999999"})
    assert resp.status_code == 202

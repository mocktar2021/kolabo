"""Tests for the account a user owns: settings, and the way back in.

Two groups, both about the same credential pair. Changing the login phone or
the password from inside a session must cost the current password, because a
bearer token only proves a session exists. Getting back in from outside must
cost possession of the phone, and must never disclose whether a number is
registered to somebody who is merely asking.
"""
from datetime import timedelta

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
OTHER_PHONE = "+22990000002"
FREE_PHONE = "+22990000003"
PASSWORD = "strongpass1"
NEW_PASSWORD = "newstrongpass2"


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    # notify() writes a Notification row on every password change, so the
    # whole metadata has to exist and not just auth's tables.
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


def _latest_otp(client, phone=PHONE):
    db = client.session_factory()
    try:
        user = db.query(models.User).filter(models.User.phone == phone).first()
        return (
            db.query(models.OtpChallenge)
            .filter(models.OtpChallenge.user_id == user.id)
            .order_by(models.OtpChallenge.created_at.desc())
            .first()
            .code
        )
    finally:
        db.close()


def _verified_token(client, phone=PHONE, role="influencer"):
    _register(client, phone=phone, role=role)
    client.post("/auth/verify-otp", json={"phone": phone, "code": _latest_otp(client, phone)})
    return client.post("/auth/login", json={"phone": phone, "password": PASSWORD}).json()[
        "access_token"
    ]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _reset_code(client, phone=PHONE):
    """The newest reset code for a phone, read straight from the table.

    The sender is a logging stub, so the database is where the code is legible
    to a test. It is stored on the token column, which now holds a six digit
    OTP rather than a urlsafe string.
    """
    db = client.session_factory()
    try:
        user = db.query(models.User).filter(models.User.phone == phone).first()
        return (
            db.query(models.PasswordResetToken)
            .filter(models.PasswordResetToken.user_id == user.id)
            .order_by(models.PasswordResetToken.created_at.desc())
            .first()
            .token
        )
    finally:
        db.close()


# --------------------------------------------------------------------------
# Reading your own account
# --------------------------------------------------------------------------


def test_me_returns_the_callers_own_account_and_never_the_hash(client):
    token = _verified_token(client)
    body = client.get("/auth/me", headers=_headers(token)).json()
    assert body["phone"] == PHONE
    assert body["role"] == "influencer"
    assert body["country_code"] == "BJ"
    assert body["is_verified"] is True
    assert body["created_at"]
    # A hash is not a display value. Shipping one gives whoever stole the
    # session something to crack offline at leisure.
    assert "password_hash" not in body
    assert "password" not in body


def test_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 401


# --------------------------------------------------------------------------
# Changing the phone: the login identity, so it costs the password
# --------------------------------------------------------------------------


def test_phone_change_requires_the_current_password(client):
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": "not-the-password", "phone": FREE_PHONE},
        headers=_headers(token),
    )
    assert r.status_code == 403
    # And the number really did not move: a stolen token must not be able to
    # point the account at a handset the thief owns.
    assert client.get("/auth/me", headers=_headers(token)).json()["phone"] == PHONE


def test_phone_change_with_the_password_works_and_logs_in_on_the_new_number(client):
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "phone": FREE_PHONE},
        headers=_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["phone"] == FREE_PHONE
    # The phone IS the login identity, so the change has to be visible there.
    assert client.post(
        "/auth/login", json={"phone": FREE_PHONE, "password": PASSWORD}
    ).status_code == 200
    assert client.post(
        "/auth/login", json={"phone": PHONE, "password": PASSWORD}
    ).status_code == 401


def test_taking_a_phone_already_in_use_is_409(client):
    token = _verified_token(client)
    _register(client, phone=OTHER_PHONE)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "phone": OTHER_PHONE},
        headers=_headers(token),
    )
    assert r.status_code == 409
    assert client.get("/auth/me", headers=_headers(token)).json()["phone"] == PHONE


def test_patch_with_neither_field_is_refused(client):
    token = _verified_token(client)
    r = client.patch("/auth/me", json={"current_password": PASSWORD}, headers=_headers(token))
    assert r.status_code == 400


# --------------------------------------------------------------------------
# Changing the password
# --------------------------------------------------------------------------


def test_password_change_requires_the_current_one(client):
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": "wrong", "new_password": NEW_PASSWORD},
        headers=_headers(token),
    )
    assert r.status_code == 403
    assert client.post(
        "/auth/login", json={"phone": PHONE, "password": PASSWORD}
    ).status_code == 200


def test_password_change_takes_effect(client):
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=_headers(token),
    )
    assert r.status_code == 200
    assert "password_hash" not in r.json()
    assert client.post(
        "/auth/login", json={"phone": PHONE, "password": NEW_PASSWORD}
    ).status_code == 200
    assert client.post(
        "/auth/login", json={"phone": PHONE, "password": PASSWORD}
    ).status_code == 401


def test_new_password_holds_the_registration_minimum(client):
    """A reset or a change must never be a way to walk an account DOWN to a
    weaker password than registration would have accepted."""
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "new_password": "short"},
        headers=_headers(token),
    )
    assert r.status_code == 422


# --------------------------------------------------------------------------
# Getting back in
# --------------------------------------------------------------------------


def test_reset_with_a_valid_code_works_and_the_code_is_single_use(client):
    _verified_token(client)
    assert client.post("/auth/password-reset/request", json={"phone": PHONE}).status_code == 202
    code = _reset_code(client)

    r = client.post(
        "/auth/password-reset/confirm",
        json={"phone": PHONE, "code": code, "new_password": NEW_PASSWORD},
    )
    assert r.status_code == 200
    assert client.post(
        "/auth/login", json={"phone": PHONE, "password": NEW_PASSWORD}
    ).status_code == 200

    # Spent. Replaying it must not walk the password somewhere else — an SMS
    # sits readable on a lock screen long after it was used.
    again = client.post(
        "/auth/password-reset/confirm",
        json={"phone": PHONE, "code": code, "new_password": "thirdpassword3"},
    )
    assert again.status_code == 400
    assert client.post(
        "/auth/login", json={"phone": PHONE, "password": NEW_PASSWORD}
    ).status_code == 200


def test_an_expired_code_is_400(client):
    _verified_token(client)
    client.post("/auth/password-reset/request", json={"phone": PHONE})
    code = _reset_code(client)

    # Aged past its lifetime rather than slept through: what is under test is
    # the expiry check, not the clock.
    db = client.session_factory()
    try:
        row = db.query(models.PasswordResetToken).first()
        row.expires_at = models.utcnow() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    r = client.post(
        "/auth/password-reset/confirm",
        json={"phone": PHONE, "code": code, "new_password": NEW_PASSWORD},
    )
    assert r.status_code == 400
    assert client.post(
        "/auth/login", json={"phone": PHONE, "password": PASSWORD}
    ).status_code == 200


def test_a_wrong_code_is_400(client):
    _verified_token(client)
    client.post("/auth/password-reset/request", json={"phone": PHONE})
    r = client.post(
        "/auth/password-reset/confirm",
        json={"phone": PHONE, "code": "000000", "new_password": NEW_PASSWORD},
    )
    assert r.status_code == 400


def test_an_unknown_phone_answers_exactly_what_a_known_one_does(client):
    """The whole security property of the request endpoint.

    Two different answers would turn this into a free "is this number
    registered on Kolabo?" lookup for anyone holding a list of phone numbers,
    which in these markets discloses who is earning on the platform to exactly
    the people a user may be trying not to be found by.
    """
    _verified_token(client)
    known = client.post("/auth/password-reset/request", json={"phone": PHONE})
    unknown = client.post("/auth/password-reset/request", json={"phone": "+22999999999"})

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()

    # And nothing was written for the number nobody has.
    db = client.session_factory()
    try:
        assert db.query(models.PasswordResetToken).count() == 1
    finally:
        db.close()


def test_the_request_rate_limit_trips(client):
    """Every request sends an SMS and every SMS costs money, so an uncapped
    endpoint is a bill a stranger can run up on us in a loop."""
    _verified_token(client)
    for _ in range(3):
        assert client.post("/auth/password-reset/request", json={"phone": PHONE}).status_code == 202
    assert client.post("/auth/password-reset/request", json={"phone": PHONE}).status_code == 429


def test_confirming_retires_the_other_outstanding_codes(client):
    """The account has just changed hands back to whoever holds the phone.
    Leaving the other live codes usable would leave two more chances for
    whoever prompted the reset in the first place."""
    _verified_token(client)
    client.post("/auth/password-reset/request", json={"phone": PHONE})
    first = _reset_code(client)
    client.post("/auth/password-reset/request", json={"phone": PHONE})
    second = _reset_code(client)

    assert client.post(
        "/auth/password-reset/confirm",
        json={"phone": PHONE, "code": second, "new_password": NEW_PASSWORD},
    ).status_code == 200

    db = client.session_factory()
    try:
        # Both rows are spent, not just the one that was used. Two six digit
        # codes can collide, so the assertion is about the rows rather than
        # about replaying the first code.
        assert db.query(models.PasswordResetToken).filter(
            models.PasswordResetToken.consumed.is_(False)
        ).count() == 0
    finally:
        db.close()
    assert first is not None

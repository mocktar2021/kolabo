"""Tests for the account a user owns: settings, and the way back in.

Two groups, both about the same credential pair. Changing the login email or
the password from inside a session must cost the current password, because a
bearer token only proves a session exists. Getting back in from outside must
cost possession of the mailbox, and must never disclose whether an address is
registered to somebody who is merely asking.

THE PHONE IS STILL HERE AND IS NO LONGER A CREDENTIAL. Registration does not
ask for one, so every account in this file starts with none; what the phone
tests below now check is that the settings screen can ADD one and that doing so
still costs the password, which it does for the reasons update_me sets out.
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
from app.modules.profiles.models import BusinessProfile, InfluencerProfile

EMAIL = "ama@example.com"
OTHER_EMAIL = "kofi@example.com"
FREE_EMAIL = "yaa@example.com"
NEW_PHONE = "+22990000003"
TAKEN_PHONE = "+22990000002"
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


def _register(client, email=EMAIL, country="BJ", role="influencer", password=PASSWORD):
    return client.post(
        "/auth/register",
        json={"email": email, "password": password, "country_code": country, "role": role},
    )


def _latest_otp(client, email=EMAIL):
    db = client.session_factory()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        return (
            db.query(models.OtpChallenge)
            .filter(models.OtpChallenge.user_id == user.id)
            .order_by(models.OtpChallenge.created_at.desc())
            .first()
            .code
        )
    finally:
        db.close()


def _verified_token(client, email=EMAIL, role="influencer"):
    _register(client, email=email, role=role)
    client.post("/auth/verify-otp", json={"email": email, "code": _latest_otp(client, email)})
    return client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()[
        "access_token"
    ]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _user_id(client, email=EMAIL):
    db = client.session_factory()
    try:
        return db.query(models.User).filter(models.User.email == email).first().id
    finally:
        db.close()


def _influencer_profile(client, email=EMAIL, display_name=None, avatar_media_id=None):
    """The creator's own public identity, which is what their nav shows them."""
    db = client.session_factory()
    try:
        db.add(
            InfluencerProfile(
                user_id=_user_id(client, email),
                display_name=display_name,
                avatar_media_id=avatar_media_id,
            )
        )
        db.commit()
    finally:
        db.close()


def _business_profile(client, email=EMAIL, company_name="Maison Kola"):
    db = client.session_factory()
    try:
        db.add(BusinessProfile(user_id=_user_id(client, email), company_name=company_name))
        db.commit()
    finally:
        db.close()


def _reset_code(client, email=EMAIL):
    """The newest reset code for an account, read straight from the table.

    The sender is a logging stub, so the database is where the code is legible
    to a test. It is stored on the token column, which now holds a six digit
    OTP rather than a urlsafe string.
    """
    db = client.session_factory()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
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
    assert body["email"] == EMAIL
    # Null, and a real answer: registration did not ask for one.
    assert body["phone"] is None
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
# Who the caller is to look at: their own name and picture
# --------------------------------------------------------------------------


def test_me_carries_the_creators_own_name_and_photo(client):
    """The nav draws the signed-in user, and nothing on the users row can.

    An email address, a role and a country are not things a person recognises
    themselves by, so this is the only field the avatar button has to work
    with — and the URL is the same media route every other surface uses.
    """
    token = _verified_token(client)
    _influencer_profile(client, display_name="Ama K.", avatar_media_id="media-abc")

    body = client.get("/auth/me", headers=_headers(token)).json()
    assert body["display_name"] == "Ama K."
    assert body["avatar_url"] == "/profiles/media/media-abc"


def test_me_gives_a_business_its_company_name_and_no_avatar(client):
    """A business has a company name and no avatar anywhere in this system,
    which is the same fact the messaging inbox records when it sets a
    counterparty avatar for creators only."""
    token = _verified_token(client, role="business")
    _business_profile(client, company_name="Maison Kola")

    body = client.get("/auth/me", headers=_headers(token)).json()
    assert body["display_name"] == "Maison Kola"
    assert body["avatar_url"] is None


def test_me_is_two_nulls_and_not_a_500_without_any_profile(client):
    """Somebody who has just signed up has written no profile yet, and that is
    a real answer rather than an error. It must never fall back to the users
    table: the only human-readable column there is the email address."""
    token = _verified_token(client)

    r = client.get("/auth/me", headers=_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] is None
    assert body["avatar_url"] is None


def test_a_creator_profile_with_no_name_yet_does_not_borrow_one(client):
    """A profile row that exists still wins the precedence, blank or not.
    Falling through would show somebody a name they never chose."""
    token = _verified_token(client)
    _influencer_profile(client, display_name=None, avatar_media_id=None)

    body = client.get("/auth/me", headers=_headers(token)).json()
    assert body["display_name"] is None
    assert body["avatar_url"] is None


def test_the_patch_response_carries_the_name_too(client):
    """PATCH answers with the same shape GET does, so a client that re-renders
    the nav from the response of a settings save does not blank the avatar."""
    token = _verified_token(client)
    _influencer_profile(client, display_name="Ama K.", avatar_media_id="media-abc")

    body = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": FREE_EMAIL},
        headers=_headers(token),
    ).json()
    assert body["email"] == FREE_EMAIL
    assert body["display_name"] == "Ama K."
    assert body["avatar_url"] == "/profiles/media/media-abc"


# --------------------------------------------------------------------------
# Changing the email: the login identity, so it costs the password
# --------------------------------------------------------------------------


def test_email_change_requires_the_current_password(client):
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": "not-the-password", "email": FREE_EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 403
    # And the address really did not move: a stolen token must not be able to
    # point the account at a mailbox the thief owns and then reset from it.
    assert client.get("/auth/me", headers=_headers(token)).json()["email"] == EMAIL


def test_email_change_with_the_password_works_and_logs_in_on_the_new_address(client):
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": FREE_EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["email"] == FREE_EMAIL
    # The email IS the login identity, so the change has to be visible there.
    assert client.post(
        "/auth/login", json={"email": FREE_EMAIL, "password": PASSWORD}
    ).status_code == 200
    assert client.post(
        "/auth/login", json={"email": EMAIL, "password": PASSWORD}
    ).status_code == 401


def test_taking_an_email_already_in_use_is_409(client):
    token = _verified_token(client)
    _register(client, email=OTHER_EMAIL)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": OTHER_EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 409
    assert client.get("/auth/me", headers=_headers(token)).json()["email"] == EMAIL


# --------------------------------------------------------------------------
# Adding a phone: not a credential any more, still costs the password
# --------------------------------------------------------------------------


def test_this_patch_is_how_an_account_gets_a_phone_at_all(client):
    """Registration stopped asking for one, so the settings screen is the only
    place a number ever arrives from. A brand needs it on file before their
    number reaches the FedaPay customer object at checkout."""
    token = _verified_token(client)
    assert client.get("/auth/me", headers=_headers(token)).json()["phone"] is None

    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "phone": NEW_PHONE},
        headers=_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["phone"] == NEW_PHONE
    assert client.get("/auth/me", headers=_headers(token)).json()["phone"] == NEW_PHONE
    # And it is not a credential: the address is still what logs in.
    assert client.post(
        "/auth/login", json={"email": EMAIL, "password": PASSWORD}
    ).status_code == 200


def test_adding_a_phone_still_costs_the_current_password(client):
    """It moves what a checkout is filed under and what support calls back on,
    which is worth more than a bearer token proves."""
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": "not-the-password", "phone": NEW_PHONE},
        headers=_headers(token),
    )
    assert r.status_code == 403
    assert client.get("/auth/me", headers=_headers(token)).json()["phone"] is None


def test_taking_a_phone_another_account_holds_is_still_409(client):
    """The unique index went with the identity (f3c0a84e17d9), so this refusal
    is now the whole of the rule rather than a friendlier spelling of a
    constraint. It has to keep working on its own."""
    token = _verified_token(client)
    other = _verified_token(client, email=OTHER_EMAIL)
    assert client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "phone": TAKEN_PHONE},
        headers=_headers(other),
    ).status_code == 200

    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "phone": TAKEN_PHONE},
        headers=_headers(token),
    )
    assert r.status_code == 409
    # The status and not the `code`. This file's client is a bare FastAPI()
    # with no app_error_handler on it, so AppError falls through to FastAPI's
    # own handler and the body carries `detail` alone — see the fixture in
    # test_auth.py, which registers the real one because its assertions need
    # it. Adding it here would be a change to every test in this file for one
    # assertion that the status already makes.
    assert client.get("/auth/me", headers=_headers(token)).json()["phone"] is None


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
        "/auth/login", json={"email": EMAIL, "password": PASSWORD}
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
        "/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD}
    ).status_code == 200
    assert client.post(
        "/auth/login", json={"email": EMAIL, "password": PASSWORD}
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
    assert client.post("/auth/password-reset/request", json={"email": EMAIL}).status_code == 202
    code = _reset_code(client)

    r = client.post(
        "/auth/password-reset/confirm",
        json={"email": EMAIL, "code": code, "new_password": NEW_PASSWORD},
    )
    assert r.status_code == 200
    assert client.post(
        "/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD}
    ).status_code == 200

    # Spent. Replaying it must not walk the password somewhere else — a reset
    # email sits readable in an inbox long after it was used.
    again = client.post(
        "/auth/password-reset/confirm",
        json={"email": EMAIL, "code": code, "new_password": "thirdpassword3"},
    )
    assert again.status_code == 400
    assert client.post(
        "/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD}
    ).status_code == 200


def test_an_expired_code_is_400(client):
    _verified_token(client)
    client.post("/auth/password-reset/request", json={"email": EMAIL})
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
        json={"email": EMAIL, "code": code, "new_password": NEW_PASSWORD},
    )
    assert r.status_code == 400
    assert client.post(
        "/auth/login", json={"email": EMAIL, "password": PASSWORD}
    ).status_code == 200


def test_a_wrong_code_is_400(client):
    _verified_token(client)
    client.post("/auth/password-reset/request", json={"email": EMAIL})
    r = client.post(
        "/auth/password-reset/confirm",
        json={"email": EMAIL, "code": "000000", "new_password": NEW_PASSWORD},
    )
    assert r.status_code == 400


def test_an_unknown_address_answers_exactly_what_a_known_one_does(client):
    """The whole security property of the request endpoint.

    Two different answers would turn this into a free "is this address
    registered on Kolabo?" lookup for anyone holding a list of addresses, which
    in these markets discloses who is earning on the platform to exactly the
    people a user may be trying not to be found by.
    """
    _verified_token(client)
    known = client.post("/auth/password-reset/request", json={"email": EMAIL})
    unknown = client.post("/auth/password-reset/request", json={"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()

    # And nothing was written for the address nobody has.
    db = client.session_factory()
    try:
        assert db.query(models.PasswordResetToken).count() == 1
    finally:
        db.close()


def test_the_request_rate_limit_trips(client):
    """Every request sends a message and every message costs something, so an
    uncapped endpoint is a bill a stranger can run up on us in a loop."""
    _verified_token(client)
    for _ in range(3):
        assert client.post("/auth/password-reset/request", json={"email": EMAIL}).status_code == 202
    assert client.post("/auth/password-reset/request", json={"email": EMAIL}).status_code == 429


def test_a_reset_is_found_whatever_case_the_address_is_typed_in(client):
    """Silence is this endpoint's failure mode, so the one thing it must get
    right is finding the row. An address typed with a capital that resolved to
    nobody would answer the same cheerful 202, send nothing, and leave somebody
    waiting for a code that is never coming."""
    _verified_token(client)
    assert client.post(
        "/auth/password-reset/request", json={"email": "AMA@Example.COM"}
    ).status_code == 202
    code = _reset_code(client)
    assert client.post(
        "/auth/password-reset/confirm",
        json={"email": "Ama@EXAMPLE.com", "code": code, "new_password": NEW_PASSWORD},
    ).status_code == 200
    assert client.post(
        "/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD}
    ).status_code == 200


def test_confirming_retires_the_other_outstanding_codes(client):
    """The account has just changed hands back to whoever holds the mailbox.
    Leaving the other live codes usable would leave two more chances for
    whoever prompted the reset in the first place."""
    _verified_token(client)
    client.post("/auth/password-reset/request", json={"email": EMAIL})
    first = _reset_code(client)
    client.post("/auth/password-reset/request", json={"email": EMAIL})
    second = _reset_code(client)

    assert client.post(
        "/auth/password-reset/confirm",
        json={"email": EMAIL, "code": second, "new_password": NEW_PASSWORD},
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

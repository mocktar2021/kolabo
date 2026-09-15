"""An account can now HOLD an email address. It still logs in with a phone.

That distinction is the whole point of this file, so it is worth stating before
the tests rather than after. Nothing here signs in with an address, nothing
resets a password to one, and /auth/register is untouched: the phone is still
the login identity and the identity move is a later change. What is new is a
column somebody can put an address in, a sentence for the two ways that can go
wrong, and the rule that an address on one account is not available to another.

Same shape as test_account.py, deliberately, including its fixture: these are
the same endpoint and the same credential rule, and a second way of standing a
client up would be a second thing to fix the day the first one changes.

THE PRICE IS THE CURRENT PASSWORD, like every other credential change here. It
is not the login identity today, which is exactly why it is worth saying out
loud why it costs the same: whatever address is in this column on the day the
identity moves becomes the way back into the account, so a stolen session that
could set it quietly would be a takeover on a delay.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.errors import AppError, app_error_handler
from app.modules.auth import models
from app.modules.auth.router import router as auth_router

PHONE = "+22990000021"
OTHER_PHONE = "+22990000022"
PASSWORD = "strongpass1"

EMAIL = "ama@example.com"
OTHER_EMAIL = "kofi@example.com"


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    # notify() writes a Notification row on every password change, so the whole
    # metadata has to exist and not just auth's tables.
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
    # The REAL error handler, for the reason test_auth.py registers it: every
    # refusal below is asserted by its `code`, and AppError subclasses
    # HTTPException, so without this FastAPI's own handler renders
    # {"detail": ...} alone and each assertion fails on a missing key rather
    # than on a wrong answer. Registering the real one rather than a lookalike
    # is what makes these tests evidence about the wiring in main.py.
    app.add_exception_handler(AppError, app_error_handler)
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


def _put_email_on(client, phone, email):
    """Give another account an address, without going through the endpoint.

    The conflict this file cares about is "somebody else already holds it", and
    how they came to hold it is not part of that question. Writing the column
    directly keeps the test about the refusal rather than about a second
    account's whole signup.
    """
    db = client.session_factory()
    try:
        user = db.query(models.User).filter(models.User.phone == phone).first()
        user.email = email
        db.commit()
    finally:
        db.close()


def _me(client, token):
    return client.get("/auth/me", headers=_headers(token)).json()


# --------------------------------------------------------------------------
# Putting an address on your own account
# --------------------------------------------------------------------------


def test_a_new_account_has_no_email_and_that_is_a_real_answer(client):
    """Null, not absent and not a 500. An email is optional on this platform,
    so almost every row has none, and the field has to be readable anyway or
    nobody can tell whether theirs saved."""
    token = _verified_token(client)
    body = _me(client, token)
    assert "email" in body
    assert body["email"] is None
    # The phone is still what this account IS. Nothing about adding an email
    # column changes that, and this PR does not pretend otherwise.
    assert body["phone"] == PHONE


def test_setting_an_email_works_and_comes_back_on_me(client):
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL
    # And it is on the account rather than only in the response of the write:
    # a settings screen reads it back on the next page load.
    assert _me(client, token)["email"] == EMAIL


def test_the_domain_is_lowercased_and_the_local_part_is_not(client):
    """The one normalisation this system performs on an address, asserted end
    to end rather than only in the unit test, because it is the storage rule
    the unique index depends on. The local part is formally case sensitive and
    is left exactly as typed; the domain is not, so it is settled once here
    instead of at every comparison."""
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": "Ama.K@EXAMPLE.COM"},
        headers=_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["email"] == "Ama.K@example.com"
    assert _me(client, token)["email"] == "Ama.K@example.com"


def test_an_address_is_trimmed_before_it_is_stored(client):
    """A pasted address arrives with a space on it more often than not, and a
    stored leading space is an address no send would ever reach."""
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": "  ama@example.com  "},
        headers=_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL


# --------------------------------------------------------------------------
# The two ways it is refused
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "typed",
    [
        "notanemail",
        "ama@",
        "@example.com",
        "ama @example.com",
        # A phone number in the email field, which is the mistake this
        # particular product is most likely to collect.
        "+22990000021",
        "",
    ],
)
def test_an_address_that_is_not_one_is_refused_by_name(client, typed):
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": typed},
        headers=_headers(token),
    )
    assert r.status_code == 400
    # The code, not the English. The client renders its own sentence from it in
    # French or English — see auth_email_invalid in errorMessages.ts.
    assert r.json()["code"] == "auth_email_invalid"
    # And nothing was written on the way to the refusal.
    assert _me(client, token)["email"] is None


def test_an_address_already_on_another_account_is_409(client):
    token = _verified_token(client)
    _register(client, phone=OTHER_PHONE)
    _put_email_on(client, OTHER_PHONE, OTHER_EMAIL)

    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": OTHER_EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 409
    assert r.json()["code"] == "auth_email_taken"
    assert _me(client, token)["email"] is None


def test_the_conflict_is_decided_on_the_normalised_spelling(client):
    """Otherwise one spelling looks free while another is taken, and the unique
    index turns a clear 409 into a 500 on the write that finds out.

    THE DOMAIN IS THE HALF THAT VARIES HERE, and it has to be. Normalisation
    lowercases the domain and deliberately leaves the local part exactly as it
    was typed (core/emails.py says why at length, and test_email_guard.py pins
    it with "AMA@EXAMPLE.COM" -> "AMA@example.com"). So "KOFI@example.com" and
    "kofi@example.com" are two different addresses on purpose: neither the
    lookup below nor the unique index behind it would treat them as one, and a
    test that asked for a 409 on that pair would be asking for the rule to be
    broken rather than checking it. Changing only the case of the domain is
    what exercises the thing this test is named for, because it is the only
    half where the stored value and the typed value legitimately differ.
    """
    token = _verified_token(client)
    _register(client, phone=OTHER_PHONE)
    _put_email_on(client, OTHER_PHONE, OTHER_EMAIL)

    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": "kofi@EXAMPLE.COM"},
        headers=_headers(token),
    )
    assert r.status_code == 409
    assert r.json()["code"] == "auth_email_taken"


def test_an_unverified_registration_still_holds_its_address(client):
    """Verified or not, a row that claims an address holds it. Letting a
    verified account take it would displace somebody who half signed up, and
    would collide on the unique index anyway."""
    token = _verified_token(client)
    # Registered and never verified, exactly as the phone rule above it.
    _register(client, phone=OTHER_PHONE)
    _put_email_on(client, OTHER_PHONE, OTHER_EMAIL)

    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": OTHER_EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 409


def test_resending_your_own_address_is_not_a_conflict(client):
    """A settings form posts every field it has, including the one that did not
    change. Answering 409 to somebody's own address would make saving a phone
    number impossible for anybody who already had an email."""
    token = _verified_token(client)
    client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": EMAIL},
        headers=_headers(token),
    )
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL


# --------------------------------------------------------------------------
# The price
# --------------------------------------------------------------------------


def test_setting_an_email_requires_the_current_password(client):
    """A bearer token says a session exists. Only the password says the owner
    is the one asking, and this column is where a reset will be sent the day
    the identity moves."""
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": "not-the-password", "email": EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 403
    assert _me(client, token)["email"] is None


def test_the_password_is_checked_before_the_address_is_looked_up(client):
    """Otherwise the endpoint is a free "does this person have a Kolabo
    account" lookup for anybody holding a stolen session and a list of
    addresses: a 409 and a 403 would tell them apart."""
    token = _verified_token(client)
    _register(client, phone=OTHER_PHONE)
    _put_email_on(client, OTHER_PHONE, OTHER_EMAIL)

    taken = client.patch(
        "/auth/me",
        json={"current_password": "not-the-password", "email": OTHER_EMAIL},
        headers=_headers(token),
    )
    free = client.patch(
        "/auth/me",
        json={"current_password": "not-the-password", "email": "nobody@example.com"},
        headers=_headers(token),
    )
    assert taken.status_code == free.status_code == 403
    assert taken.json()["code"] == free.json()["code"] == "auth_password_incorrect"


def test_an_email_and_a_phone_move_together_in_one_patch(client):
    """Both are credentials and both cost the one password, so a settings screen
    saves them in one request rather than two that can half succeed."""
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "phone": OTHER_PHONE, "email": EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["phone"] == OTHER_PHONE
    assert r.json()["email"] == EMAIL
    # The phone is still the login identity, and it really moved.
    assert client.post(
        "/auth/login", json={"phone": OTHER_PHONE, "password": PASSWORD}
    ).status_code == 200


def test_an_email_alone_is_enough_of_a_change_to_be_accepted(client):
    """auth_account_nothing_to_change now has three fields to look at, not two.
    An email on its own must not be read as an empty patch."""
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 200
    # And an empty one is still refused, with the code whose sentence now
    # mentions the address as well.
    empty = client.patch(
        "/auth/me", json={"current_password": PASSWORD}, headers=_headers(token)
    )
    assert empty.status_code == 400
    assert empty.json()["code"] == "auth_account_nothing_to_change"

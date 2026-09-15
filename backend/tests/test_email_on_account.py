"""Moving the address an account logs in with, and the two ways that can fail.

The identity move this file was written just ahead of has happened: the address
IS the login identity now, /auth/register collects one, and a reset code goes
to it. So what is left here is the SETTINGS half — changing the address of an
account that already has one — and it is worth keeping separate from
test_account.py because the rules it pins are about the address specifically:
what a valid one is, and that one account's address is not available to another.

Same shape as test_account.py, deliberately, including its fixture: these are
the same endpoint and the same credential rule, and a second way of standing a
client up would be a second thing to fix the day the first one changes.

THE PRICE IS THE CURRENT PASSWORD, like every other credential change here, and
it needs no special pleading any more: this is the address a reset code is sent
to, so a stolen session that could point it somewhere else quietly would own
the account outright a minute later.
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

PASSWORD = "strongpass1"

EMAIL = "ama@example.com"
OTHER_EMAIL = "kofi@example.com"
THIRD_EMAIL = "yaa@example.com"


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


def _unverified_holder(client, email):
    """An account that CLAIMS an address without having verified it.

    Registered and never verified, which is the state the conflict rule below
    is specifically about: a half-finished signup still holds the address it
    claimed, and a verified account must not be able to take it.
    """
    _register(client, email=email)


def _me(client, token):
    return client.get("/auth/me", headers=_headers(token)).json()


# --------------------------------------------------------------------------
# Moving the address on your own account
# --------------------------------------------------------------------------


def test_a_new_account_arrives_with_the_address_it_registered_with(client):
    """The address is what the account IS, so it is never null on a row created
    since the flip. The phone is, because registration does not ask."""
    token = _verified_token(client)
    body = _me(client, token)
    assert body["email"] == EMAIL
    assert body["phone"] is None


def test_changing_the_email_works_and_comes_back_on_me(client):
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": THIRD_EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["email"] == THIRD_EMAIL
    # And it is on the account rather than only in the response of the write:
    # a settings screen reads it back on the next page load, and the next login
    # resolves on it.
    assert _me(client, token)["email"] == THIRD_EMAIL


def test_the_whole_address_is_lowercased(client):
    """The one normalisation this system performs on an address, asserted end
    to end rather than only in the unit test, because it is the storage rule
    the unique index depends on AND the rule that makes a login work whatever
    case somebody types.

    Both halves are folded. The domain because it is case insensitive by
    standard, the local part by a decision core/emails.py argues at length: a
    formally case sensitive local part that no provider these users have
    actually distinguishes is not worth locking anybody out over."""
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": "Yaa.K@EXAMPLE.COM"},
        headers=_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["email"] == "yaa.k@example.com"
    assert _me(client, token)["email"] == "yaa.k@example.com"
    # And the folded spelling is the one that logs in, which is the point.
    assert client.post(
        "/auth/login", json={"email": "YAA.K@example.com", "password": PASSWORD}
    ).status_code == 200


def test_an_address_is_trimmed_before_it_is_stored(client):
    """A pasted address arrives with a space on it more often than not, and a
    stored leading space is an address no send would ever reach."""
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": "  yaa@example.com  "},
        headers=_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["email"] == THIRD_EMAIL


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
        # particular product is most likely to collect, and more likely than
        # ever now that the signup form asks for an address where it used to
        # ask for a number.
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
    # And nothing was written on the way to the refusal: the account still logs
    # in with the address it had.
    assert _me(client, token)["email"] == EMAIL


def test_an_address_already_on_another_account_is_409(client):
    token = _verified_token(client)
    _unverified_holder(client, OTHER_EMAIL)

    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": OTHER_EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 409
    assert r.json()["code"] == "auth_email_taken"
    assert _me(client, token)["email"] == EMAIL


def test_the_conflict_is_decided_on_the_normalised_spelling(client):
    """Otherwise one spelling looks free while another is taken, and the unique
    index turns a clear 409 into a 500 on the write that finds out.

    THE LOCAL PART IS THE HALF THAT VARIES HERE, and that is the case worth
    testing now. It used to be the domain, because the domain was the only half
    normalisation touched; folding the local part as well is the change that
    made the address safe to log in with, so "KOFI@example.com" arriving at an
    account that already holds "kofi@example.com" is exactly the collision that
    would have slipped through before and the one a reader of this test needs
    to see caught. A domain-only variation would still pass while the rule it
    is named for had been reverted.
    """
    token = _verified_token(client)
    _unverified_holder(client, OTHER_EMAIL)

    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": "KOFI@example.com"},
        headers=_headers(token),
    )
    assert r.status_code == 409
    assert r.json()["code"] == "auth_email_taken"


def test_an_unverified_registration_still_holds_its_address(client):
    """Verified or not, a row that claims an address holds it. Letting a
    verified account take it would displace somebody who half signed up, and
    would collide on ix_users_email anyway."""
    token = _verified_token(client)
    _unverified_holder(client, OTHER_EMAIL)

    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": OTHER_EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 409


def test_resending_your_own_address_is_not_a_conflict(client):
    """A settings form posts every field it has, including the one that did not
    change. Answering 409 to somebody's own address would make saving a phone
    number impossible for everybody, since every account has an address."""
    token = _verified_token(client)
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
    is the one asking, and this column is where a reset code is sent."""
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": "not-the-password", "email": THIRD_EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 403
    assert _me(client, token)["email"] == EMAIL


def test_the_password_is_checked_before_the_address_is_looked_up(client):
    """Otherwise the endpoint is a free "does this person have a Kolabo
    account" lookup for anybody holding a stolen session and a list of
    addresses: a 409 and a 403 would tell them apart."""
    token = _verified_token(client)
    _unverified_holder(client, OTHER_EMAIL)

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
    """Both cost the one password, so a settings screen saves them in one
    request rather than two that can half succeed."""
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "phone": "+22990000022", "email": THIRD_EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["phone"] == "+22990000022"
    assert r.json()["email"] == THIRD_EMAIL
    # The email is the login identity, and it really moved.
    assert client.post(
        "/auth/login", json={"email": THIRD_EMAIL, "password": PASSWORD}
    ).status_code == 200


def test_an_email_alone_is_enough_of_a_change_to_be_accepted(client):
    """auth_account_nothing_to_change now has three fields to look at, not two.
    An email on its own must not be read as an empty patch."""
    token = _verified_token(client)
    r = client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "email": THIRD_EMAIL},
        headers=_headers(token),
    )
    assert r.status_code == 200
    # And an empty one is still refused, with the code whose sentence mentions
    # the address as well.
    empty = client.patch(
        "/auth/me", json={"current_password": PASSWORD}, headers=_headers(token)
    )
    assert empty.status_code == 400
    assert empty.json()["code"] == "auth_account_nothing_to_change"

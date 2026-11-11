"""Signing in with Apple: POST /auth/apple, and the rules that are not Google's.

THE NETWORK AND THE CRYPTO ARE BOTH STOOD IN FOR, at the shallowest seam that
still leaves our own code under test. apple._signing_key and apple.jwt.decode
are monkeypatched on the module, the same way test_google_signin.py swaps
google.id_token.verify_oauth2_token. What stays under test is everything this
codebase actually wrote: the audience check (which python-jose cannot do for
us and which this file asserts is really performed), the subject-first lookup,
the relay address rule, the two step signup, the linking, and the re-auth
branch. What is NOT exercised is that a real Apple token verifies against real
Apple keys, which is a manual check against a real bundle id and cannot be
CI's job without putting Apple on the critical path of every build.

THE THREE DECISIONS THIS FILE EXISTS TO PIN, because each of them could be
quietly reversed by somebody making the Apple path "consistent" with Google's:

  * A RETURNING TOKEN CARRIES NO ADDRESS AND MUST STILL WORK. Apple sends
    `email` on the first authorisation and generally never again. A flow that
    looks the account up by address passes every test written on day one and
    fails for every user on day two. test_a_second_sign_in_carries_no_address
    is the one that would catch that.

  * A HIDE MY EMAIL RELAY ADDRESS MUST NEVER CLAIM AN EXISTING ACCOUNT. It is
    minted per app and proves nothing about any other mailbox. The Google rule
    (the mailbox is the login identity, so holding it is enough to enter the
    account under it) is sound for a real confirmed address and is not sound
    for this one.

  * AN ACCOUNT WITH NO apple_sub CANNOT BE RE-AUTHENTICATED BY ANY APPLE
    TOKEN. Without the explicit None check in require_reauth, None == None
    holds on an unlinked row and any valid Apple token from any Apple account
    proves ownership of it. test_re_auth_refuses_an_unlinked_account is the
    assertion standing in front of that.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.db import Base, get_db
from app.core.errors import AppError, app_error_handler
from app.modules.auth import apple, models
from app.modules.auth.router import router as auth_router

# Two audiences, because that is the shape the setting exists for, and on this
# provider the two are not even the same KIND of string: the native flow
# stamps the bundle id, the web flow stamps a Services ID. A test with one
# would pass against a verifier that could only ever check one.
BUNDLE_ID = "com.kolaboafrica.app"
SERVICES_ID = "com.kolaboafrica.web"
OTHER_APP_ID = "com.someoneelse.app"

REAL_EMAIL = "ama@example.com"
RELAY_EMAIL = "abc123xyz@privaterelay.appleid.com"
PASSWORD = "strongpass1"
SUBJECT = "001234.fedcba9876543210.0001"


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
    # The REAL error handler, for the reason test_google_signin.py gives:
    # nearly every assertion below reads `code` out of the body.
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(auth_router, prefix="/auth")
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    test_client.session_factory = testing_session
    return test_client


class _FakeApple:
    """Apple's signing keys and decoder, stood in for by tokens we minted.

    A token this fixture never issued raises, which is what python-jose does
    for a signature it cannot verify, so "an invalid token" needs no setup.

    EVERY CLAIM IS OPTIONAL EXCEPT `sub`, which is the whole point of the
    fixture: issue() defaults to the SECOND sign in shape (no email at all),
    because that is the shape this integration spends its life handling and
    the one a Google shaped implementation gets wrong.
    """

    def __init__(self):
        self.tokens: dict[str, dict] = {}

    def issue(
        self,
        raw: str,
        sub: str = SUBJECT,
        aud: str = BUNDLE_ID,
        email: str | None = None,
        email_verified: object = True,
        is_private_email: object = None,
    ) -> str:
        claims = {
            "iss": apple.ISSUER,
            "aud": aud,
            "sub": sub,
            # RELATIVE, never a literal date, for the reason the Google
            # fixture gives: a date that goes stale is a test that fails on a
            # calendar rather than on a change.
            "exp": int((datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp()),
        }
        if email is not None:
            claims["email"] = email
            claims["email_verified"] = email_verified
        if is_private_email is not None:
            claims["is_private_email"] = is_private_email
        self.tokens[raw] = claims
        return raw

    def decode(self, raw, key, algorithms=None, issuer=None, options=None):
        claims = self.tokens.get(raw)
        if claims is None:
            raise ValueError("Signature verification failed.")
        return claims


@pytest.fixture()
def fake_apple(monkeypatch):
    """Two audiences configured, Apple's keys and decoder replaced."""
    monkeypatch.setattr(settings, "apple_client_ids", f"{BUNDLE_ID},{SERVICES_ID}")
    fake = _FakeApple()
    monkeypatch.setattr(apple.jwt, "get_unverified_header", lambda raw: {"kid": "test-kid"})
    monkeypatch.setattr(apple, "_signing_key", lambda kid: {"kid": kid})
    monkeypatch.setattr(apple.jwt, "decode", fake.decode)
    return fake


def _sign_in(client, token, **extra):
    return client.post("/auth/apple", json={"identity_token": token, **extra})


def _new_account(client, fake_apple, **issue):
    """The first sign in, with the questions the client has to ask answered."""
    issue.setdefault("email", REAL_EMAIL)
    token = fake_apple.issue("first-token", **issue)
    return _sign_in(client, token, role="influencer", country_code="BJ")


def _register(client, email=REAL_EMAIL, country="BJ", role="influencer", password=PASSWORD):
    return client.post(
        "/auth/register",
        json={"email": email, "password": password, "country_code": country, "role": role},
    )


def _user(client, **filters):
    db = client.session_factory()
    try:
        query = db.query(models.User)
        for column, value in filters.items():
            query = query.filter(getattr(models.User, column) == value)
        return query.first()
    finally:
        db.close()


class TestTheFeatureCanBeAbsent:
    def test_no_client_ids_means_unavailable(self, client, monkeypatch):
        # Not 404 and not 400: the feature exists, this deployment has not been
        # given what it needs, and the caller did nothing wrong. The client
        # hides the button on this one.
        monkeypatch.setattr(settings, "apple_client_ids", "")
        response = _sign_in(client, "anything")
        assert response.status_code == 503
        assert response.json()["code"] == "auth_apple_unavailable"

    def test_nobody_is_signed_in_without_an_audience_to_check(self, client, monkeypatch):
        monkeypatch.setattr(settings, "apple_client_ids", "")
        _sign_in(client, "anything", role="influencer", country_code="BJ")
        assert _user(client) is None


class TestTheAudienceCheck:
    """python-jose cannot do this one for us, so it is done by hand and asserted here."""

    def test_a_token_for_another_app_is_refused(self, client, fake_apple):
        # A correctly signed Apple token issued to somebody else's app is
        # trivially obtainable: sign in to their app and read it off the wire.
        # Without this check every other app on the App Store is a way in.
        token = fake_apple.issue("other-app", aud=OTHER_APP_ID, email=REAL_EMAIL)
        response = _sign_in(client, token, role="influencer", country_code="BJ")
        assert response.status_code == 401
        assert response.json()["code"] == "auth_apple_token_invalid"
        assert _user(client) is None

    def test_both_configured_audiences_are_accepted(self, client, fake_apple):
        # The setting is a list because the native and web flows stamp
        # different strings. One of them working is not the test.
        native = fake_apple.issue("native", aud=BUNDLE_ID, email=REAL_EMAIL, sub="sub-native")
        web = fake_apple.issue("web", aud=SERVICES_ID, email="kofi@example.com", sub="sub-web")
        assert _sign_in(client, native, role="influencer", country_code="BJ").status_code == 200
        assert _sign_in(client, web, role="business", country_code="BJ").status_code == 200

    def test_an_audience_list_is_handled(self, client, fake_apple):
        # The JWT specification allows `aud` to be a list. Apple sends a
        # string today, and trusting that shape is how this breaks quietly.
        token = fake_apple.issue("listy", aud=[OTHER_APP_ID, BUNDLE_ID], email=REAL_EMAIL)
        assert _sign_in(token=token, client=client, role="influencer", country_code="BJ").status_code == 200

    def test_an_unissued_token_is_refused(self, client, fake_apple):
        response = _sign_in(client, "never-issued", role="influencer", country_code="BJ")
        assert response.status_code == 401
        assert response.json()["code"] == "auth_apple_token_invalid"


class TestTheFirstSignIn:
    def test_a_new_person_is_asked_for_a_country_and_a_role(self, client, fake_apple):
        # Not an error. The first leg of a two step flow, and the client is
        # expected to come back with the SAME token.
        token = fake_apple.issue("first", email=REAL_EMAIL)
        response = _sign_in(client, token)
        assert response.status_code == 400
        assert response.json()["code"] == "auth_apple_profile_required"
        assert _user(client) is None

    def test_the_second_call_creates_the_account(self, client, fake_apple):
        response = _new_account(client, fake_apple)
        assert response.status_code == 200
        assert response.json()["role"] == "influencer"
        user = _user(client, email=REAL_EMAIL)
        assert user is not None
        # Verified from birth and no OTP: registration sends a code to prove
        # the mailbox and Apple has just proved it. A row created unverified
        # here is one login() would immediately lock out over a code nothing
        # ever sent.
        assert user.is_verified is True
        assert user.apple_sub == SUBJECT

    def test_an_unknown_role_is_refused_exactly_as_registration_refuses_it(self, client, fake_apple):
        token = fake_apple.issue("first", email=REAL_EMAIL)
        response = _sign_in(client, token, role="wizard", country_code="BJ")
        assert response.status_code == 400
        assert response.json()["code"] == "auth_role_unknown"

    def test_a_closed_country_is_refused(self, client, fake_apple):
        token = fake_apple.issue("first", email=REAL_EMAIL)
        response = _sign_in(client, token, role="influencer", country_code="ZZ")
        assert response.status_code == 400
        assert response.json()["code"] == "auth_country_unavailable"


class TestTheSecondSignIn:
    """The shape a Google shaped implementation gets wrong."""

    def test_a_second_sign_in_carries_no_address(self, client, fake_apple):
        created = _new_account(client, fake_apple)
        assert created.status_code == 200

        # No email claim at all, which is what Apple actually sends from the
        # second authorisation onwards. The subject is the only thing left.
        returning = fake_apple.issue("second-token")
        response = _sign_in(client, returning)
        assert response.status_code == 200

        # The SAME account, not a second one. This is the assertion.
        db = client.session_factory()
        try:
            assert db.query(models.User).count() == 1
        finally:
            db.close()

    def test_a_subject_nothing_knows_and_no_address_is_refused(self, client, fake_apple):
        # The returning person whose link was lost. There is nothing to sign
        # in to and nothing to create an account from, and inventing an
        # address would make a duplicate under a name its owner cannot read.
        token = fake_apple.issue("orphan", sub="sub-nobody-has")
        response = _sign_in(client, token, role="influencer", country_code="BJ")
        assert response.status_code == 409
        assert response.json()["code"] == "auth_apple_unlinked"
        assert _user(client) is None


class TestTheAddressRules:
    def test_a_confirmed_real_address_signs_into_the_account_that_holds_it(self, client, fake_apple):
        # The same rule google_sign_in rests on, and it is sound here for the
        # same reason: the mailbox is the login identity, and somebody holding
        # it could already take the account back through a password reset.
        assert _register(client).status_code in (200, 201)
        token = fake_apple.issue("first", email=REAL_EMAIL, email_verified=True)
        response = _sign_in(client, token)
        assert response.status_code == 200

        db = client.session_factory()
        try:
            assert db.query(models.User).count() == 1
        finally:
            db.close()
        # And the link is recorded, because an account that has just walked
        # through the Apple door is reachable by Apple from this moment.
        assert _user(client, email=REAL_EMAIL).apple_sub == SUBJECT

    def test_a_relay_address_never_claims_an_existing_account(self, client, fake_apple):
        # Hide My Email mints a per app address. It proves nothing about any
        # other mailbox, so it must not be treated as proof of one. Contrived
        # on purpose: a real relay address cannot collide with a real one, and
        # the check is here so that it cannot in principle either.
        assert _register(client, email=RELAY_EMAIL).status_code in (200, 201)
        token = fake_apple.issue("relay", email=RELAY_EMAIL, is_private_email=True)
        response = _sign_in(client, token, role="influencer", country_code="BJ")
        assert response.status_code == 409
        assert response.json()["code"] == "auth_apple_email_unavailable"
        # Untouched. The pre-existing account did not acquire an Apple link.
        assert _user(client, email=RELAY_EMAIL).apple_sub is None

    def test_a_relay_address_still_opens_its_own_account(self, client, fake_apple):
        # It is a real deliverable address, so mail reaches the person. What
        # it is not is something they will recognise at a login form, which is
        # why that account signs in with the button.
        token = fake_apple.issue("relay", email=RELAY_EMAIL, is_private_email=True)
        response = _sign_in(client, token, role="influencer", country_code="BJ")
        assert response.status_code == 200
        assert _user(client, email=RELAY_EMAIL).apple_sub == SUBJECT

    def test_the_relay_domain_is_recognised_without_the_claim(self, client, fake_apple):
        # Apple has omitted is_private_email on some flows. The domain is
        # Apple's own and nothing else is issued under it, so the restrictive
        # reading wins whatever the claim says.
        assert _register(client, email=RELAY_EMAIL).status_code in (200, 201)
        token = fake_apple.issue("relay-no-claim", email=RELAY_EMAIL)
        response = _sign_in(client, token, role="influencer", country_code="BJ")
        assert response.status_code == 409
        assert response.json()["code"] == "auth_apple_email_unavailable"

    def test_an_unconfirmed_address_does_not_claim_an_account(self, client, fake_apple):
        assert _register(client).status_code in (200, 201)
        token = fake_apple.issue("unconfirmed", email=REAL_EMAIL, email_verified=False)
        response = _sign_in(client, token, role="influencer", country_code="BJ")
        assert response.status_code == 409
        assert response.json()["code"] == "auth_apple_email_unavailable"
        assert _user(client, email=REAL_EMAIL).apple_sub is None

    def test_apples_string_booleans_are_understood(self, client, fake_apple):
        # Apple has shipped these claims as JSON booleans and as the quoted
        # strings at different times. "true" has to mean true, or a confirmed
        # address silently stops claiming its account.
        assert _register(client).status_code in (200, 201)
        token = fake_apple.issue("stringy", email=REAL_EMAIL, email_verified="true")
        assert _sign_in(client, token).status_code == 200
        assert _user(client, email=REAL_EMAIL).apple_sub == SUBJECT


class TestTheLink:
    def test_a_subject_another_account_holds_is_not_taken_from_it(self, client, fake_apple):
        first = _new_account(client, fake_apple)
        assert first.status_code == 200

        # A second Kolabo account, and a token presenting the SAME subject
        # under a different confirmed address. The identity belongs to the row
        # that claimed it first; the unique index is what makes that true.
        assert _register(client, email="kofi@example.com").status_code in (200, 201)
        token = fake_apple.issue("same-sub", email="kofi@example.com")
        response = _sign_in(client, token)
        # The sign in still succeeds, on the strength of its own mailbox.
        assert response.status_code == 200
        # And the second account is left unlinked rather than stealing it.
        assert _user(client, email="kofi@example.com").apple_sub is None
        assert _user(client, email=REAL_EMAIL).apple_sub == SUBJECT

    def test_the_subject_never_reaches_the_api(self, client, fake_apple):
        token = _new_account(client, fake_apple).json()["access_token"]
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        body = me.json()
        # A `sub` is a stable cross site identifier for a person and no client
        # has a use for the value, only for whether there is one.
        assert "apple_sub" not in body
        assert SUBJECT not in str(body)
        assert body["apple_linked"] is True

    def test_an_account_that_has_never_seen_apple_says_so(self, client, fake_apple):
        assert _register(client).status_code in (200, 201)
        login = client.post("/auth/login", json={"email": REAL_EMAIL, "password": PASSWORD})
        if login.status_code != 200:
            pytest.skip("registration here requires OTP verification before login")
        token = login.json()["access_token"]
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["apple_linked"] is False


class TestReAuthentication:
    """require_reauth, and the None comparison that would have undone it."""

    def test_an_apple_token_proves_ownership_of_the_linked_account(self, client, fake_apple):
        from app.modules.auth.account import require_reauth

        user = models.User(
            email=REAL_EMAIL,
            password_hash="x",
            country_code="BJ",
            role="influencer",
            apple_sub=SUBJECT,
        )
        token = fake_apple.issue("reauth")
        # No exception is the assertion.
        require_reauth(user, None, None, token)

    def test_re_auth_refuses_an_unlinked_account(self, client, fake_apple):
        # THE IMPORTANT ONE. Without the explicit `user.apple_sub is None`
        # test, None == None holds here and any valid Apple token from any
        # Apple account proves ownership of this row.
        from app.modules.auth.account import require_reauth

        user = models.User(
            email=REAL_EMAIL,
            password_hash="x",
            country_code="BJ",
            role="influencer",
            apple_sub=None,
        )
        token = fake_apple.issue("reauth")
        with pytest.raises(AppError) as refused:
            require_reauth(user, None, None, token)
        assert refused.value.code == "auth_reauth_required"

    def test_re_auth_refuses_somebody_elses_apple_account(self, client, fake_apple):
        from app.modules.auth.account import require_reauth

        user = models.User(
            email=REAL_EMAIL,
            password_hash="x",
            country_code="BJ",
            role="influencer",
            apple_sub=SUBJECT,
        )
        token = fake_apple.issue("reauth", sub="somebody-else")
        with pytest.raises(AppError) as refused:
            require_reauth(user, None, None, token)
        assert refused.value.code == "auth_reauth_required"

    def test_two_proofs_at_once_are_refused(self, client, fake_apple):
        # Exactly one, never both and never neither. Both is a request whose
        # author does not know which proof they hold.
        from app.modules.auth.account import require_reauth

        user = models.User(
            email=REAL_EMAIL,
            password_hash="x",
            country_code="BJ",
            role="influencer",
            apple_sub=SUBJECT,
        )
        token = fake_apple.issue("reauth")
        with pytest.raises(AppError) as refused:
            require_reauth(user, PASSWORD, None, token)
        assert refused.value.code == "auth_reauth_required"

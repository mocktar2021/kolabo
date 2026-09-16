"""Signing in with Google: POST /auth/google, and what it costs to own an account.

THE NETWORK IS NEVER TOUCHED. google.oauth2.id_token.verify_oauth2_token is
monkeypatched on the module attribute, the same way test_enrichment.py swaps
enrichment.httpx.get and test_social_oauth.py swaps the provider registry. That
seam is deliberately as deep as it can be while staying offline: everything
this codebase actually wrote stays under test, including the audience list it
hands the library, the email_verified rule, the address normalisation and every
branch of the endpoint. What is NOT exercised is the library call itself, so
nothing here proves that a real Google token verifies against real Google
certificates. That is a manual check against a real client id, and it cannot be
CI's job without putting Google on the critical path of every build.

THE LINKING RULE IS ASSERTED HERE BECAUSE IT IS A DECISION, not an accident. A
verified Google address that already has a Kolabo account signs into it. The
mailbox is the login identity on this platform, so that is the same person by
definition, and somebody holding the mailbox could already take the account
back through a password reset. test_a_verified_google_address_signs_into_the_
account_that_already_holds_it is what stops that being quietly reversed, and
test_an_unverified_google_address_is_refused is what keeps it safe.
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
from app.modules.auth import google, models
from app.modules.auth.router import router as auth_router

# Two client ids, because that is the shape the setting exists for: web and
# mobile are separate OAuth clients and Google stamps whichever one asked into
# `aud`. A test with one id would pass just as happily against a verifier that
# could only ever check one, which is the bug the list is there to prevent.
WEB_CLIENT_ID = "111111.apps.googleusercontent.com"
MOBILE_CLIENT_ID = "222222.apps.googleusercontent.com"
OTHER_APP_CLIENT_ID = "999999.apps.googleusercontent.com"

EMAIL = "ama@example.com"
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
    # Account deletion reaches into most modules, so every table has to exist.
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
    # The REAL error handler. Nearly every assertion below reads `code` out of
    # the body, and AppError subclasses HTTPException: without this, FastAPI's
    # own handler renders {"detail": ...} alone and every one of them dies on a
    # missing key rather than on a wrong answer. Same registration, and the
    # same reason, as tests/test_auth.py.
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(auth_router, prefix="/auth")
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    test_client.session_factory = testing_session
    return test_client


class _FakeGoogle:
    """Google's verifier, stood in for by a dictionary of tokens we minted.

    A token this fixture never issued raises, which is what the library does
    for a signature it cannot verify, so "an invalid token" needs no special
    setup in a test: any string will do.

    It records the audience it was handed so one test can assert that BOTH
    configured client ids are offered, rather than trusting that they are.
    """

    def __init__(self):
        self.tokens: dict[str, dict] = {}
        self.audiences_seen: list = []

    def issue(
        self,
        raw: str,
        email: str = EMAIL,
        email_verified: bool = True,
        aud: str = WEB_CLIENT_ID,
        sub: str = "google-sub-1",
    ) -> str:
        self.tokens[raw] = {
            "iss": "https://accounts.google.com",
            "aud": aud,
            "sub": sub,
            "email": email,
            "email_verified": email_verified,
            # RELATIVE, never a literal date. The stand-in does not check it
            # (the real library does, and that is exactly the part being
            # stubbed out), but a fixture carrying a date that goes stale is a
            # test that starts failing on a calendar rather than on a change.
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }
        return raw

    def __call__(self, raw, request, audience=None):
        self.audiences_seen.append(audience)
        claims = self.tokens.get(raw)
        if claims is None:
            raise ValueError("Could not verify token signature.")
        return claims


@pytest.fixture()
def fake_google(monkeypatch):
    """Two client ids configured, and Google's verifier replaced.

    The settings object is patched rather than the environment because what is
    under test is the rule, not this machine's configuration, and because that
    is how test_enrichment.py turns the YouTube and Meta integrations on and
    off.
    """
    monkeypatch.setattr(settings, "google_client_ids", f"{WEB_CLIENT_ID},{MOBILE_CLIENT_ID}")
    fake = _FakeGoogle()
    monkeypatch.setattr(google.id_token, "verify_oauth2_token", fake)
    return fake


def _sign_in(client, token, **extra):
    return client.post("/auth/google", json={"id_token": token, **extra})


def _register(client, email=EMAIL, country="BJ", role="influencer", password=PASSWORD):
    return client.post(
        "/auth/register",
        json={"email": email, "password": password, "country_code": country, "role": role},
    )


def _latest_code(client, email=EMAIL):
    db = client.session_factory()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        challenge = (
            db.query(models.OtpChallenge)
            .filter(models.OtpChallenge.user_id == user.id)
            .order_by(models.OtpChallenge.created_at.desc())
            .first()
        )
        return challenge.code
    finally:
        db.close()


def _verified_password_account(client, email=EMAIL, role="influencer"):
    _register(client, email=email, role=role)
    client.post("/auth/verify-otp", json={"email": email, "code": _latest_code(client, email)})


def _user(client, email=EMAIL):
    db = client.session_factory()
    try:
        return db.query(models.User).filter(models.User.email == email).first()
    finally:
        db.close()


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------
# Refusals
# --------------------------------------------------------------------------


def test_with_no_client_ids_the_feature_reports_itself_unavailable(client, monkeypatch):
    """An unconfigured provider is ABSENT, not broken, and not unrestricted.

    503 rather than 400 or 404: the caller did nothing wrong and the feature
    exists, this deployment simply has nothing to check an audience against.
    The client's job on this code is to hide the button.
    """
    monkeypatch.setattr(settings, "google_client_ids", "")
    refused = _sign_in(client, "anything")
    assert refused.status_code == 503
    assert refused.json()["code"] == "auth_google_unavailable"


def test_a_token_google_did_not_sign_is_refused(client, fake_google):
    refused = _sign_in(client, "not-a-real-token")
    assert refused.status_code == 401
    assert refused.json()["code"] == "auth_google_token_invalid"
    # And no account was conjured out of it.
    assert _user(client, EMAIL) is None


def test_an_unverified_google_address_is_refused(client, fake_google):
    """THE CHECK THE WHOLE LINKING DECISION RESTS ON.

    A Workspace domain can be created by anyone who controls a domain, and an
    account inside it can claim any address its administrator types, including
    one at a domain they do not control, until Google confirms it. Because a
    verified address signs straight into whatever Kolabo account already holds
    it, this claim is the only thing between an attacker and that account.

    Refused with the same code and the same sentence as a forged token, on
    purpose: telling them apart would say to whoever is holding one which check
    caught it.
    """
    fake_google.issue("unconfirmed", email_verified=False)
    refused = _sign_in(client, "unconfirmed", role="influencer", country_code="BJ")
    assert refused.status_code == 401
    assert refused.json()["code"] == "auth_google_token_invalid"
    assert _user(client, EMAIL) is None


def test_a_token_addressed_to_another_application_is_refused(client, fake_google):
    """A correctly signed Google ID token issued to somebody ELSE'S app is easy
    to come by: sign in to their app and read it off the wire. Without the
    audience check that token would sign its holder in here, which turns every
    other Google app on the internet into a way into Kolabo."""
    fake_google.issue("someone-elses-app", aud=OTHER_APP_CLIENT_ID)
    refused = _sign_in(client, "someone-elses-app", role="influencer", country_code="BJ")
    assert refused.status_code == 401
    assert refused.json()["code"] == "auth_google_token_invalid"


def test_both_configured_client_ids_are_offered_as_the_audience(client, fake_google):
    """Web and mobile are different OAuth clients. A verifier that offered only
    the first id would work on one surface and refuse the other, and the
    refusal would look like a broken button rather than a configuration bug."""
    fake_google.issue("from-the-phone", aud=MOBILE_CLIENT_ID)
    assert _sign_in(client, "from-the-phone", role="business", country_code="GH").status_code == 200
    assert sorted(fake_google.audiences_seen[-1]) == sorted([WEB_CLIENT_ID, MOBILE_CLIENT_ID])


# --------------------------------------------------------------------------
# The two step flow for an address with no account
# --------------------------------------------------------------------------


def test_a_new_address_without_a_role_or_a_country_asks_for_them(client, fake_google):
    """Not an error: the first leg of a two step flow. Google says who somebody
    is and cannot say which country they sell in or whether they came here to
    sell."""
    fake_google.issue("newcomer")
    refused = _sign_in(client, "newcomer")
    assert refused.status_code == 400
    assert refused.json()["code"] == "auth_google_profile_required"
    # Nothing half made was left behind for the second call to trip over.
    assert _user(client, EMAIL) is None


def test_half_the_answer_is_not_enough(client, fake_google):
    """A role with no country, and a country with no role, are both the same
    unanswered question."""
    fake_google.issue("newcomer")
    assert _sign_in(client, "newcomer", role="influencer").json()["code"] == "auth_google_profile_required"
    assert _sign_in(client, "newcomer", country_code="BJ").json()["code"] == "auth_google_profile_required"


def test_the_same_token_completes_the_signup_on_the_second_call(client, fake_google):
    """The client asks the two questions and calls again with the SAME token,
    which is still good for the best part of an hour. A flow that needed a
    fresh token would send the user back through Google's dialog for no
    reason."""
    fake_google.issue("newcomer")
    assert _sign_in(client, "newcomer").status_code == 400
    done = _sign_in(client, "newcomer", role="agency", country_code="CI")
    assert done.status_code == 200
    body = done.json()
    assert body["access_token"]
    # The role travels with the token, exactly as it does from verify-otp and
    # login: the client picks the home experience from it, and an agency that
    # came back as a creator is the bug that put it there.
    assert body["role"] == "agency"


def test_a_created_account_is_verified_from_birth_and_was_sent_no_code(client, fake_google):
    """Registration sends an OTP to prove the mailbox. Google has just proved
    it. A row created unverified here would be one that login() immediately
    locks out with auth_not_verified, over a code nothing ever sent."""
    fake_google.issue("newcomer")
    assert _sign_in(client, "newcomer", role="influencer", country_code="BJ").status_code == 200
    user = _user(client, EMAIL)
    assert user is not None
    assert user.is_verified is True
    db = client.session_factory()
    try:
        assert db.query(models.OtpChallenge).count() == 0
    finally:
        db.close()


def test_a_created_account_has_a_password_nobody_can_use(client, fake_google):
    """password_hash is NOT NULL and stays that way, so the row carries a hash
    of a secret that was generated, used once and dropped. login() is unchanged
    and simply always refuses such an account, which is correct rather than a
    special case."""
    fake_google.issue("newcomer")
    _sign_in(client, "newcomer", role="influencer", country_code="BJ")
    user = _user(client, EMAIL)
    assert user.password_hash
    assert client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 401


def test_the_address_is_folded_the_way_registration_folds_it(client, fake_google):
    """Google may hand back a capitalised spelling of the same mailbox. Stored
    un-normalised it would be a second account, or a 500 on the unique index
    that discovered it was not."""
    _verified_password_account(client)
    fake_google.issue("shouty", email="AMA@Example.COM")
    assert _sign_in(client, "shouty").status_code == 200
    db = client.session_factory()
    try:
        assert db.query(models.User).count() == 1
    finally:
        db.close()


def test_an_unknown_role_and_a_closed_country_are_refused_as_at_registration(client, fake_google, monkeypatch):
    """Validated with the same two codes register uses, so there is one rule
    about what a role is and one about which markets are open."""
    fake_google.issue("newcomer")
    bad_role = _sign_in(client, "newcomer", role="astronaut", country_code="BJ")
    assert bad_role.status_code == 400
    assert bad_role.json()["code"] == "auth_role_unknown"

    from app.core import country_config

    monkeypatch.setitem(
        country_config.COUNTRY_CONFIG,
        "NG",
        {**country_config.COUNTRY_CONFIG["NG"], "enabled": False},
    )
    closed = _sign_in(client, "newcomer", role="influencer", country_code="NG")
    assert closed.status_code == 400
    assert closed.json()["code"] == "auth_country_unavailable"
    assert _user(client, EMAIL) is None


def test_a_referral_code_still_attributes_the_signup(client, fake_google):
    """This IS a registration when the address is new. A creator who brought
    somebody in should not lose the credit because that person tapped the
    Google button instead of filling in the form."""
    _verified_password_account(client, email="referrer@example.com")
    login = client.post(
        "/auth/login", json={"email": "referrer@example.com", "password": PASSWORD}
    )
    code = client.get("/auth/me/referral", headers=_headers(login.json()["access_token"])).json()["code"]

    fake_google.issue("newcomer", email="newcomer@example.com")
    assert _sign_in(
        client, "newcomer", role="influencer", country_code="BJ", referral_code=code
    ).status_code == 200
    assert _user(client, "newcomer@example.com").referred_by_user_id == _user(client, "referrer@example.com").id


# --------------------------------------------------------------------------
# Linking: an address that already has an account
# --------------------------------------------------------------------------


def test_a_verified_google_address_signs_into_the_account_that_already_holds_it(client, fake_google):
    """THE OWNER'S EXPLICIT DECISION, asserted so it cannot be quietly undone.

    The mailbox is the login identity here, so a Google verified address is the
    same person: everything about an account resolves from its address, and
    whoever holds the mailbox could already take the account back through a
    password reset in ten minutes. This is that, faster.
    """
    _verified_password_account(client, role="business")
    fake_google.issue("returning")

    signed_in = _sign_in(client, "returning")
    assert signed_in.status_code == 200
    assert signed_in.json()["role"] == "business"
    # No second account, and no role or country asked for: the answer to both
    # is already on the row.
    db = client.session_factory()
    try:
        assert db.query(models.User).count() == 1
    finally:
        db.close()


def test_linking_leaves_the_password_alone_so_both_doors_still_open(client, fake_google):
    """A password account that also signs in with Google keeps both routes.
    Overwriting the hash would lock somebody out of the way in they have been
    using for a year."""
    _verified_password_account(client)
    before = _user(client).password_hash
    fake_google.issue("returning")
    assert _sign_in(client, "returning").status_code == 200
    assert _user(client).password_hash == before
    assert client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 200


def test_an_unverified_account_becomes_verified(client, fake_google):
    """A half finished signup, completed by a different route. The account was
    created by /auth/register, the code was never entered, and Google has now
    proved the mailbox that code was sent to. Leaving the flag alone would
    strand the account: it would hold a token from here and still be refused
    by login()."""
    _register(client)
    assert _user(client).is_verified is False

    fake_google.issue("returning")
    assert _sign_in(client, "returning").status_code == 200
    assert _user(client).is_verified is True
    assert client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 200


# --------------------------------------------------------------------------
# Re-authentication: owning an account with no usable password
# --------------------------------------------------------------------------


def _google_account(client, fake_google, token="newcomer", email=EMAIL, role="influencer"):
    """An account that exists only because of Google, and its bearer token."""
    fake_google.issue(token, email=email)
    resp = _sign_in(client, token, role=role, country_code="BJ")
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_a_google_account_can_delete_itself_with_a_google_token(client, fake_google):
    """WITHOUT THIS THE ACCOUNT COULD NEVER BE DELETED BY ITS OWNER, which both
    app stores and every data protection regime in these markets expect to
    work. The fix is not to drop the ownership check: it is to accept a
    different proof of the same fact."""
    bearer = _google_account(client, fake_google)
    r = client.request(
        "DELETE", "/auth/me", json={"google_token": "newcomer"}, headers=_headers(bearer)
    )
    assert r.status_code == 204
    assert _user(client) is None


def test_deleting_with_neither_proof_is_refused(client, fake_google):
    """A bearer token says a session exists. It cannot tell an owner from
    whoever picked the handset up."""
    bearer = _google_account(client, fake_google)
    r = client.request("DELETE", "/auth/me", json={}, headers=_headers(bearer))
    assert r.status_code == 403
    assert r.json()["code"] == "auth_reauth_required"
    assert _user(client) is not None


def test_sending_both_proofs_is_refused_rather_than_silently_preferred(client, fake_google):
    """Accepting both would mean deciding, without saying so, which one
    counted."""
    _verified_password_account(client)
    fake_google.issue("returning")
    bearer = _sign_in(client, "returning").json()["access_token"]
    r = client.request(
        "DELETE",
        "/auth/me",
        json={"password": PASSWORD, "google_token": "returning"},
        headers=_headers(bearer),
    )
    assert r.status_code == 403
    assert r.json()["code"] == "auth_reauth_required"
    assert _user(client) is not None


def test_somebody_elses_google_token_cannot_delete_this_account(client, fake_google):
    """A verified token proves who the HOLDER is and says nothing about which
    account they are pointing it at. Without the address comparison anybody
    with any Google account could re-authenticate as anybody else."""
    bearer = _google_account(client, fake_google)
    fake_google.issue("stranger", email="stranger@example.com", sub="google-sub-2")
    r = client.request(
        "DELETE", "/auth/me", json={"google_token": "stranger"}, headers=_headers(bearer)
    )
    assert r.status_code == 403
    assert r.json()["code"] == "auth_reauth_required"
    assert _user(client) is not None


def test_a_wrong_password_still_says_the_password_is_wrong(client, fake_google):
    """auth_reauth_required is not a replacement for auth_password_incorrect.
    Telling somebody who sent a password that they should confirm with Google
    is the wrong next step, and the reverse is worse: it sends a Google user
    hunting for a password they have never had."""
    _verified_password_account(client)
    login = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    r = client.request(
        "DELETE",
        "/auth/me",
        json={"password": "not-the-password"},
        headers=_headers(login.json()["access_token"]),
    )
    assert r.status_code == 403
    assert r.json()["code"] == "auth_password_incorrect"


def test_a_google_account_can_set_a_password_for_the_first_time(client, fake_google):
    """The one thing such an account cannot otherwise ever do. new_password is
    the only way to acquire a password and it is gated behind a current one,
    which this account has never had. A Google token pays that price instead,
    and afterwards both doors are open."""
    bearer = _google_account(client, fake_google)
    r = client.patch(
        "/auth/me",
        json={"google_token": "newcomer", "new_password": "brandnewpass7"},
        headers=_headers(bearer),
    )
    assert r.status_code == 200
    assert client.post(
        "/auth/login", json={"email": EMAIL, "password": "brandnewpass7"}
    ).status_code == 200
    # And from then on the password works as the proof too.
    assert client.patch(
        "/auth/me",
        json={"current_password": "brandnewpass7", "phone": "+22990000099"},
        headers=_headers(bearer),
    ).status_code == 200


def test_patching_with_neither_proof_is_refused(client, fake_google):
    bearer = _google_account(client, fake_google)
    r = client.patch("/auth/me", json={"phone": "+22990000098"}, headers=_headers(bearer))
    assert r.status_code == 403
    assert r.json()["code"] == "auth_reauth_required"


def test_a_password_account_is_unaffected_by_any_of_this(client, fake_google):
    """The rule gained a second form; it did not lose the first. Every existing
    settings change still costs exactly the current password."""
    _verified_password_account(client)
    login = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    bearer = login.json()["access_token"]
    assert client.patch(
        "/auth/me",
        json={"current_password": PASSWORD, "phone": "+22990000097"},
        headers=_headers(bearer),
    ).status_code == 200
    assert client.patch(
        "/auth/me",
        json={"current_password": "wrong-one", "phone": "+22990000096"},
        headers=_headers(bearer),
    ).status_code == 403


def test_re_authentication_is_refused_when_google_is_not_configured(client, fake_google, monkeypatch):
    """A deployment that loses its client ids cannot verify a token, so it
    cannot accept one as proof. The refusal is auth_reauth_required rather than
    auth_google_unavailable: the caller is not signing in, they are being asked
    to prove they own an account, and the sentence has to name both ways of
    doing that."""
    bearer = _google_account(client, fake_google)
    monkeypatch.setattr(settings, "google_client_ids", "")
    r = client.request(
        "DELETE", "/auth/me", json={"google_token": "newcomer"}, headers=_headers(bearer)
    )
    assert r.status_code == 403
    assert r.json()["code"] == "auth_reauth_required"
    assert _user(client) is not None


def test_login_is_untouched(client, fake_google):
    """A Google only user failing to log in with a password is correct
    behaviour, not a gap. There is no password to get right."""
    _google_account(client, fake_google)
    assert client.post("/auth/login", json={"email": EMAIL, "password": "guess"}).status_code == 401

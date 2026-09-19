"""The OAuth subsystem, proved against a provider that does not exist.

NO NETWORK, NO DEVELOPER ACCOUNT, NO APP REVIEW. Every test here runs against a
FakeProvider that answers instantly and records what it was asked — the same
treatment test_enrichment.py gives httpx and test_follower_provenance.py gives
the enricher. That is the point of building the mechanism before any real
provider: the state handling, the encryption and the refresh rules can be
pinned in CI today, and the first real platform is then a diff about ITS
endpoints rather than about all of this again.

WHAT IS ACTUALLY BEING GUARDED, in rough order of how badly it goes wrong:

  * A REPLAYED STATE. The callback is unauthenticated by necessity — a browser
    redirect from a platform carries no bearer token — so the state row is the
    only thing that says whose profile an account lands on. A state that works
    twice is a callback URL that works twice, out of a browser history or a
    referer header.
  * A ROTATED REFRESH TOKEN. TikTok hands back a NEW refresh token on every
    refresh and retires the old one. Storing the old one back is silent today
    and breaks the creator's connection weeks later, which is the worst shape a
    defect can have.
  * TOKENS AT REST. An access token is a credential for somebody else's account
    on somebody else's platform. It is in the database, so it is encrypted, and
    a test asserts the plaintext is genuinely not in the column.

THE FIXTURE IS CALLED `auth_client`, NOT `client`, AND THAT IS LOAD-BEARING —
the same trick, for a different reason, as test_profiles_auth.py. The autouse
fixture in backend/conftest.py rebinds `profile_owner` to
`lambda user_id: user_id` for any test that uses a fixture named `client`, and
POST /profiles/oauth/{platform}/start has no `user_id` in its path: under that
override FastAPI would turn `user_id` into a required QUERY parameter and the
route would answer 422. Naming the fixture differently keeps the real
dependency, which is what these tests want anyway.
"""
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.crypto import decrypt_bytes
from app.core.db import Base, get_db
from app.core.errors import AppError, app_error_handler
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.profiles import models, oauth, oauth_service
from app.modules.profiles.router import router as profiles_router

PLATFORM = "tiktok"


@pytest.fixture()
def auth_client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    from app.core.db import import_all_models

    import_all_models()
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(profiles_router, prefix="/profiles")
    app.dependency_overrides[get_db] = override_get_db
    # THE REAL ERROR HANDLER, registered from app.core.errors rather than
    # re-declared, so the assertions below can read `code` off the body — a
    # bare FastAPI app would fall back to the default HTTPException handler and
    # answer with `detail` alone. Same reasoning as the fixture in
    # test_error_codes.py: a handler that merely resembles the production one
    # is a test that stays green while the wiring is wrong.
    app.add_exception_handler(AppError, app_error_handler)
    c = TestClient(app)
    c.session_factory = ts
    return c


def _user(client, phone):
    db = client.session_factory()
    try:
        u = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


def _headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


class FakeProvider:
    """A platform that answers instantly and remembers what it was asked.

    Everything a real provider would do over HTTPS — build a consent URL, POST
    to a token endpoint, POST again to renew — reduced to the three method
    bodies and a couple of lists. It is enough to exercise every rule in
    oauth_service, and it needs neither a socket nor an approved app.
    """

    platform = PLATFORM

    def __init__(self, *, access_expires_in=3600, refresh_token="refresh-1", rotates_to=None):
        self.exchanges = []
        self.refreshes = []
        self.access_expires_in = access_expires_in
        self.refresh_token = refresh_token
        # None means "hand back whatever you were given", which is what a
        # provider that does NOT rotate looks like.
        self.rotates_to = rotates_to

    def authorize_url(self, state, code_verifier, redirect_uri):
        # A real provider sends the S256 challenge, never the verifier. Doing
        # the same here keeps the fake honest about which of the two crosses
        # the wire.
        return (
            "https://fake.test/oauth/authorize"
            f"?state={state}"
            f"&code_challenge={oauth.code_challenge(code_verifier)}"
            f"&redirect_uri={redirect_uri}"
        )

    def exchange_code(self, code, code_verifier, redirect_uri):
        self.exchanges.append((code, code_verifier, redirect_uri))
        return oauth.TokenSet(
            access_token="access-1",
            refresh_token=self.refresh_token,
            access_expires_in=self.access_expires_in,
            refresh_expires_in=86400,
            scope="user.info.basic",
            provider_user_id="open-id-1",
        )

    def refresh(self, refresh_token):
        self.refreshes.append(refresh_token)
        return oauth.TokenSet(
            access_token="access-2",
            refresh_token=self.rotates_to if self.rotates_to is not None else refresh_token,
            access_expires_in=3600,
            refresh_expires_in=86400,
            scope="user.info.basic",
            provider_user_id="open-id-1",
        )


class BrokenProvider(FakeProvider):
    """A platform that refuses the exchange, the way a revoked client id does."""

    def exchange_code(self, code, code_verifier, redirect_uri):
        raise RuntimeError("invalid_client")


def _register(monkeypatch, provider):
    """Point the service's registry at a fake.

    Patches the module attribute the service reads, exactly as
    test_follower_provenance.py does with `social_enricher`: providers are
    chosen at import time from credentials, the test suite configures none, so
    without this every call refuses with oauth_platform_unsupported.
    """
    monkeypatch.setattr(oauth_service, "providers", {provider.platform: provider})
    return provider


def _start(client, user_id, platform=PLATFORM, **body):
    r = client.post(
        f"/profiles/oauth/{platform}/start", json=body or {}, headers=_headers(user_id)
    )
    assert r.status_code == 200, r.text
    return r.json()["authorize_url"]


def _state_in(url):
    return parse_qs(urlparse(url).query)["state"][0]


def _callback(client, state, code="the-code", platform=PLATFORM, headers=None):
    return client.get(
        f"/profiles/oauth/{platform}/callback",
        params={"code": code, "state": state},
        headers=headers or {},
        # NEVER FOLLOWED, and TestClient follows by default. The callback may
        # now answer a 302 to the web app or to a kolabo:// deep link: httpx
        # would route the first back into this test app and refuse the second
        # outright as an unsupported protocol. What these tests are about is
        # the Location header itself, not what lies on the other end of it.
        follow_redirects=False,
    )


def _state_row(client, state):
    db = client.session_factory()
    try:
        row = db.query(models.OAuthState).filter(models.OAuthState.state == state).first()
        if row is None:
            return None
        return {
            "id": row.id,
            "user_id": row.user_id,
            "platform": row.platform,
            "code_verifier": row.code_verifier,
            "consumed": row.consumed,
            "redirect_to": row.redirect_to,
        }
    finally:
        db.close()


def _stored_token(client, account_id):
    """The token row's RAW columns, read straight out of the database.

    Raw on purpose: the ciphertext assertions are about what is actually in the
    column, and a helper that decrypted on the way out would be asserting the
    encryption round trip rather than the storage.
    """
    db = client.session_factory()
    try:
        row = (
            db.query(models.SocialToken)
            .filter(models.SocialToken.social_account_id == account_id)
            .first()
        )
        if row is None:
            return None
        return {
            "access_ciphertext": row.access_token_ciphertext,
            "refresh_ciphertext": row.refresh_token_ciphertext,
            "access_expires_at": row.access_expires_at,
            "scope": row.scope,
            "provider_user_id": row.provider_user_id,
        }
    finally:
        db.close()


def _accounts(client, user_id):
    return client.get(f"/profiles/{user_id}/social-accounts").json()


# --------------------------------------------------------------------------
# The pieces the state row is made of
# --------------------------------------------------------------------------


def test_a_state_is_unguessable_and_the_verifier_is_pkce_sized():
    """Both come from secrets, and both are long enough to be worth nothing to
    a guesser. 32 bytes of urlsafe base64 is 43 characters; RFC 7636 wants a
    verifier of 43 to 128."""
    a, b = oauth.new_state(), oauth.new_state()
    assert a != b
    assert len(a) >= 43

    verifier = oauth.new_code_verifier()
    assert 43 <= len(verifier) <= 128


def test_the_code_challenge_is_unpadded_s256():
    """base64url of a sha256 is 44 characters with padding and 43 without.
    Providers reject the "=" inconsistently, which is the worst way for
    something compared byte for byte to be wrong."""
    challenge = oauth.code_challenge("a" * 64)
    assert len(challenge) == 43
    assert "=" not in challenge
    assert challenge == oauth.code_challenge("a" * 64)


def test_no_provider_is_configured_by_default():
    """build_default_providers() is empty, exactly as build_default_enricher()
    is a NoopEnricher: no platform in this repo has an OAuth client id or an
    approved developer app, so there is nothing that could honestly be
    registered."""
    assert oauth.build_default_providers() == {}


def test_start_refuses_a_platform_with_no_provider(auth_client):
    """The honest answer today, on every platform. Deliberately NOT
    monkeypatched: this is what a creator actually gets."""
    uid = _user(auth_client, "+22990002001")
    r = auth_client.post("/profiles/oauth/tiktok/start", json={}, headers=_headers(uid))
    assert r.status_code == 400
    assert r.json()["code"] == "oauth_platform_unsupported"


def test_start_needs_a_token(auth_client):
    """`start` is where the handshake's identity is decided, so it is the half
    that must be authenticated. The callback cannot be, and is not."""
    assert auth_client.post("/profiles/oauth/tiktok/start", json={}).status_code == 401


# --------------------------------------------------------------------------
# The happy path
# --------------------------------------------------------------------------


def test_start_then_callback_connects_the_account_and_stores_the_tokens(auth_client, monkeypatch):
    provider = _register(monkeypatch, FakeProvider())
    uid = _user(auth_client, "+22990002010")

    url = _start(auth_client, uid, redirect_to="kolabo://profile")
    state = _state_in(url)
    # The callback URL the provider will be told to send the creator back to is
    # built from settings, not from the request, so it can be checked here.
    assert oauth_service.redirect_uri(PLATFORM) in url

    row = _state_row(auth_client, state)
    assert row["user_id"] == uid
    assert row["platform"] == PLATFORM
    assert row["consumed"] is False
    assert row["redirect_to"] == "kolabo://profile"

    r = _callback(auth_client, state)
    # A 302 WHERE THIS ONCE READ A JSON BODY, because this test starts with a
    # redirect_to and the callback now honours one. Nothing it guards has been
    # dropped: the account is read back off the profile instead of out of the
    # body, and the JSON answer is pinned by
    # test_no_redirect_to_still_answers_json_exactly_as_it_always_did below.
    assert r.status_code == 302, r.text
    assert r.headers["location"] == f"kolabo://profile?connected={PLATFORM}"

    account = _accounts(auth_client, uid)[0]
    assert account["platform"] == PLATFORM
    assert account["method"] == "oauth"
    # PENDING like every other connection: no provider has been reviewed, so
    # nothing here has honestly verified anything yet. See oauth_service's
    # module docstring.
    assert account["status"] == "pending"
    # Nothing claims a follower number, so nothing claims a provenance either.
    assert account["follower_count"] is None
    assert account["follower_source"] is None

    # The verifier stayed on the server and was presented at the exchange —
    # that is the whole of PKCE.
    assert len(provider.exchanges) == 1
    code, verifier, used_redirect = provider.exchanges[0]
    assert code == "the-code"
    assert verifier == row["code_verifier"]
    assert used_redirect == oauth_service.redirect_uri(PLATFORM)

    stored = _stored_token(auth_client, account["id"])
    assert decrypt_bytes(stored["access_ciphertext"]).decode() == "access-1"
    assert decrypt_bytes(stored["refresh_ciphertext"]).decode() == "refresh-1"
    assert stored["scope"] == "user.info.basic"
    assert stored["provider_user_id"] == "open-id-1"

    assert _state_row(auth_client, state)["consumed"] is True
    assert len(_accounts(auth_client, uid)) == 1


def test_reauthorising_the_same_platform_account_updates_it_rather_than_duplicating(
    auth_client, monkeypatch
):
    """The same provider_user_id is the same account, whatever its handle says.

    A creator who reconnects — because they revoked us, or changed their
    password, or simply pressed the button twice — should end up with one row
    holding fresh credentials, not two rows racing each other.
    """
    _register(monkeypatch, FakeProvider())
    uid = _user(auth_client, "+22990002011")

    first = _callback(auth_client, _state_in(_start(auth_client, uid))).json()["account"]
    second = _callback(auth_client, _state_in(_start(auth_client, uid))).json()["account"]

    assert first["id"] == second["id"]
    assert len(_accounts(auth_client, uid)) == 1


# --------------------------------------------------------------------------
# The state row is the authentication, so these are the security tests
# --------------------------------------------------------------------------


def test_a_replayed_state_is_refused_so_a_used_callback_url_is_worthless(
    auth_client, monkeypatch
):
    """SINGLE USE. This is the test whose NAME has to say what broke.

    The callback URL carries everything needed to connect an account, and it
    ends up in a browser history, in a referer header sent to whatever the
    landing page loads, and in screenshots people paste into support chats. If
    a state works twice then so does that URL, forever.

    Remove the conditional UPDATE in complete_authorization — or turn it into a
    read-then-assign — and this goes red.
    """
    provider = _register(monkeypatch, FakeProvider())
    uid = _user(auth_client, "+22990002020")
    state = _state_in(_start(auth_client, uid))

    assert _callback(auth_client, state).status_code == 200

    replay = _callback(auth_client, state)
    assert replay.status_code == 400
    assert replay.json()["code"] == "oauth_state_invalid"

    # And nothing happened on the second attempt: no second exchange, no second
    # account.
    assert len(provider.exchanges) == 1
    assert len(_accounts(auth_client, uid)) == 1


def test_an_expired_state_is_refused(auth_client, monkeypatch):
    """Ten minutes. A URL sitting in a history is stale before anybody reads it."""
    provider = _register(monkeypatch, FakeProvider())
    uid = _user(auth_client, "+22990002021")
    state = _state_in(_start(auth_client, uid))

    db = auth_client.session_factory()
    try:
        row = db.query(models.OAuthState).filter(models.OAuthState.state == state).first()
        row.expires_at = models.utcnow() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    r = _callback(auth_client, state)
    assert r.status_code == 400
    # Its own code, not oauth_state_invalid: the creator can act on this one —
    # nothing is wrong, they took too long, and starting again works.
    assert r.json()["code"] == "oauth_state_expired"
    assert provider.exchanges == []
    assert _accounts(auth_client, uid) == []


def test_an_unknown_state_is_refused(auth_client, monkeypatch):
    _register(monkeypatch, FakeProvider())
    r = _callback(auth_client, "not-a-state-anybody-minted")
    assert r.status_code == 400
    assert r.json()["code"] == "oauth_state_invalid"


def test_a_state_cannot_be_redeemed_at_another_platforms_callback(auth_client, monkeypatch):
    """A tiktok state replayed at instagram's callback would attach an account
    on a platform the creator never authorised. The row names its platform, and
    the callback checks it."""
    provider = FakeProvider()
    monkeypatch.setattr(
        oauth_service, "providers", {PLATFORM: provider, "instagram": FakeProvider()}
    )
    uid = _user(auth_client, "+22990002022")
    state = _state_in(_start(auth_client, uid))

    r = _callback(auth_client, state, platform="instagram")
    assert r.status_code == 400
    assert r.json()["code"] == "oauth_state_invalid"
    assert _accounts(auth_client, uid) == []


def test_a_state_belonging_to_one_creator_cannot_attach_an_account_to_another(
    auth_client, monkeypatch
):
    """WHOSE PROFILE THE ACCOUNT LANDS ON IS DECIDED BY THE ROW, NOT THE CALLER.

    Bob gets hold of Alice's callback URL — off a shared screen, out of a
    referer header — and calls it with his own bearer token. The account is
    created for ALICE, because that is who started the authorization and that
    is what the state row says. Bob's token is not consulted at all: the route
    reads no identity, which is why there is nothing here to spoof.

    Note what this does NOT claim. Bob has connected an account he controls to
    Alice's profile, which is the residual risk of any OAuth callback and the
    reason the state has to be unguessable and single-use. What it must never
    do is the reverse — hand Alice's authorization to Bob.
    """
    _register(monkeypatch, FakeProvider())
    alice = _user(auth_client, "+22990002030")
    bob = _user(auth_client, "+22990002031")

    state = _state_in(_start(auth_client, alice))
    r = _callback(auth_client, state, headers=_headers(bob))
    assert r.status_code == 200, r.text

    alice_accounts = _accounts(auth_client, alice)
    assert len(alice_accounts) == 1
    assert alice_accounts[0]["id"] == r.json()["account"]["id"]
    assert _accounts(auth_client, bob) == []


def test_a_refused_exchange_saves_nothing_and_spends_the_state(auth_client, monkeypatch):
    """The platform says no. Nothing is written, the sentence says so, and the
    state is spent anyway — an authorization code is single-use at the provider
    too, so a retry with the same URL was never going to work."""
    _register(monkeypatch, BrokenProvider())
    uid = _user(auth_client, "+22990002040")
    state = _state_in(_start(auth_client, uid))

    r = _callback(auth_client, state)
    assert r.status_code == 502
    assert r.json()["code"] == "oauth_exchange_failed"
    assert _accounts(auth_client, uid) == []
    assert _state_row(auth_client, state)["consumed"] is True


# --------------------------------------------------------------------------
# Coming back to the client, and the allowlist that bounds where that can be
#
# The callback answers a 302 when the state row carries a validated
# redirect_to, and the JSON body it has always answered when it does not. The
# tests below pin both halves, and the one that matters most is the one that
# proves a destination we refused never reaches the response at all.
# --------------------------------------------------------------------------


WEB_ORIGIN = "https://app.kolabo.test"


@pytest.fixture()
def web_origin(monkeypatch):
    """Pin the allowlisted web origin for a test.

    Set here rather than relied on from config.py, so that these tests say what
    they assume and do not quietly start passing or failing the day somebody
    changes a development default.
    """
    monkeypatch.setattr(oauth_service.settings, "web_public_base_url", WEB_ORIGIN)
    return WEB_ORIGIN


def test_no_redirect_to_still_answers_json_exactly_as_it_always_did(
    auth_client, monkeypatch
):
    """THE OLD CONTRACT, PINNED, and the reason this change is additive.

    Every caller that existed before this feature sends no redirect_to, so
    every one of them still gets the same 200 and the same body. If somebody
    later decides the callback should always redirect, this is the test that
    says which callers that would break.
    """
    _register(monkeypatch, FakeProvider())
    uid = _user(auth_client, "+22990002070")

    r = _callback(auth_client, _state_in(_start(auth_client, uid)))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["account"]["platform"] == PLATFORM
    assert body["account"]["status"] == "pending"
    assert body["redirect_to"] is None
    assert "location" not in r.headers


def test_an_allowlisted_web_redirect_sends_the_creator_back_to_the_app(
    auth_client, monkeypatch, web_origin
):
    """The case this whole change exists for: a creator who finished a consent
    screen lands back on their own settings page, not on a page of JSON."""
    _register(monkeypatch, FakeProvider())
    uid = _user(auth_client, "+22990002071")
    state = _state_in(
        _start(auth_client, uid, redirect_to=f"{web_origin}/settings/socials")
    )

    r = _callback(auth_client, state)
    assert r.status_code == 302
    assert (
        r.headers["location"] == f"{web_origin}/settings/socials?connected={PLATFORM}"
    )
    # The redirect is the ANSWER, not a substitute for the work: the account is
    # connected and its credentials are stored, exactly as on the JSON path.
    accounts = _accounts(auth_client, uid)
    assert len(accounts) == 1
    assert _stored_token(auth_client, accounts[0]["id"]) is not None


def test_a_mobile_deep_link_is_allowlisted_because_a_phone_has_no_origin(
    auth_client, monkeypatch, web_origin
):
    """kolabo:// is the second half of the allowlist. The app registers the
    scheme with the operating system, so there is no origin to compare and the
    scheme is the narrowest honest check available."""
    _register(monkeypatch, FakeProvider())
    uid = _user(auth_client, "+22990002072")
    state = _state_in(_start(auth_client, uid, redirect_to="kolabo://oauth/facebook"))

    r = _callback(auth_client, state)
    assert r.status_code == 302
    assert r.headers["location"] == f"kolabo://oauth/facebook?connected={PLATFORM}"


def test_a_redirect_to_outside_the_allowlist_never_appears_in_the_response(
    auth_client, monkeypatch, web_origin
):
    """THE OPEN-REDIRECT GUARD, and the test in this section worth keeping
    above all the others.

    An open redirect on a route a creator reaches mid-handshake is a phishing
    machine: the link starts on kolabo.africa, the browser bar says so, and the
    page it lands on is somebody else's. So a destination that fails the
    allowlist must not reach a Location header, must not reach the JSON body,
    and must not reach the state row where a later reader could trust it.

    Note what is NOT asserted: a refusal. The creator's connection completes,
    because a bad redirect_to is a client bug and never something they did. See
    oauth_service._allowlisted_or_discarded.
    """
    _register(monkeypatch, FakeProvider())
    uid = _user(auth_client, "+22990002073")
    evil = "https://evil.example.com/steal"

    state = _state_in(_start(auth_client, uid, redirect_to=evil))
    assert _state_row(auth_client, state)["redirect_to"] is None

    r = _callback(auth_client, state)
    assert r.status_code == 200, r.text
    assert "location" not in r.headers
    assert r.json()["redirect_to"] is None
    assert "evil.example.com" not in r.text
    assert "evil.example.com" not in str(r.headers)
    # And the connection was not the price of refusing it.
    assert len(_accounts(auth_client, uid)) == 1


@pytest.mark.parametrize(
    "target",
    [
        "https://evil.example.com/steal",
        # A PREFIX MATCH WOULD ADMIT THIS ONE: the host is evil.example.
        "https://app.kolabo.test.evil.example/",
        # And this one, whose host is also evil.example. Everything before the
        # @ is userinfo, which a browser reads and discards.
        "https://app.kolabo.test@evil.example/",
        # Right host, wrong scheme: a downgrade to cleartext.
        "http://app.kolabo.test/settings",
        # No scheme at all, which a browser reads as protocol relative and
        # resolves to https://evil.example/steal.
        "//evil.example/steal",
        "/settings/socials",
        "javascript:alert(1)",
        # Close enough to the deep link scheme to be worth naming.
        "kolabo.example://oauth",
        "",
    ],
)
def test_the_allowlist_refuses_the_usual_open_redirect_tricks(web_origin, target):
    """The unit half of the test above. Each of these is a way an allowlist
    written as a prefix comparison, or as "does it contain our domain", quietly
    lets somebody else's host through."""
    assert oauth_service.redirect_allowed(target) is False


@pytest.mark.parametrize(
    "target",
    [
        "https://app.kolabo.test",
        "https://app.kolabo.test/settings/socials",
        "https://app.kolabo.test/settings?tab=socials#done",
        "kolabo://oauth/facebook",
        "kolabo://profile",
    ],
)
def test_the_allowlist_accepts_the_web_origin_and_the_mobile_scheme(web_origin, target):
    """The other direction, so that a tightening which refuses everything is a
    failing test rather than a feature nobody notices is dead."""
    assert oauth_service.redirect_allowed(target) is True


def test_a_failed_exchange_with_a_redirect_to_carries_the_error_code_home(
    auth_client, monkeypatch, web_origin
):
    """A creator whose exchange failed goes back to the app with the reason,
    instead of reading a 502 in JSON.

    The code in the query string is one that already exists, which is the whole
    trick: the client renders the French or English sentence it already has for
    oauth_exchange_failed, and no new code had to be added to two 50 KB
    translation catalogues to ship this.
    """
    _register(monkeypatch, BrokenProvider())
    uid = _user(auth_client, "+22990002074")
    state = _state_in(
        _start(auth_client, uid, redirect_to=f"{web_origin}/settings/socials")
    )

    r = _callback(auth_client, state)
    assert r.status_code == 302
    assert (
        r.headers["location"]
        == f"{web_origin}/settings/socials?social_error=oauth_exchange_failed"
    )
    # Everything the JSON path promises about a failure still holds.
    assert _accounts(auth_client, uid) == []
    assert _state_row(auth_client, state)["consumed"] is True


def test_an_expired_state_with_a_redirect_to_goes_home_rather_than_to_json(
    auth_client, monkeypatch, web_origin
):
    """Taking eleven minutes over a consent screen is an ordinary thing to do,
    and the creator can act on this one. Telling them so on their own settings
    page is worth more than telling them so in a JSON body."""
    _register(monkeypatch, FakeProvider())
    uid = _user(auth_client, "+22990002075")
    state = _state_in(_start(auth_client, uid, redirect_to=f"{web_origin}/settings"))

    db = auth_client.session_factory()
    try:
        row = db.query(models.OAuthState).filter(models.OAuthState.state == state).first()
        row.expires_at = models.utcnow() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    r = _callback(auth_client, state)
    assert r.status_code == 302
    assert (
        r.headers["location"] == f"{web_origin}/settings?social_error=oauth_state_expired"
    )


def test_an_unknown_state_names_no_destination_so_it_stays_on_json(
    auth_client, monkeypatch, web_origin
):
    """There is no row, so there is no destination anybody ever validated, so
    there is nowhere to go. The refusal keeps its old shape."""
    _register(monkeypatch, FakeProvider())
    r = _callback(auth_client, "not-a-state-anybody-minted")
    assert r.status_code == 400
    assert r.json()["code"] == "oauth_state_invalid"
    assert "location" not in r.headers


def test_a_redirect_to_that_already_has_a_query_string_keeps_it(
    auth_client, monkeypatch, web_origin
):
    """Appended with urllib rather than with a "?", which is the difference
    between a URL the client can parse and one with two question marks in it.
    The existing parameters survive, the marker joins them, and the path is
    untouched."""
    _register(monkeypatch, FakeProvider())
    uid = _user(auth_client, "+22990002076")
    state = _state_in(
        _start(
            auth_client,
            uid,
            redirect_to=f"{web_origin}/settings?tab=socials&from=onboarding",
        )
    )

    r = _callback(auth_client, state)
    assert r.status_code == 302
    location = r.headers["location"]
    assert location.count("?") == 1
    assert urlparse(location).path == "/settings"
    assert parse_qs(urlparse(location).query) == {
        "tab": ["socials"],
        "from": ["onboarding"],
        "connected": [PLATFORM],
    }


# --------------------------------------------------------------------------
# Refresh, and the rotation rule
# --------------------------------------------------------------------------


def _connect(client, monkeypatch, phone, **provider_kwargs):
    provider = _register(monkeypatch, FakeProvider(**provider_kwargs))
    uid = _user(client, phone)
    account = _callback(client, _state_in(_start(client, uid))).json()["account"]
    return provider, uid, account["id"]


def test_load_access_token_returns_the_stored_one_while_it_is_still_valid(
    auth_client, monkeypatch
):
    provider, _uid, account_id = _connect(auth_client, monkeypatch, "+22990002050")

    db = auth_client.session_factory()
    try:
        assert oauth_service.load_access_token(db, account_id) == "access-1"
    finally:
        db.close()
    assert provider.refreshes == [], "a live token must not be renewed"


def test_load_access_token_refreshes_transparently_when_it_has_expired(
    auth_client, monkeypatch
):
    """The caller asks for a token and gets one that works.

    Every future consumer — the TikTok enricher, YouTube Analytics — goes
    through here precisely so that none of them separately decides what
    "expired" means or remembers to write the renewed credentials back.
    """
    provider, _uid, account_id = _connect(
        auth_client, monkeypatch, "+22990002051", access_expires_in=-10
    )

    db = auth_client.session_factory()
    try:
        assert oauth_service.load_access_token(db, account_id) == "access-2"
    finally:
        db.close()
    assert provider.refreshes == ["refresh-1"]

    # The renewed token was PERSISTED, not just returned: the second call finds
    # a live token and does not go back to the provider.
    stored = _stored_token(auth_client, account_id)
    assert decrypt_bytes(stored["access_ciphertext"]).decode() == "access-2"

    db = auth_client.session_factory()
    try:
        assert oauth_service.load_access_token(db, account_id) == "access-2"
    finally:
        db.close()
    assert provider.refreshes == ["refresh-1"], "the second call must not refresh again"


def test_a_refresh_that_returns_a_different_refresh_token_persists_the_new_one(
    auth_client, monkeypatch
):
    """THE REGRESSION GUARD FOR THE WHOLE FEATURE, and the one worth naming.

    TikTok ROTATES: every refresh response carries a new refresh_token and
    retires the one just used. Keeping the old value — because it "is probably
    still the same", or because an optimisation skipped re-encrypting a field
    that looked unchanged — produces a defect with no symptom whatever at the
    moment it is introduced. Nothing throws. Nothing logs. The request that
    triggered the refresh succeeds. The connection dies at the NEXT renewal,
    days or weeks later, and arrives as "my TikTok disconnected itself".

    Turn the rotation branch in save_tokens into
    `if row.refresh_token_ciphertext is None:` and this test fails here, in CI,
    instead of in a support queue in a fortnight.
    """
    provider, _uid, account_id = _connect(
        auth_client,
        monkeypatch,
        "+22990002052",
        access_expires_in=-10,
        rotates_to="refresh-2-rotated",
    )
    assert decrypt_bytes(
        _stored_token(auth_client, account_id)["refresh_ciphertext"]
    ).decode() == "refresh-1"

    db = auth_client.session_factory()
    try:
        oauth_service.load_access_token(db, account_id)
    finally:
        db.close()

    assert provider.refreshes == ["refresh-1"], "the OLD token is what gets sent"
    stored = _stored_token(auth_client, account_id)
    assert (
        decrypt_bytes(stored["refresh_ciphertext"]).decode() == "refresh-2-rotated"
    ), "the NEW refresh token must be what is stored"


def test_a_refresh_that_returns_no_refresh_token_keeps_the_stored_one(
    auth_client, monkeypatch
):
    """The deliberate exception to the rule above, and the only one.

    Google issues a refresh token at authorization time and omits the field
    from every renewal after it. Absent is not revoked, so absent means
    unchanged — blanking the column there would break exactly the connections
    the rotation rule exists to protect.
    """
    provider, _uid, account_id = _connect(
        auth_client, monkeypatch, "+22990002053", access_expires_in=-10
    )
    provider.rotates_to = None
    # A provider that hands back nothing at all on a refresh.
    provider.refresh = lambda refresh_token: oauth.TokenSet(  # type: ignore[assignment]
        access_token="access-2",
        refresh_token=None,
        access_expires_in=3600,
        refresh_expires_in=None,
        scope="user.info.basic",
        provider_user_id="open-id-1",
    )

    db = auth_client.session_factory()
    try:
        assert oauth_service.load_access_token(db, account_id) == "access-2"
    finally:
        db.close()

    stored = _stored_token(auth_client, account_id)
    assert decrypt_bytes(stored["refresh_ciphertext"]).decode() == "refresh-1"


def test_an_account_with_no_refresh_token_asks_the_creator_to_reconnect(
    auth_client, monkeypatch
):
    provider, _uid, account_id = _connect(
        auth_client, monkeypatch, "+22990002054", access_expires_in=-10, refresh_token=None
    )

    db = auth_client.session_factory()
    try:
        with pytest.raises(AppError) as raised:
            oauth_service.load_access_token(db, account_id)
    finally:
        db.close()
    assert raised.value.code == "oauth_token_expired"
    assert provider.refreshes == []


def test_revoke_forgets_the_credentials_and_keeps_the_account(auth_client, monkeypatch):
    _provider, uid, account_id = _connect(auth_client, monkeypatch, "+22990002055")

    db = auth_client.session_factory()
    try:
        oauth_service.revoke(db, account_id)
        # Twice: revoking what is already gone is not an error, so a caller
        # tidying up after a refused refresh need not check first.
        oauth_service.revoke(db, account_id)
    finally:
        db.close()

    assert _stored_token(auth_client, account_id) is None
    # The account itself is still on the profile. Disconnecting it is a
    # different decision, and it belongs to the creator.
    assert len(_accounts(auth_client, uid)) == 1


# --------------------------------------------------------------------------
# At rest
# --------------------------------------------------------------------------


def test_tokens_are_stored_as_ciphertext_and_not_as_the_token(auth_client, monkeypatch):
    """A database dump that leaks an access token is not a leak of data ABOUT a
    creator — it is the ability to act AS them, on a platform we do not run.

    Asserted against the raw column rather than through the decryption helper,
    because the claim is about what is actually written down.
    """
    _provider, _uid, account_id = _connect(auth_client, monkeypatch, "+22990002060")
    stored = _stored_token(auth_client, account_id)

    assert b"access-1" not in stored["access_ciphertext"]
    assert b"refresh-1" not in stored["refresh_ciphertext"]
    # Fernet tokens are urlsafe base64 beginning with the version byte 0x80,
    # which renders as "gAAAAA". Named so a future change of scheme is a
    # decision somebody makes rather than a test that quietly still passes.
    assert stored["access_ciphertext"].startswith(b"gAAAAA")
    # And it does come back.
    assert decrypt_bytes(stored["access_ciphertext"]).decode() == "access-1"


def test_the_public_profile_never_carries_a_token(auth_client, monkeypatch):
    """social_tokens is a separate table precisely so that the storefront — read
    by anybody, with no token in the request — cannot carry one out."""
    _provider, uid, _account_id = _connect(auth_client, monkeypatch, "+22990002061")
    auth_client.put(
        f"/profiles/influencer/{uid}",
        json={"bio": "Hi", "categories": ["fashion"], "rate_card": {}},
        headers=_headers(uid),
    )

    body = auth_client.get(f"/profiles/influencer/{uid}/public").text
    assert "access-1" not in body
    assert "refresh-1" not in body
    assert "ciphertext" not in body

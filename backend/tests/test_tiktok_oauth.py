"""The TikTok provider, proved against a fake Login Kit.

NO NETWORK, NO APP, NO REVIEW. httpx.post and httpx.get are monkeypatched with
canned responses shaped like the real ones, the same treatment
test_meta_oauth.py gives the Graph API and for the same reason: an approval
queue at TikTok must not be what decides whether CI is honest.

A SEPARATE FILE FROM test_social_oauth.py ON PURPOSE, and from
test_meta_oauth.py for the same reason one step further out. test_social_oauth
pins the MECHANISM against a FakeProvider and is untouched by this PR. Each
real provider file pins ONE PLATFORM's endpoints and quirks. When TikTok
changes something, exactly one of these three should go red, and it should be
this one.

WHAT IS ACTUALLY BEING GUARDED, in rough order of how quietly it fails:

  * THE ROTATED REFRESH TOKEN BEING PERSISTED. TikTok retires a refresh token
    the moment it issues a replacement. Keeping the old one is a defect with
    NO SYMPTOM AT THE TIME: the refresh succeeded, the request that triggered
    it worked, the creator sees nothing. The connection dies at the NEXT
    renewal, a day or a week later, and arrives as "my TikTok disconnected
    itself". test_a_rotated_refresh_token_is_what_survives_the_renewal is the
    line that says otherwise, and it runs the whole flow rather than calling
    save_tokens directly, because the bug this guards against lives in the
    seam between the provider and the service.
  * AN HTTP 200 THAT IS A FAILURE. /v2/user/info/ answers a refused token with
    status 200 and an error object. Reading only the status turns that into an
    AudienceSnapshot full of Nones, which is indistinguishable from a creator
    who declined the scopes, and it would be written to their profile as fact.
  * A SPACE-JOINED SCOPE STRING. TikTok reads scopes comma separated. A space
    is not rejected; it is read as one permission with a strange name that
    nobody has, and the handshake then succeeds carrying nothing.
  * THE WRONG BODY ENCODING. The token endpoint wants a form, not JSON, and
    answers JSON with an error about a missing grant_type, which reads like a
    parameter bug rather than an encoding one.
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
CLIENT_KEY = "awxyzsandboxkey"
CLIENT_SECRET = "not-a-real-tiktok-secret"

FIRST_ACCESS = "act.first-access-token-good-for-one-day"
FIRST_REFRESH = "rft.first-refresh-token"
SECOND_ACCESS = "act.second-access-token-after-the-renewal"
# THE WHOLE POINT OF THE ROTATION TESTS. TikTok hands this back on the refresh
# and retires FIRST_REFRESH at the same moment.
ROTATED_REFRESH = "rft.rotated-refresh-token-that-must-be-kept"

OPEN_ID = "open-id-of-the-creator-1"
USERNAME = "adjo.cuisine"
DISPLAY_NAME = "Adjo Cuisine BJ"
FOLLOWERS = 18400

# What TikTok says was granted, which is not necessarily what was asked for.
# Comma separated, because that is TikTok's spelling in both directions.
GRANTED_SCOPE = "user.info.basic,user.info.profile,user.info.stats"

ACCESS_LIFETIME = 86400
REFRESH_LIFETIME = 31536000


# --------------------------------------------------------------------------
# The fake Login Kit
# --------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeTikTok:
    """Everything TikTok would answer, and a record of what it was asked.

    ROUTED ON grant_type RATHER THAN ON CALL ORDER, so a test asserting about
    the refresh is asserting about the refresh even if the provider's internal
    ordering changes.

    IT RECORDS HOW THE BODY WAS SENT, not just what was in it. `data=` and
    `json=` carry the same dict and produce different requests, and only one
    of them works against the real endpoint. See test_the_token_call_is_form
    _encoded_and_never_json.
    """

    def __init__(
        self,
        *,
        user=None,
        expires_in=ACCESS_LIFETIME,
        refresh_expires_in=REFRESH_LIFETIME,
        scope=GRANTED_SCOPE,
        rotate=True,
        fail=(),
        raise_on=(),
        user_info_error=None,
        user_info_status=200,
    ):
        self.calls = []
        self.user = dict(user) if user is not None else {
            "username": USERNAME,
            "display_name": DISPLAY_NAME,
            "follower_count": FOLLOWERS,
        }
        self.expires_in = expires_in
        self.refresh_expires_in = refresh_expires_in
        self.scope = scope
        self.rotate = rotate
        self.fail = set(fail)
        self.raise_on = set(raise_on)
        self.user_info_error = user_info_error
        self.user_info_status = user_info_status

    # -- recording ---------------------------------------------------------

    def body_for(self, step: str) -> dict:
        matches = [call["body"] for call in self.calls if call["step"] == step]
        assert len(matches) == 1, f"expected exactly one {step} call, got {len(matches)}"
        return matches[0]

    def steps(self) -> list:
        return [call["step"] for call in self.calls]

    # -- the endpoints -----------------------------------------------------

    def post(self, url, data=None, json=None, headers=None, timeout=None):
        body = dict(data or json or {})
        step = "refresh" if body.get("grant_type") == "refresh_token" else "exchange"
        self.calls.append(
            {
                "step": step,
                "url": url,
                "body": body,
                "sent_as": "json" if json is not None else "form",
                "headers": dict(headers or {}),
            }
        )
        if step in self.raise_on:
            raise RuntimeError("connection reset")
        if step in self.fail:
            return FakeResponse(
                {
                    "error": "invalid_grant",
                    "error_description": "Authorization code is invalid or expired.",
                    "log_id": "202610301244ABCDEF",
                },
                status_code=400,
            )
        payload = {
            "access_token": SECOND_ACCESS if step == "refresh" else FIRST_ACCESS,
            "open_id": OPEN_ID,
            "token_type": "Bearer",
        }
        if self.expires_in is not None:
            payload["expires_in"] = self.expires_in
        if self.refresh_expires_in is not None:
            payload["refresh_expires_in"] = self.refresh_expires_in
        if self.scope is not None:
            payload["scope"] = self.scope
        if step == "refresh":
            if self.rotate:
                payload["refresh_token"] = ROTATED_REFRESH
        else:
            payload["refresh_token"] = FIRST_REFRESH
        return FakeResponse(payload)

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(
            {
                "step": "user_info",
                "url": url,
                "body": dict(params or {}),
                "sent_as": "query",
                "headers": dict(headers or {}),
            }
        )
        if "user_info" in self.raise_on:
            raise RuntimeError("connection reset")
        if self.user_info_error is not None:
            # DATA AND AN ERROR IN THE SAME BODY, which is the shape that
            # makes the envelope check load bearing rather than decorative.
            # An error response with no `data` at all would be caught further
            # down by "no user object", so a test built on that shape would
            # pass with the check deleted and prove nothing. An EMPTY user
            # object beside an error is what turns into
            # AudienceSnapshot(None, None) and gets written to a profile as a
            # successful read of an account with no handle and no followers.
            return FakeResponse(
                {"data": {"user": {}}, "error": self.user_info_error},
                status_code=self.user_info_status,
            )
        return FakeResponse(
            {
                "data": {"user": dict(self.user)},
                "error": {"code": "ok", "message": "", "log_id": "202610301245ABCDEF"},
            },
            status_code=self.user_info_status,
        )


@pytest.fixture()
def tiktok(monkeypatch):
    """A fake TikTok installed over httpx, returned so tests can inspect it."""
    fake = FakeTikTok()
    monkeypatch.setattr(oauth.httpx, "post", fake.post)
    monkeypatch.setattr(oauth.httpx, "get", fake.get)
    return fake


def _install(monkeypatch, fake):
    monkeypatch.setattr(oauth.httpx, "post", fake.post)
    monkeypatch.setattr(oauth.httpx, "get", fake.get)
    return fake


def _provider():
    return oauth.TikTokOAuthProvider(CLIENT_KEY, CLIENT_SECRET)


# --------------------------------------------------------------------------
# Registration: nothing changes for a deployment with no credentials
# --------------------------------------------------------------------------


def _no_other_providers(monkeypatch):
    """Clear every OTHER platform's credentials for a registry assertion.

    The mirror of the helper in test_meta_oauth.py, and there for the same
    reason: an assertion about the whole registry is otherwise also an
    assertion about whoever is running the suite."""
    monkeypatch.setattr(oauth.settings, "meta_app_id", "")
    monkeypatch.setattr(oauth.settings, "meta_app_secret", "")


def test_no_tiktok_credentials_still_means_no_provider_at_all(monkeypatch):
    """THE UNCHANGED-BEHAVIOUR TEST, and the reason this PR is inert until
    somebody configures it. A deployment that has not been given a key offers
    nothing new, and POST /profiles/oauth/tiktok/start answers
    oauth_platform_unsupported exactly as it did before this provider
    existed."""
    monkeypatch.setattr(oauth.settings, "tiktok_client_key", "")
    monkeypatch.setattr(oauth.settings, "tiktok_client_secret", "")
    _no_other_providers(monkeypatch)
    assert oauth.build_default_providers() == {}


def test_both_credentials_register_the_tiktok_provider(monkeypatch):
    monkeypatch.setattr(oauth.settings, "tiktok_client_key", CLIENT_KEY)
    monkeypatch.setattr(oauth.settings, "tiktok_client_secret", CLIENT_SECRET)
    _no_other_providers(monkeypatch)
    built = oauth.build_default_providers()
    assert set(built) == {"tiktok"}
    assert isinstance(built["tiktok"], oauth.TikTokOAuthProvider)
    assert built["tiktok"].client_key == CLIENT_KEY


def test_the_two_providers_are_independent_of_each_other(monkeypatch):
    """A box mid-review on one platform is a normal box, not a broken one.

    Meta configured and TikTok not is exactly the state production was in the
    day this was written, and it has to mean one working connect button rather
    than an exception at import time or an empty registry."""
    monkeypatch.setattr(oauth.settings, "meta_app_id", "an-app-id")
    monkeypatch.setattr(oauth.settings, "meta_app_secret", "a-secret")
    monkeypatch.setattr(oauth.settings, "tiktok_client_key", "")
    monkeypatch.setattr(oauth.settings, "tiktok_client_secret", "")
    assert set(oauth.build_default_providers()) == {"facebook"}

    monkeypatch.setattr(oauth.settings, "meta_app_id", "")
    monkeypatch.setattr(oauth.settings, "meta_app_secret", "")
    monkeypatch.setattr(oauth.settings, "tiktok_client_key", CLIENT_KEY)
    monkeypatch.setattr(oauth.settings, "tiktok_client_secret", CLIENT_SECRET)
    assert set(oauth.build_default_providers()) == {"tiktok"}


@pytest.mark.parametrize("key,secret", [(CLIENT_KEY, ""), ("", CLIENT_SECRET)])
def test_half_configured_tiktok_is_treated_as_unconfigured(monkeypatch, key, secret):
    """A client key with no secret cannot complete a token exchange.
    Registering on the key alone only moves the failure to AFTER the creator
    has granted permissions on TikTok's consent screen."""
    monkeypatch.setattr(oauth.settings, "tiktok_client_key", key)
    monkeypatch.setattr(oauth.settings, "tiktok_client_secret", secret)
    _no_other_providers(monkeypatch)
    assert oauth.build_default_providers() == {}


# --------------------------------------------------------------------------
# The authorization URL
# --------------------------------------------------------------------------


def test_the_authorize_url_is_on_tiktok_com_and_names_all_three_scopes():
    url = _provider().authorize_url("the-state", "the-verifier", "https://api.example/cb")
    parsed = urlparse(url)
    # The consent host, not the API host. Pointing this at open.tiktokapis.com
    # does not error, it serves something that is not a consent screen.
    assert parsed.netloc == "www.tiktok.com"
    assert parsed.path == "/v2/auth/authorize/"

    query = parse_qs(parsed.query)
    assert query["client_key"] == [CLIENT_KEY]
    assert query["response_type"] == ["code"]
    assert query["state"] == ["the-state"]
    assert query["redirect_uri"] == ["https://api.example/cb"]

    # COMMA SEPARATED, AND ASSERTED AS THE WHOLE STRING rather than by
    # membership. A space-joined string would still contain all three names,
    # so a test that checked "user.info.stats" in the scope would pass against
    # the exact bug this guards: TikTok reads a space-joined value as one
    # permission that nobody has, the handshake succeeds, and the follower
    # count silently never arrives.
    assert query["scope"] == ["user.info.basic,user.info.profile,user.info.stats"]


def test_the_consent_screen_is_never_skipped_for_a_signed_in_account():
    """disable_auto_auth=1, and it has to be sent rather than assumed.

    TikTok documents 0 as "skip the authorization page for a valid session"
    and 1 as "always show it", and does not document the default. Two things
    break if the screen is skipped, and neither announces itself: a creator
    reconnecting never sees the three permissions they are granting over
    their own audience data, and the App Review demo video loses the only
    frame where a reviewer can see the scopes named."""
    url = _provider().authorize_url("the-state", "the-verifier", "https://api.example/cb")
    assert parse_qs(urlparse(url).query)["disable_auto_auth"] == ["1"]


def test_no_pkce_parameter_reaches_tiktok():
    """The verifier is accepted and forwarded nowhere.

    TikTok documents code_verifier as required only for mobile and desktop
    apps, and documents no code_challenge on the web authorization request.
    This app is registered Web only. Sending a challenge the endpoint ignores
    would be a claim of protection that is not there.

    THE DAY ANDROID OR IOS IS ADDED TO THE APP THIS TEST IS WRONG, and that is
    the intent: a native client cannot hold the secret, PKCE stops being
    optional, and this file should be what says so."""
    url = _provider().authorize_url("the-state", "the-verifier", "https://api.example/cb")
    query = parse_qs(urlparse(url).query)
    assert "code_challenge" not in query
    assert "code_challenge_method" not in query
    assert "the-verifier" not in url


def test_the_client_secret_never_reaches_the_authorize_url():
    """The consent URL goes to a browser, into history, and into any referrer
    that follows. The key belongs there; the secret never does."""
    url = _provider().authorize_url("the-state", "the-verifier", "https://api.example/cb")
    assert CLIENT_SECRET not in url


# --------------------------------------------------------------------------
# The exchange
# --------------------------------------------------------------------------


def test_the_exchange_is_one_call_and_stores_what_it_returns(tiktok):
    """ONE CALL, unlike Meta's two. There is no short-lived token to launder
    into a long-lived one here: what the code buys is what gets stored."""
    tokens = _provider().exchange_code("the-code", "the-verifier", "https://api.example/cb")
    assert tiktok.steps() == ["exchange"]
    assert tokens.access_token == FIRST_ACCESS
    assert tokens.refresh_token == FIRST_REFRESH
    assert tokens.access_expires_in == ACCESS_LIFETIME
    assert tokens.refresh_expires_in == REFRESH_LIFETIME
    assert tokens.provider_user_id == OPEN_ID


def test_the_exchange_records_the_granted_scope_not_the_requested_one(monkeypatch):
    """THE FIRST PROVIDER HERE THAT CAN TELL THE DIFFERENCE.

    Meta's token response carries no scope, so MetaOAuthProvider writes None
    rather than echoing its own request into a column that means the grant.
    TikTok states what was actually GRANTED, so SocialToken.scope finally
    holds an answer to its own question.

    THE FAKE DELIBERATELY RETURNS LESS THAN WAS ASKED FOR, which is the live
    case: a creator who unticks the stats permission on the consent screen.
    A provider that echoed its own request would write all three names here
    and the profile would record a permission nobody granted."""
    declined = "user.info.basic,user.info.profile"
    _install(monkeypatch, FakeTikTok(scope=declined))
    tokens = _provider().exchange_code("c", "v", "https://api.example/cb")
    assert tokens.scope == declined
    assert "user.info.stats" not in tokens.scope


def test_the_token_call_is_form_encoded_and_never_json(tiktok):
    """THE ENCODING BUG THAT READS LIKE A PARAMETER BUG.

    TikTok's token endpoint documents application/x-www-form-urlencoded. httpx
    sends that for `data=` and JSON for `json=`. The same dict passed the
    wrong way produces a well formed request that the endpoint refuses with a
    complaint about a missing grant_type, which sends the next reader looking
    at the parameters."""
    _provider().exchange_code("the-code", "the-verifier", "https://api.example/cb")
    call = [c for c in tiktok.calls if c["step"] == "exchange"][0]
    assert call["sent_as"] == "form"
    assert call["headers"].get("Content-Type") == "application/x-www-form-urlencoded"
    assert call["url"] == "https://open.tiktokapis.com/v2/oauth/token/"


def test_the_exchange_sends_the_secret_and_the_redirect_uri(tiktok):
    _provider().exchange_code("the-code", "the-verifier", "https://api.example/cb")
    body = tiktok.body_for("exchange")
    assert body["client_key"] == CLIENT_KEY
    assert body["client_secret"] == CLIENT_SECRET
    assert body["grant_type"] == "authorization_code"
    assert body["code"] == "the-code"
    # Byte for byte what authorize_url sent, because both take it from
    # oauth_service.redirect_uri. TikTok compares them and refuses a mismatch
    # without naming either.
    assert body["redirect_uri"] == "https://api.example/cb"
    # No PKCE, on the web flow.
    assert "code_verifier" not in body


def test_a_token_response_with_no_access_expiry_falls_back(monkeypatch):
    """Erring short, deliberately. Understating costs a creator an early
    reconnection; overstating produces a connection that reports itself
    healthy while every call it makes is refused."""
    _install(monkeypatch, FakeTikTok(expires_in=None))
    tokens = _provider().exchange_code("c", "v", "https://api.example/cb")
    assert tokens.access_expires_in == oauth.TIKTOK_ACCESS_FALLBACK_SECONDS


def test_a_token_response_with_no_refresh_expiry_falls_back(monkeypatch):
    _install(monkeypatch, FakeTikTok(refresh_expires_in=None))
    tokens = _provider().exchange_code("c", "v", "https://api.example/cb")
    assert tokens.refresh_expires_in == oauth.TIKTOK_REFRESH_FALLBACK_SECONDS


def test_a_token_response_with_no_scope_claims_nothing(monkeypatch):
    """None is the honest answer when TikTok said nothing, and it is NOT the
    same as writing back what we asked for."""
    _install(monkeypatch, FakeTikTok(scope=None))
    tokens = _provider().exchange_code("c", "v", "https://api.example/cb")
    assert tokens.scope is None


def test_a_refused_exchange_raises_rather_than_returning_something_empty(monkeypatch):
    """A failed exchange means there is NO CONNECTION, so it has to be
    impossible to mistake for a call that succeeded and returned nothing.
    oauth_service turns this into oauth_exchange_failed."""
    _install(monkeypatch, FakeTikTok(fail=("exchange",)))
    with pytest.raises(oauth.TikTokOAuthError) as caught:
        _provider().exchange_code("the-code", "v", "https://api.example/cb")
    message = str(caught.value)
    assert "invalid_grant" in message
    # log_id is the one string TikTok support asks for.
    assert "202610301244ABCDEF" in message


def test_a_network_failure_is_a_tiktok_error_not_a_stray_exception(monkeypatch):
    _install(monkeypatch, FakeTikTok(raise_on=("exchange",)))
    with pytest.raises(oauth.TikTokOAuthError):
        _provider().exchange_code("the-code", "v", "https://api.example/cb")


def test_a_token_response_with_no_access_token_is_a_failure(monkeypatch):
    class NoToken(FakeTikTok):
        def post(self, url, data=None, json=None, headers=None, timeout=None):
            self.calls.append(
                {"step": "exchange", "url": url, "body": dict(data or {}), "sent_as": "form",
                 "headers": dict(headers or {})}
            )
            return FakeResponse({"open_id": OPEN_ID, "expires_in": ACCESS_LIFETIME})

    _install(monkeypatch, NoToken())
    with pytest.raises(oauth.TikTokOAuthError):
        _provider().exchange_code("the-code", "v", "https://api.example/cb")


# --------------------------------------------------------------------------
# Refresh, and the rotation that is the whole reason it matters
# --------------------------------------------------------------------------


def test_the_refresh_returns_the_rotated_token_rather_than_the_one_sent(tiktok):
    """THE PROVIDER HALF OF THE ROTATION RULE.

    The service half lives in oauth_service.save_tokens and is pinned in
    test_social_oauth.py against a FakeProvider. This is the line that says
    the real provider actually hands the new value up, which is what makes
    the other test about something."""
    tokens = _provider().refresh(FIRST_REFRESH)
    assert tokens.refresh_token == ROTATED_REFRESH
    assert tokens.refresh_token != FIRST_REFRESH
    assert tokens.access_token == SECOND_ACCESS


def test_the_refresh_sends_exactly_the_four_fields_tiktok_takes(tiktok):
    """NO redirect_uri AND NO code, which is not an omission. TikTok's refresh
    grant takes four fields and refuses extras."""
    _provider().refresh(FIRST_REFRESH)
    body = tiktok.body_for("refresh")
    assert set(body) == {"client_key", "client_secret", "grant_type", "refresh_token"}
    assert body["grant_type"] == "refresh_token"
    assert body["refresh_token"] == FIRST_REFRESH


def test_a_refresh_that_rotates_nothing_leaves_the_stored_token_alone(monkeypatch):
    """ABSENT MEANS UNCHANGED, NOT REVOKED. A provider that declines to rotate
    on a given renewal has not taken anything away, and save_tokens reads None
    as "keep what you have"."""
    _install(monkeypatch, FakeTikTok(rotate=False))
    tokens = _provider().refresh(FIRST_REFRESH)
    assert tokens.refresh_token is None
    assert tokens.access_token == SECOND_ACCESS


def test_a_refused_refresh_raises(monkeypatch):
    _install(monkeypatch, FakeTikTok(fail=("refresh",)))
    with pytest.raises(oauth.TikTokOAuthError):
        _provider().refresh(FIRST_REFRESH)


# --------------------------------------------------------------------------
# The audience read
# --------------------------------------------------------------------------


def test_the_audience_read_asks_for_the_fields_each_scope_paid_for(tiktok):
    _provider().read_audience(
        oauth.TokenSet(FIRST_ACCESS, FIRST_REFRESH, ACCESS_LIFETIME, REFRESH_LIFETIME, None, OPEN_ID)
    )
    call = [c for c in tiktok.calls if c["step"] == "user_info"][0]
    assert call["url"] == "https://open.tiktokapis.com/v2/user/info/"
    assert call["body"]["fields"] == "username,display_name,follower_count"
    # The creator's own bearer token, not the app's credentials.
    assert call["headers"]["Authorization"] == f"Bearer {FIRST_ACCESS}"
    assert CLIENT_SECRET not in str(call)


def test_the_handle_is_the_username_and_not_the_display_name(tiktok):
    """display_name is a label a creator can change and two creators can
    share. username is the @handle their audience types and the platform
    guarantees unique. A profile card showing the display name would show the
    less identifying of the two."""
    snapshot = _provider().read_audience(_tokens())
    assert snapshot.handle == USERNAME
    assert snapshot.handle != DISPLAY_NAME
    assert snapshot.follower_count == FOLLOWERS


def test_the_display_name_is_the_fallback_when_the_profile_scope_was_declined(monkeypatch):
    """A creator who unticks user.info.profile reaches here with a readable
    response and no username. A display name is worse than a handle and much
    better than a numeric open_id on a brand's shortlist."""
    _install(monkeypatch, FakeTikTok(user={"display_name": DISPLAY_NAME, "follower_count": 12}))
    snapshot = _provider().read_audience(_tokens())
    assert snapshot.handle == DISPLAY_NAME
    assert snapshot.follower_count == 12


def test_a_declined_stats_scope_is_no_number_rather_than_a_zero(monkeypatch):
    """TikTok omits the field instead of refusing the call. None is the honest
    record of "they did not let us look", and a zero would be a claim about
    their audience that we would then stamp as the platform's own word."""
    _install(monkeypatch, FakeTikTok(user={"username": USERNAME, "display_name": DISPLAY_NAME}))
    snapshot = _provider().read_audience(_tokens())
    assert snapshot.handle == USERNAME
    assert snapshot.follower_count is None


def test_a_creator_with_no_followers_yet_reports_zero_rather_than_nothing(monkeypatch):
    """Zero is a fact about that account and a brand is entitled to see it.
    The floor on this field is 0, unlike expires_in, whose floor is 1."""
    _install(monkeypatch, FakeTikTok(user={"username": USERNAME, "follower_count": 0}))
    snapshot = _provider().read_audience(_tokens())
    assert snapshot.follower_count == 0


def test_an_http_200_carrying_an_error_is_a_failure_and_not_an_empty_profile(monkeypatch):
    """THE ONE THAT FAILS SILENTLY IF READ BY STATUS ALONE.

    /v2/user/info/ answers a refused token with HTTP 200 and an error object.
    Trusting the status turns that into a snapshot of Nones, which is exactly
    what a creator who declined every scope also produces, and which
    _apply_audience would then treat as a successful read."""
    _install(
        monkeypatch,
        FakeTikTok(
            user_info_error={
                "code": "access_token_invalid",
                "message": "The access token is invalid or not found.",
                "log_id": "202610301246ABCDEF",
            },
            user_info_status=200,
        ),
    )
    assert _provider().read_audience(_tokens()) is None


def test_the_ok_code_is_not_mistaken_for_a_failure(tiktok):
    """The mirror of the test above, and the reason it is here: an envelope
    whose code is literally "ok" is a success, and a check that only looked
    for the presence of an `error` key would refuse every healthy response."""
    assert _provider().read_audience(_tokens()) is not None


def test_a_failed_audience_read_returns_none_and_never_raises(monkeypatch):
    """THE AudienceReader CONTRACT, and it matters more here than anywhere
    else in this provider: this runs AFTER the tokens are stored, so an
    exception escaping turns a connection that succeeded into one the creator
    is told failed, over a follower count."""
    _install(monkeypatch, FakeTikTok(raise_on=("user_info",)))
    assert _provider().read_audience(_tokens()) is None


def test_an_unreadable_audience_response_returns_none(monkeypatch):
    class NotJson(FakeTikTok):
        def get(self, url, params=None, headers=None, timeout=None):
            self.calls.append({"step": "user_info", "url": url, "body": {}, "sent_as": "query",
                               "headers": dict(headers or {})})

            class Broken:
                status_code = 200

                def json(self):
                    raise ValueError("not json")

            return Broken()

    _install(monkeypatch, NotJson())
    assert _provider().read_audience(_tokens()) is None


def test_the_provider_offers_no_page_picker(tiktok):
    """ONE AUTHORIZATION IS ONE ACCOUNT. Meta needs a picker because a person
    can administer several Pages and nothing says which one they sell. A
    TikTok creator who authorises IS the account, so oauth_service's getattr
    lookup must find nothing here and refuse the picker endpoints cleanly."""
    assert not hasattr(_provider(), "list_pages")


def _tokens():
    return oauth.TokenSet(
        FIRST_ACCESS, FIRST_REFRESH, ACCESS_LIFETIME, REFRESH_LIFETIME, GRANTED_SCOPE, OPEN_ID
    )


# --------------------------------------------------------------------------
# End to end, through the router
# --------------------------------------------------------------------------


@pytest.fixture()
def auth_client():
    """Named `auth_client`, not `client`, and that is load-bearing.

    The autouse fixture in backend/conftest.py rebinds `profile_owner` to
    `lambda user_id: user_id` for any test using a fixture named `client`, and
    POST /profiles/oauth/{platform}/start has no `user_id` in its path: under
    that override FastAPI turns `user_id` into a required QUERY parameter and
    the route answers 422. Same trick, and same reason, as test_meta_oauth.py.
    """
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
    app.add_exception_handler(AppError, app_error_handler)
    c = TestClient(app)
    c.session_factory = ts
    return c


def _user(client, phone):
    db = client.session_factory()
    try:
        u = User(
            phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x",
            country_code="BJ", role="influencer", is_verified=True
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


def _headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _connect(client, monkeypatch, phone):
    """Register the real TikTok provider and run one whole handshake through it.

    THROUGH THE ROUTER, NOT AROUND IT, and this is the lesson from the account
    deletion bug in KOL-144: a test that assembles the end state by inserting
    rows proves the end state, and the defect lived in the path that builds
    it. So this starts the handshake, reads the state out of the real
    authorize URL, and hands that state back to the real callback."""
    monkeypatch.setattr(oauth_service, "providers", {PLATFORM: _provider()})
    uid = _user(client, phone)
    started = client.post(
        f"/profiles/oauth/{PLATFORM}/start", json={}, headers=_headers(uid)
    )
    assert started.status_code == 200, started.text
    query = parse_qs(urlparse(started.json()["authorize_url"]).query)
    assert query["redirect_uri"] == [oauth_service.redirect_uri(PLATFORM)]
    state = query["state"][0]
    done = client.get(
        f"/profiles/oauth/{PLATFORM}/callback", params={"code": "the-code", "state": state}
    )
    return uid, done


def _stored_token(client, account_id):
    db = client.session_factory()
    try:
        row = (
            db.query(models.SocialToken)
            .filter(models.SocialToken.social_account_id == account_id)
            .first()
        )
        if row is None:
            return None
        return row
    finally:
        db.close()


def test_a_whole_connection_stores_both_tokens_and_the_granted_scope(
    auth_client, monkeypatch, tiktok
):
    _uid, done = _connect(auth_client, monkeypatch, "+22990004001")
    assert done.status_code == 200, done.text
    account = done.json()["account"]

    row = _stored_token(auth_client, account["id"])
    assert decrypt_bytes(row.access_token_ciphertext).decode() == FIRST_ACCESS
    # THE REFRESH TOKEN IS THE PART META NEVER HAD. Without it this connection
    # is dead within 24 hours and nothing would say why.
    assert decrypt_bytes(row.refresh_token_ciphertext).decode() == FIRST_REFRESH
    assert row.scope == GRANTED_SCOPE
    assert row.provider_user_id == OPEN_ID
    assert row.refresh_expires_at > models.utcnow() + timedelta(days=300)


def test_the_follower_count_is_stamped_as_the_platforms_own_word(
    auth_client, monkeypatch, tiktok
):
    """The whole reason user.info.stats is requested. A number TikTok stated
    about its own account is the only kind that earns PLATFORM_API and a
    verified date, and it is what a brand shortlists on."""
    _uid, done = _connect(auth_client, monkeypatch, "+22990004002")
    account = done.json()["account"]
    assert account["handle"] == USERNAME
    assert account["follower_count"] == FOLLOWERS

    db = auth_client.session_factory()
    try:
        row = db.query(models.SocialAccount).filter(
            models.SocialAccount.id == account["id"]
        ).first()
        assert row.follower_source == models.PLATFORM_API
        assert row.follower_verified_at is not None
    finally:
        db.close()


def test_a_rotated_refresh_token_is_what_survives_the_renewal(
    auth_client, monkeypatch, tiktok
):
    """THE REGRESSION GUARD FOR THE WHOLE PROVIDER, and the one defect in this
    subsystem with no symptom at the time it happens.

    TikTok retires a refresh token the moment it issues a replacement. Write
    the old one back and the refresh still SUCCEEDS, the caller gets a working
    access token, the creator sees nothing. The connection dies at the NEXT
    renewal, a day or a week later.

    RUN THROUGH load_access_token RATHER THAN BY CALLING save_tokens, because
    the seam between the provider and the service is where this breaks."""
    _uid, done = _connect(auth_client, monkeypatch, "+22990004003")
    account_id = done.json()["account"]["id"]

    db = auth_client.session_factory()
    try:
        row = (
            db.query(models.SocialToken)
            .filter(models.SocialToken.social_account_id == account_id)
            .first()
        )
        # Age the access token past its life, exactly as 24 hours would.
        row.access_expires_at = models.utcnow() - timedelta(minutes=1)
        db.commit()

        renewed = oauth_service.load_access_token(db, account_id)
        assert renewed == SECOND_ACCESS

        db.refresh(row)
        kept = decrypt_bytes(row.refresh_token_ciphertext).decode()
        assert kept == ROTATED_REFRESH, "the retired refresh token was written back"
        assert kept != FIRST_REFRESH
    finally:
        db.close()


def test_a_tiktok_refusal_reaches_the_creator_as_one_readable_sentence(
    auth_client, monkeypatch
):
    """TikTokOAuthError never reaches a creator. oauth_service turns every
    exception out of a provider into oauth_exchange_failed, and the secret in
    the request body is not in what comes back."""
    _install(monkeypatch, FakeTikTok(fail=("exchange",)))
    _uid, done = _connect(auth_client, monkeypatch, "+22990004004")
    assert CLIENT_SECRET not in done.text
    assert "invalid_grant" not in done.text


def test_a_failed_audience_read_leaves_the_connection_standing(auth_client, monkeypatch):
    """The AudienceReader contract, end to end. A follower count that could
    not be read is a profile field left empty, never a failed connection."""
    _install(monkeypatch, FakeTikTok(raise_on=("user_info",)))
    _uid, done = _connect(auth_client, monkeypatch, "+22990004005")
    assert done.status_code == 200, done.text
    account = done.json()["account"]
    assert account["follower_count"] is None
    assert _stored_token(auth_client, account["id"]) is not None


# --- The client secret cannot reach a log line -------------------------------


def test_the_secret_is_struck_out_of_a_quoted_error(monkeypatch):
    """TikTok's error_description is free text, and nothing in TikTok's
    documentation establishes that it cannot quote a request parameter back.
    Treated as unverified rather than as safe, exactly as Meta's `message` is
    after KOL-108."""

    class Echoing(FakeTikTok):
        def post(self, url, data=None, json=None, headers=None, timeout=None):
            body = dict(data or {})
            self.calls.append({"step": "exchange", "url": url, "body": body,
                               "sent_as": "form", "headers": dict(headers or {})})
            return FakeResponse(
                {
                    "error": "invalid_client",
                    "error_description": f"client_secret {body['client_secret']} is wrong",
                    "log_id": "202610301247ABCDEF",
                },
                status_code=400,
            )

    _install(monkeypatch, Echoing())
    with pytest.raises(oauth.TikTokOAuthError) as caught:
        _provider().exchange_code("the-code", "v", "https://api.example/cb")
    assert CLIENT_SECRET not in str(caught.value)
    assert "202610301247ABCDEF" in str(caught.value)


def test_the_code_is_struck_out_of_a_quoted_error(monkeypatch):
    """An authorization code is still spendable at the moment the first token
    call fails, which is the moment this error is built."""

    class Echoing(FakeTikTok):
        def post(self, url, data=None, json=None, headers=None, timeout=None):
            body = dict(data or {})
            self.calls.append({"step": "exchange", "url": url, "body": body,
                               "sent_as": "form", "headers": dict(headers or {})})
            return FakeResponse(
                {"error": "invalid_grant", "error_description": f"code {body['code']} expired"},
                status_code=400,
            )

    _install(monkeypatch, Echoing())
    with pytest.raises(oauth.TikTokOAuthError) as caught:
        _provider().exchange_code("a-very-distinctive-code", "v", "https://api.example/cb")
    assert "a-very-distinctive-code" not in str(caught.value)


def test_the_refresh_token_is_struck_out_of_a_quoted_error(monkeypatch):
    """The longest lived secret this subsystem handles: 365 days."""

    class Echoing(FakeTikTok):
        def post(self, url, data=None, json=None, headers=None, timeout=None):
            body = dict(data or {})
            self.calls.append({"step": "refresh", "url": url, "body": body,
                               "sent_as": "form", "headers": dict(headers or {})})
            return FakeResponse(
                {"error": "invalid_grant",
                 "error_description": f"refresh_token {body['refresh_token']} retired"},
                status_code=400,
            )

    _install(monkeypatch, Echoing())
    with pytest.raises(oauth.TikTokOAuthError) as caught:
        _provider().refresh(FIRST_REFRESH)
    assert FIRST_REFRESH not in str(caught.value)

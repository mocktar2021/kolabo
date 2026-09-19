"""The Meta provider, proved against a fake Graph API.

NO NETWORK, NO APP, NO REVIEW. httpx.get is monkeypatched with canned
responses shaped like the real ones — the same treatment test_enrichment.py
gives the enrichers, and the same reason: none of this should need a Meta app
to stay honest in CI.

A SEPARATE FILE FROM test_social_oauth.py ON PURPOSE. That one pins the
MECHANISM — the state row, the encryption, the rotation rule — against a
FakeProvider, and it is unchanged by this PR: a real provider arriving must not
require editing the fake that guards the rules it obeys. This one pins ONE
PLATFORM's endpoints and quirks. When Meta changes something, exactly one of
these two files should go red, and it should be this one.

WHAT IS ACTUALLY BEING GUARDED, in rough order of how quietly it fails:

  * THE SHORT-LIVED TOKEN BEING WHAT GETS STORED. Meta answers an
    authorization code with a token that expires "in hours". Storing it is a
    connection that dies before onboarding finishes, and it fails with no
    symptom at all: the exchange SUCCEEDED, nothing throws, nothing logs. Only
    the second call — fb_exchange_token — produces the ~60 day token, and
    test_the_short_lived_token_is_never_what_gets_stored is the line that says
    so.
  * A MISSING REFRESH TOKEN BLANKING SOMETHING. Meta issues none, ever, so
    every TokenSet it produces carries None. save_tokens reads absent as
    "unchanged" rather than "revoked", which is what makes that safe rather
    than destructive.
  * A MULTI-PAGE CREATOR HAVING A PAGE PICKED FOR THEM. Three Pages is a
    question, not a fact, and answering it by taking the first or the biggest
    is us deciding which of somebody's businesses is their identity.
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

PLATFORM = "facebook"
VERSION = "v26.0"
APP_ID = "1888079209231475"
APP_SECRET = "not-a-real-secret"

SHORT_LIVED = "SHORT-lived-token-that-dies-in-hours"
LONG_LIVED = "LONG-lived-token-good-for-sixty-days"
ME_ID = "app-scoped-user-id-1"

ONE_PAGE = [{"id": "page-1", "name": "Chez Adjo", "followers_count": 12400, "fan_count": 11900}]
TWO_PAGES = [
    {"id": "page-1", "name": "Chez Adjo", "followers_count": 12400},
    {"id": "page-2", "name": "Adjo Traiteur", "followers_count": 800},
]

# THE LIVE CASE THE PICKER EXISTS FOR, with the names changed. One creator,
# four Pages: a gossip page, their own buzz page, a beauty page, and a tech
# company whose account they merely administer. Four is a question and not a
# fact, so read_audience answered it with None and the creator was left looking
# at a numeric app-scoped id where a name should be, no follower count, and
# nothing on screen to say why.
#
# DELIBERATELY NOT IN SIZE ORDER. The platform's order is the platform's
# business, and the list endpoint is the thing that has to impose one.
FOUR_PAGES = [
    {"id": "page-tech", "name": "Zinsou Technologies", "followers_count": 300},
    {"id": "page-gossip", "name": "Cotonou Gossip", "followers_count": 184000},
    {"id": "page-beauty", "name": "Beaute by Adjo", "followers_count": 9100},
    {"id": "page-buzz", "name": "Adjo Buzz", "followers_count": 42000},
]
PAGE_BY_ID = {page["id"]: page for page in FOUR_PAGES}

# Somebody else's Page entirely, and the largest one in this file. Used to
# prove that a page_id from a client is worth nothing on its own: the only
# thing that makes a Page selectable is the creator's own token seeing it.
STRANGER_PAGES = [
    {"id": "page-stranger", "name": "Someone Else Media", "followers_count": 990000},
]


# --------------------------------------------------------------------------
# The fake Graph
# --------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeGraph:
    """Everything Meta would answer, and a record of what it was asked.

    Routed on the URL rather than on call order, so a test that asserts about
    the fb_exchange_token call is asserting about the RIGHT call even if the
    provider's internal ordering changes.
    """

    def __init__(self, *, pages=None, expires_in=5184000, fail=(), raise_on=()):
        self.calls = []
        self.pages = list(pages) if pages is not None else list(ONE_PAGE)
        self.expires_in = expires_in
        # Step names that answer with a Meta error envelope and a 400.
        self.fail = set(fail)
        # Step names whose socket falls over before an answer exists at all.
        self.raise_on = set(raise_on)

    def params_for(self, step: str) -> dict:
        """The params of the one call for a step, so a test can read them."""
        matches = [params for name, _url, params in self.calls if name == step]
        assert len(matches) == 1, f"expected exactly one {step} call, got {len(matches)}"
        return matches[0]

    def steps(self) -> list:
        return [name for name, _url, _params in self.calls]

    def __call__(self, url, params=None, timeout=None):
        params = dict(params or {})
        step = self._step(url, params)
        self.calls.append((step, url, params))
        if step in self.raise_on:
            raise RuntimeError("connection reset")
        if step in self.fail:
            return FakeResponse(
                {
                    "error": {
                        "message": "Invalid OAuth access token.",
                        "type": "OAuthException",
                        "code": 190,
                        "fbtrace_id": "AbC123",
                    }
                },
                status_code=400,
            )
        if step == "short":
            return FakeResponse(
                {"access_token": SHORT_LIVED, "token_type": "bearer", "expires_in": 3600}
            )
        if step == "long":
            body = {"access_token": LONG_LIVED, "token_type": "bearer"}
            if self.expires_in is not None:
                body["expires_in"] = self.expires_in
            return FakeResponse(body)
        if step == "me":
            return FakeResponse({"id": ME_ID})
        if step == "accounts":
            return FakeResponse({"data": self.pages})
        raise AssertionError(f"unexpected Graph call: {url}")

    @staticmethod
    def _step(url, params):
        if url.endswith("/oauth/access_token"):
            return "long" if params.get("grant_type") == "fb_exchange_token" else "short"
        if url.endswith("/me"):
            return "me"
        if url.endswith("/accounts"):
            return "accounts"
        return "unknown"


@pytest.fixture()
def graph(monkeypatch):
    """A fake Graph installed over httpx, returned so tests can inspect it."""
    fake = FakeGraph()
    monkeypatch.setattr(oauth.httpx, "get", fake)
    return fake


def _provider():
    return oauth.MetaOAuthProvider(APP_ID, APP_SECRET, VERSION)


# --------------------------------------------------------------------------
# Registration: nothing changes for a deployment with no credentials
# --------------------------------------------------------------------------


def test_no_meta_credentials_still_means_no_provider_at_all(monkeypatch):
    """THE UNCHANGED-BEHAVIOUR TEST, and the reason this PR is inert until
    somebody configures it. With no app id and no secret the registry is empty,
    exactly as #162 shipped it, and every platform still answers
    oauth_platform_unsupported."""
    monkeypatch.setattr(oauth.settings, "meta_app_id", "")
    monkeypatch.setattr(oauth.settings, "meta_app_secret", "")
    assert oauth.build_default_providers() == {}


def test_both_credentials_register_the_facebook_provider(monkeypatch):
    monkeypatch.setattr(oauth.settings, "meta_app_id", APP_ID)
    monkeypatch.setattr(oauth.settings, "meta_app_secret", APP_SECRET)
    monkeypatch.setattr(oauth.settings, "meta_graph_version", VERSION)
    built = oauth.build_default_providers()
    assert set(built) == {"facebook"}
    assert isinstance(built["facebook"], oauth.MetaOAuthProvider)
    # The pinned version reaches the provider rather than being defaulted
    # inside it, so ageing it out is one setting rather than a code change.
    assert built["facebook"].version == VERSION


@pytest.mark.parametrize(
    "app_id,app_secret", [(APP_ID, ""), ("", APP_SECRET)]
)
def test_half_configured_is_treated_as_unconfigured(monkeypatch, app_id, app_secret):
    """An app id with no secret cannot complete a token exchange. Registering
    on the id alone would only move the failure to AFTER the creator has
    granted permissions on Meta's consent screen, which is the worst available
    moment to discover a server is misconfigured."""
    monkeypatch.setattr(oauth.settings, "meta_app_id", app_id)
    monkeypatch.setattr(oauth.settings, "meta_app_secret", app_secret)
    assert oauth.build_default_providers() == {}


# --------------------------------------------------------------------------
# The authorization URL
# --------------------------------------------------------------------------


def test_the_authorize_url_is_on_facebook_com_and_names_both_permissions():
    """The dialog is on www.facebook.com; everything else is graph.facebook.com.
    Sending the dialog to the Graph host does not error, it serves a page that
    is not a consent screen.

    The two scopes are asserted by name because App Review grants them one at a
    time against a demonstrated use: a scope here that the demo video does not
    show being used is a rejected submission.
    """
    url = _provider().authorize_url("the-state", "the-verifier", "https://api.example/cb")
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "www.facebook.com"
    assert parsed.path == f"/{VERSION}/dialog/oauth"

    query = parse_qs(parsed.query)
    assert query["client_id"] == [APP_ID]
    assert query["state"] == ["the-state"]
    assert query["redirect_uri"] == ["https://api.example/cb"]
    assert query["response_type"] == ["code"]
    # Comma separated, which is Meta's spelling and not OAuth's space. A
    # space-joined string is read as one permission with an odd name, granted
    # to nobody, and the handshake then succeeds with nothing at all.
    assert query["scope"] == ["pages_show_list,pages_read_engagement"]


def test_no_pkce_parameter_reaches_either_meta_endpoint(graph):
    """THE PKCE DECISION, WRITTEN AS A TEST.

    The service mints a verifier for every authorization and hands it to both
    provider methods. This provider accepts both and forwards neither: Meta
    does not document PKCE for the manual login flow these endpoints belong to
    (its PKCE documentation is scoped to the OIDC/limited-login flow, which is
    a different handshake), so a challenge here is a parameter nobody has
    agreed to remember and a verifier at the token endpoint is one nobody has
    agreed to check.

    Sending them anyway would not break anything. It would be worse than that:
    it would make this code look PKCE-protected when the other side has not
    agreed to protect it. What actually protects the exchange is client_secret,
    which a browser never sees.
    """
    url = _provider().authorize_url("the-state", "the-verifier", "https://api.example/cb")
    assert "code_challenge" not in url
    assert "code_challenge_method" not in url
    assert "the-verifier" not in url

    _provider().exchange_code("the-code", "the-verifier", "https://api.example/cb")
    for _step, _url, params in graph.calls:
        assert "code_verifier" not in params
        assert "code_challenge" not in params
        assert "the-verifier" not in params.values()


# --------------------------------------------------------------------------
# The exchange, and the second call that is the whole point of it
# --------------------------------------------------------------------------


def test_the_exchange_spends_the_short_lived_token_on_a_long_lived_one(graph):
    """Two calls to the token endpoint, in order, and the second one carries
    the first one's answer as fb_exchange_token."""
    tokens = _provider().exchange_code("the-code", "verifier", "https://api.example/cb")

    assert graph.steps() == ["short", "long", "me"]

    first = graph.params_for("short")
    assert first["client_id"] == APP_ID
    assert first["client_secret"] == APP_SECRET
    assert first["code"] == "the-code"
    # Byte for byte the same string the authorize URL carried. Meta compares
    # them and answers redirect_uri_mismatch, which names neither of them.
    assert first["redirect_uri"] == "https://api.example/cb"

    second = graph.params_for("long")
    assert second["grant_type"] == "fb_exchange_token"
    assert second["fb_exchange_token"] == SHORT_LIVED
    assert second["client_id"] == APP_ID
    assert second["client_secret"] == APP_SECRET

    assert tokens.access_token == LONG_LIVED
    assert tokens.access_expires_in == 5184000
    assert tokens.provider_user_id == ME_ID


def test_the_exchange_returns_no_refresh_token_and_claims_no_scope(graph):
    """Meta issues no refresh token, so None is the honest answer rather than a
    gap somebody fills in later.

    Scope is None for a related reason: Meta's token response carries none, so
    the only string available is the one we ASKED for, and SocialToken.scope
    means what was GRANTED. Writing the request into that column would turn a
    question into an answer — and it is exactly the question somebody needs
    answered honestly the first time a creator unticks a permission.
    """
    tokens = _provider().exchange_code("the-code", "verifier", "https://api.example/cb")
    assert tokens.refresh_token is None
    assert tokens.refresh_expires_in is None
    assert tokens.scope is None


def test_a_token_response_with_no_expiry_falls_back_to_sixty_days(monkeypatch):
    """Erring short is the safe direction: understating it asks a creator to
    reconnect a little early, overstating it leaves a connection reporting
    itself healthy while every call it makes is refused."""
    fake = FakeGraph(expires_in=None)
    monkeypatch.setattr(oauth.httpx, "get", fake)
    tokens = _provider().exchange_code("the-code", "verifier", "https://api.example/cb")
    assert tokens.access_expires_in == oauth.META_LONG_LIVED_FALLBACK_SECONDS


def test_a_refused_exchange_raises_rather_than_returning_something_empty(monkeypatch):
    """The protocol's rule: providers RAISE on failure. oauth_service turns
    that into oauth_exchange_failed; returning a half-built TokenSet would let
    a failure be stored as a connection."""
    fake = FakeGraph(fail={"short"})
    monkeypatch.setattr(oauth.httpx, "get", fake)
    with pytest.raises(oauth.MetaOAuthError) as raised:
        _provider().exchange_code("the-code", "verifier", "https://api.example/cb")
    # fbtrace_id is the one string Meta support asks for, so it has to survive
    # into the message that reaches the log.
    assert "AbC123" in str(raised.value)
    assert fake.steps() == ["short"], "nothing is attempted after a refusal"


def test_a_failed_long_lived_exchange_is_not_quietly_downgraded(monkeypatch):
    """The failure mode this whole two-call dance exists to prevent: falling
    back to the short-lived token when the second call fails would store a
    credential that dies in hours, and the connection would look fine."""
    fake = FakeGraph(fail={"long"})
    monkeypatch.setattr(oauth.httpx, "get", fake)
    with pytest.raises(oauth.MetaOAuthError):
        _provider().exchange_code("the-code", "verifier", "https://api.example/cb")


def test_a_network_failure_is_a_meta_error_not_a_stray_exception(monkeypatch):
    fake = FakeGraph(raise_on={"short"})
    monkeypatch.setattr(oauth.httpx, "get", fake)
    with pytest.raises(oauth.MetaOAuthError):
        _provider().exchange_code("the-code", "verifier", "https://api.example/cb")


# --------------------------------------------------------------------------
# Refresh: there is none
# --------------------------------------------------------------------------


def test_meta_refresh_says_out_loud_that_it_cannot_be_done():
    """DOCUMENTATION WITH TEETH. Meta's renewal is fb_exchange_token with the
    current ACCESS token, so `refresh(refresh_token)` is handed the one thing
    that does not exist. Raising makes wiring Meta into a renewal loop fail
    loudly instead of silently doing nothing."""
    with pytest.raises(NotImplementedError):
        _provider().refresh("there-is-no-such-thing")


# --------------------------------------------------------------------------
# The Pages read
# --------------------------------------------------------------------------


def _tokens():
    return oauth.TokenSet(
        access_token=LONG_LIVED,
        refresh_token=None,
        access_expires_in=5184000,
        refresh_expires_in=None,
        scope=None,
        provider_user_id=ME_ID,
    )


def test_one_page_is_a_fact_and_is_reported(graph):
    snapshot = _provider().read_audience(_tokens())
    assert snapshot.handle == "Chez Adjo"
    assert snapshot.follower_count == 12400
    # Read with the LONG-LIVED user token, against the verified node.
    params = graph.params_for("accounts")
    assert params["access_token"] == LONG_LIVED
    assert graph.calls[-1][1].endswith(f"/{ME_ID}/accounts")


def test_a_page_reporting_only_likes_falls_back_to_fan_count(monkeypatch):
    """followers_count is the number to show; fan_count is Page likes and is
    kept only for Pages that still report the two separately. Same order and
    same reason as enrichment.FacebookEnricher."""
    fake = FakeGraph(pages=[{"id": "p", "name": "Chez Adjo", "fan_count": 900}])
    monkeypatch.setattr(oauth.httpx, "get", fake)
    assert _provider().read_audience(_tokens()).follower_count == 900


def test_a_page_with_no_followers_yet_reports_zero_rather_than_nothing(monkeypatch):
    """Zero is a fact about that Page and a brand is entitled to see it. It
    must not be swallowed as if it were a missing field."""
    fake = FakeGraph(pages=[{"id": "p", "name": "New Page", "followers_count": 0}])
    monkeypatch.setattr(oauth.httpx, "get", fake)
    assert _provider().read_audience(_tokens()).follower_count == 0


def test_several_pages_answers_nothing_rather_than_guessing(monkeypatch):
    """THE MULTI-PAGE DECISION, WRITTEN AS A TEST.

    A creator managing a restaurant Page, a side project and a client's account
    has not said which one is the audience they are selling, and nothing in the
    response says either. "The first one" is ordered by Meta for Meta's reasons
    and can change between calls. "The biggest one" is us deciding which of
    somebody's businesses is their identity, and it is precisely wrong for the
    creator whose largest Page belongs to a client.

    So: no number. The connection still succeeds — see the end-to-end test
    below — and the creator picks a Page in the app.
    """
    fake = FakeGraph(pages=TWO_PAGES)
    monkeypatch.setattr(oauth.httpx, "get", fake)
    assert _provider().read_audience(_tokens()) is None


def test_no_pages_answers_nothing(monkeypatch):
    """A creator who has not made a Page, or who declined pages_show_list on
    the consent screen. Both are ordinary and neither is an error."""
    fake = FakeGraph(pages=[])
    monkeypatch.setattr(oauth.httpx, "get", fake)
    assert _provider().read_audience(_tokens()) is None


def test_a_failed_pages_lookup_returns_none_and_never_raises(monkeypatch):
    """The AudienceReader contract. This runs after the tokens are stored, so
    an exception escaping it would turn a completed connection into a failed
    one over a follower count."""
    fake = FakeGraph(raise_on={"accounts"})
    monkeypatch.setattr(oauth.httpx, "get", fake)
    assert _provider().read_audience(_tokens()) is None

    refused = FakeGraph(fail={"accounts"})
    monkeypatch.setattr(oauth.httpx, "get", refused)
    assert _provider().read_audience(_tokens()) is None


# --------------------------------------------------------------------------
# The split: list_pages reports, read_audience decides
#
# THE REGRESSION GUARD ON THE REFACTOR, and the part of this file that must not
# be skipped. The Graph call moved out of read_audience into list_pages so that
# the picker could read the same data; the exactly-one rule did not move and
# did not change. The four tests below say so from both ends: what list_pages
# reports, and what read_audience still refuses to do with it.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pages,expected",
    [
        ([], []),
        (ONE_PAGE, ["Chez Adjo"]),
        (TWO_PAGES, ["Chez Adjo", "Adjo Traiteur"]),
        (
            FOUR_PAGES,
            ["Zinsou Technologies", "Cotonou Gossip", "Beaute by Adjo", "Adjo Buzz"],
        ),
    ],
)
def test_list_pages_reports_every_page_in_the_order_meta_gave_them(
    monkeypatch, pages, expected
):
    """The provider REPORTS. It does not filter, count or reorder.

    Ordering is oauth_service.list_pages's job, and keeping it out of here is
    what lets read_audience trust the length of this list: a provider that
    quietly dropped an entry would change which creators are treated as
    ambiguous.
    """
    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(pages=pages))
    assert [page.name for page in _provider().list_pages(_tokens())] == expected


def test_list_pages_carries_the_id_and_the_count_that_read_audience_would_use(
    monkeypatch,
):
    """The same normalisation, because it is the same function. Whatever a
    creator sees in the picker is the name and the number a one-Page connection
    would have recorded on its own."""
    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(pages=ONE_PAGE))
    only = _provider().list_pages(_tokens())[0]
    assert (only.id, only.name, only.follower_count) == ("page-1", "Chez Adjo", 12400)


def test_list_pages_says_none_when_it_could_not_ask_and_empty_when_there_are_none(
    monkeypatch,
):
    """None IS NOT []. None means we could not ask; [] means we asked and the
    creator manages no Pages. A caller that treats them alike will one day tell
    somebody they have no Pages because a socket timed out."""
    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(raise_on={"accounts"}))
    assert _provider().list_pages(_tokens()) is None

    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(fail={"accounts"}))
    assert _provider().list_pages(_tokens()) is None

    # No id to ask about at all, so there is no question to put.
    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(pages=FOUR_PAGES))
    assert (
        _provider().list_pages(
            oauth.TokenSet(
                access_token=LONG_LIVED,
                refresh_token=None,
                access_expires_in=5184000,
                refresh_expires_in=None,
                scope=None,
                provider_user_id=None,
            )
        )
        is None
    )

    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(pages=[]))
    assert _provider().list_pages(_tokens()) == []


@pytest.mark.parametrize("pages", [[], TWO_PAGES, FOUR_PAGES])
def test_read_audience_still_refuses_to_guess_after_the_split(monkeypatch, pages):
    """THE RULE THAT DID NOT MOVE.

    Zero Pages and several Pages are both questions, and the answer is still no
    number at all. Put the exactly-one rule into list_pages, or let
    read_audience take the first or the largest entry now that it can see them
    all, and this goes red.
    """
    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(pages=pages))
    assert _provider().read_audience(_tokens()) is None


def test_read_audience_still_reports_exactly_one_page_after_the_split(monkeypatch):
    """The other half of the same rule: one Page is a fact and is recorded."""
    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(pages=ONE_PAGE))
    snapshot = _provider().read_audience(_tokens())
    assert (snapshot.handle, snapshot.follower_count) == ("Chez Adjo", 12400)


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
    the route answers 422. Same trick, and same reason, as test_social_oauth.py.
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
    """Register the real Meta provider and run one whole handshake through it."""
    monkeypatch.setattr(oauth_service, "providers", {PLATFORM: _provider()})
    uid = _user(client, phone)
    started = client.post(
        f"/profiles/oauth/{PLATFORM}/start", json={}, headers=_headers(uid)
    )
    assert started.status_code == 200, started.text
    query = parse_qs(urlparse(started.json()["authorize_url"]).query)
    # The callback URL the provider was told to send the creator back to is
    # built from settings, not from the request, so it can be checked here.
    #
    # COMPARED AS A DECODED PARAMETER, NOT AS A SUBSTRING OF THE URL, and the
    # difference is a real one rather than a style preference. A substring
    # check passes for test_social_oauth.py's FakeProvider only because that
    # fake interpolates the redirect_uri into its URL raw; a provider that
    # builds its query properly percent-encodes it ("://" becomes "%3A%2F%2F"),
    # so the plain string is not in the URL at all and the check fails against
    # correct code. What actually matters is that the value Meta receives
    # equals the one the token exchange will send, and that is what this
    # compares.
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
        return {
            "access_ciphertext": row.access_token_ciphertext,
            "refresh_ciphertext": row.refresh_token_ciphertext,
            "access_expires_at": row.access_expires_at,
            "refresh_expires_at": row.refresh_expires_at,
            "scope": row.scope,
            "provider_user_id": row.provider_user_id,
        }
    finally:
        db.close()


def test_the_short_lived_token_is_never_what_gets_stored(auth_client, monkeypatch, graph):
    """THE REGRESSION GUARD FOR THE WHOLE PROVIDER.

    Meta answers an authorization code with a token that expires in hours. If
    that is what lands in the database, the exchange still SUCCEEDED — nothing
    throws, nothing logs, the creator sees a connected account — and the
    connection is dead by the next morning. Drop the fb_exchange_token call, or
    return the first response's token, and this goes red here rather than in a
    support queue.
    """
    _uid, done = _connect(auth_client, monkeypatch, "+22990003001")
    assert done.status_code == 200, done.text
    account = done.json()["account"]

    stored = _stored_token(auth_client, account["id"])
    assert decrypt_bytes(stored["access_ciphertext"]).decode() == LONG_LIVED
    assert SHORT_LIVED.encode() not in stored["access_ciphertext"]
    # And it is stored as a credential with a real life ahead of it, not one
    # that expires this afternoon.
    assert stored["access_expires_at"] > models.utcnow() + timedelta(days=30)
    assert stored["provider_user_id"] == ME_ID


def test_nothing_is_blanked_by_a_provider_that_has_no_refresh_token(
    auth_client, monkeypatch, graph
):
    """Meta's TokenSet carries refresh_token=None on every single exchange.
    save_tokens reads absent as "unchanged" rather than "revoked", so a null
    column stays null and nothing that WAS there is destroyed. Reconnecting
    exercises the second half of that: the same account, refreshed
    credentials, and still nothing in the refresh column."""
    uid, done = _connect(auth_client, monkeypatch, "+22990003002")
    account = done.json()["account"]
    first = _stored_token(auth_client, account["id"])
    assert first["refresh_ciphertext"] is None
    assert first["refresh_expires_at"] is None
    # Nothing is claimed about what was granted — see the exchange test.
    assert first["scope"] is None

    # Reconnect. Matched on provider_user_id, so it is the same row.
    monkeypatch.setattr(oauth_service, "providers", {PLATFORM: _provider()})
    again = auth_client.post(
        f"/profiles/oauth/{PLATFORM}/start", json={}, headers=_headers(uid)
    )
    state = parse_qs(urlparse(again.json()["authorize_url"]).query)["state"][0]
    second = auth_client.get(
        f"/profiles/oauth/{PLATFORM}/callback", params={"code": "code-2", "state": state}
    )
    assert second.status_code == 200, second.text
    assert second.json()["account"]["id"] == account["id"]
    assert _stored_token(auth_client, account["id"])["refresh_ciphertext"] is None
    assert len(auth_client.get(f"/profiles/{uid}/social-accounts").json()) == 1


def test_a_lapsed_meta_connection_asks_for_a_reconnection_and_never_calls_refresh(
    auth_client, monkeypatch, graph
):
    """THE RENEWAL DECISION, WRITTEN AS A TEST.

    Meta connections simply expire and the creator reconnects. There is no
    refresh token, so load_access_token refuses on the null column several
    lines before it would look up a provider — which is why
    MetaOAuthProvider.refresh can raise NotImplementedError rather than
    pretend. If that were ever reached, this test would see NotImplementedError
    instead of a readable refusal, and a fourth Graph call in the log.
    """
    _uid, done = _connect(auth_client, monkeypatch, "+22990003003")
    account_id = done.json()["account"]["id"]

    db = auth_client.session_factory()
    try:
        row = (
            db.query(models.SocialToken)
            .filter(models.SocialToken.social_account_id == account_id)
            .first()
        )
        row.access_expires_at = models.utcnow() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    calls_before = len(graph.calls)
    db = auth_client.session_factory()
    try:
        with pytest.raises(AppError) as raised:
            oauth_service.load_access_token(db, account_id)
    finally:
        db.close()
    assert raised.value.code == "oauth_token_expired"
    assert len(graph.calls) == calls_before, "nothing was asked of Meta"


def test_one_page_stamps_the_count_as_the_platforms_own_word(
    auth_client, monkeypatch, graph
):
    """All three provenance columns together, per #161.

    This is the first place in the codebase that earns PLATFORM_API honestly:
    the creator authorised us on Meta's own consent screen, the token is
    theirs, and the number is their own Page's — rather than an app-owned token
    reading a handle somebody typed.
    """
    uid, done = _connect(auth_client, monkeypatch, "+22990003004")
    account = done.json()["account"]

    assert account["follower_count"] == 12400
    assert account["follower_source"] == "platform_api"
    assert account["follower_verified_at"] is not None
    # The numeric app-scoped id the exchange returned, replaced by something a
    # brand can read.
    assert account["handle"] == "Chez Adjo"
    # CONNECTED. The creator authorised a real app on Meta's own consent
    # screen and the number came back through Meta's API on their token, so
    # "pending, like a handle somebody typed" was never a fair description of
    # this row. It is still not verified: see models.CONNECTED.
    assert account["status"] == "connected"
    assert account["method"] == "oauth"

    listed = auth_client.get(f"/profiles/{uid}/social-accounts").json()
    assert listed[0]["follower_count"] == 12400
    assert listed[0]["follower_source"] == "platform_api"


def test_several_pages_connects_the_account_but_records_no_number(
    auth_client, monkeypatch
):
    """The connection is worth having on its own. What is missing is a number
    nobody can supply without guessing which Page the creator meant — and a
    null count keeps a null source with it, because a source beside no number
    would claim a report nobody made."""
    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(pages=TWO_PAGES))
    uid, done = _connect(auth_client, monkeypatch, "+22990003005")
    assert done.status_code == 200, done.text
    account = done.json()["account"]

    assert account["follower_count"] is None
    assert account["follower_source"] is None
    assert account["follower_verified_at"] is None
    # The account exists and its credentials are stored: nothing about the
    # ambiguity cost the creator the connection.
    assert account["platform"] == PLATFORM
    assert _stored_token(auth_client, account["id"]) is not None
    assert len(auth_client.get(f"/profiles/{uid}/social-accounts").json()) == 1


def test_a_failed_pages_lookup_leaves_the_connection_standing(auth_client, monkeypatch):
    """Best effort, always. The audience read runs after the tokens are stored
    precisely so that this is true rather than hopeful."""
    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(raise_on={"accounts"}))
    _uid, done = _connect(auth_client, monkeypatch, "+22990003006")
    assert done.status_code == 200, done.text
    account = done.json()["account"]
    assert account["follower_count"] is None
    assert account["follower_source"] is None
    assert decrypt_bytes(
        _stored_token(auth_client, account["id"])["access_ciphertext"]
    ).decode() == LONG_LIVED


def test_a_meta_refusal_reaches_the_creator_as_one_readable_sentence(
    auth_client, monkeypatch
):
    """Meta's own error text names client ids and is written for a developer.
    It goes to the log; the creator gets oauth_exchange_failed and the promise
    that nothing was saved."""
    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(fail={"short"}))
    uid, done = _connect(auth_client, monkeypatch, "+22990003007")
    assert done.status_code == 502
    assert done.json()["code"] == "oauth_exchange_failed"
    assert "OAuthException" not in done.text
    assert auth_client.get(f"/profiles/{uid}/social-accounts").json() == []


# --------------------------------------------------------------------------
# The picker: the creator answering the question read_audience refuses to
#
# WHAT THESE ARE FOR. read_audience declining to guess is correct and is pinned
# above. The cost of that refusal was a creator staring at an app-scoped id and
# no follower count, and these two endpoints are how they fix it themselves.
#
# THE ONE THAT MATTERS is
# test_a_page_the_creator_does_not_manage_is_refused_and_changes_nothing. Every
# other test here describes a convenience; that one describes the difference
# between a follower number a platform stated and a follower number somebody
# typed into a URL.
# --------------------------------------------------------------------------


def _pages(client, user_id, platform=PLATFORM):
    return client.get(f"/profiles/oauth/{platform}/pages", headers=_headers(user_id))


def _choose(client, user_id, page_id, platform=PLATFORM):
    return client.post(
        f"/profiles/oauth/{platform}/pages/{page_id}", headers=_headers(user_id)
    )


def _only_account(client, user_id):
    accounts = client.get(f"/profiles/{user_id}/social-accounts").json()
    assert len(accounts) == 1, accounts
    return accounts[0]


def test_the_picker_needs_a_token(auth_client):
    """Both halves. The list is every Page somebody manages, including the
    client account they merely administer, and the select writes to their
    profile. Neither is anybody else's business."""
    assert auth_client.get(f"/profiles/oauth/{PLATFORM}/pages").status_code == 401
    assert (
        auth_client.post(f"/profiles/oauth/{PLATFORM}/pages/page-gossip").status_code
        == 401
    )


def test_the_picker_lists_every_page_the_creator_manages(auth_client, monkeypatch):
    """THE LIVE CASE, FROM THE CREATOR'S SIDE.

    Four Pages, so the connection recorded no number. The list is what turns
    that dead end into a question somebody can answer: all four, largest first,
    with the name and the count for each.
    """
    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(pages=FOUR_PAGES))
    uid, done = _connect(auth_client, monkeypatch, "+22990003010")
    assert done.status_code == 200, done.text
    assert done.json()["account"]["follower_count"] is None

    listed = _pages(auth_client, uid)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    # LARGEST FIRST, which is not the order Meta handed them over in. Ordering
    # is not choosing: nothing is recorded until the creator taps one.
    assert [page["id"] for page in body] == [
        "page-gossip",
        "page-buzz",
        "page-beauty",
        "page-tech",
    ]
    assert body[0] == {
        "id": "page-gossip",
        "name": "Cotonou Gossip",
        "follower_count": 184000,
    }


def test_a_page_of_unknown_size_sorts_last_rather_than_leading(auth_client, monkeypatch):
    """"We do not know" is a worse thing to lead a list with than any number."""
    monkeypatch.setattr(
        oauth.httpx,
        "get",
        FakeGraph(
            pages=[
                {"id": "page-unknown", "name": "Sans Chiffre"},
                {"id": "page-small", "name": "Petite Page", "followers_count": 12},
            ]
        ),
    )
    uid, _done = _connect(auth_client, monkeypatch, "+22990003011")
    body = _pages(auth_client, uid).json()
    assert [page["id"] for page in body] == ["page-small", "page-unknown"]
    assert body[-1]["follower_count"] is None


def test_choosing_a_page_records_it_as_the_platforms_own_word(auth_client, monkeypatch):
    """All three provenance columns, exactly as a one-Page connection writes
    them, and on the row that already existed rather than on a new one."""
    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(pages=FOUR_PAGES))
    uid, done = _connect(auth_client, monkeypatch, "+22990003012")
    account_id = done.json()["account"]["id"]
    # What the creator was actually looking at before this feature existed.
    assert done.json()["account"]["handle"] == ME_ID

    chosen = _choose(auth_client, uid, "page-beauty")
    assert chosen.status_code == 200, chosen.text
    body = chosen.json()

    assert body["id"] == account_id
    assert body["handle"] == "Beaute by Adjo"
    assert body["follower_count"] == 9100
    assert body["follower_source"] == "platform_api"
    assert body["follower_verified_at"] is not None
    # AND NOT THE BIGGEST ONE, which is the whole argument for asking. The
    # gossip page has twenty times the audience and is not what she sells.
    assert body["follower_count"] != 184000

    stored = _only_account(auth_client, uid)
    assert stored["handle"] == "Beaute by Adjo"
    assert stored["follower_count"] == 9100
    # CONNECTED, and choosing a Page is still not a badge: verifying an
    # identity stays an admin's deliberate decision and nothing here writes it.
    assert stored["status"] == "connected"


def test_a_page_the_creator_does_not_manage_is_refused_and_changes_nothing(
    auth_client, monkeypatch
):
    """THE SECURITY TEST, AND THE ONE WORTH KEEPING ABOVE ALL THE OTHERS.

    Adjo manages four Pages. A stranger manages one, and it is enormous. If the
    page_id in the URL were believed on sight, Adjo could post the stranger's
    id and this API would stamp "Someone Else Media" and 990,000 followers onto
    her profile as platform_api: a platform-verified-looking claim to an
    audience she has never had, on the one number a brand reads before it
    spends. The provenance columns exist precisely to make that impossible.

    So the list is fetched again, with ADJO'S OWN token, and only a Page that
    comes back may be written. Delete the re-fetch in oauth_service._own_pages,
    or match the id against anything a client supplied, and this goes red.

    Nothing is a 403 here. A 404 is the honest answer, and it is also the one
    that declines to confirm to a prober that some other id was real.
    """
    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(pages=STRANGER_PAGES))
    stranger, stranger_done = _connect(auth_client, monkeypatch, "+22990003013")
    assert stranger_done.status_code == 200, stranger_done.text
    # The stranger's own connection is a perfectly ordinary one-Page one.
    assert _only_account(auth_client, stranger)["follower_count"] == 990000

    adjo_graph = FakeGraph(pages=FOUR_PAGES)
    monkeypatch.setattr(oauth.httpx, "get", adjo_graph)
    adjo, adjo_done = _connect(auth_client, monkeypatch, "+22990003014")
    assert adjo_done.status_code == 200, adjo_done.text

    before = _only_account(auth_client, adjo)
    calls_before = len(adjo_graph.calls)

    refused = _choose(auth_client, adjo, "page-stranger")
    assert refused.status_code == 404
    assert refused.json()["code"] == "oauth_page_not_found"

    # META WAS ASKED, with this creator's token, before the refusal. The answer
    # is the result of a question actually put to the platform rather than a
    # guess about the shape of an id.
    assert adjo_graph.steps()[calls_before:] == ["accounts"]
    assert adjo_graph.calls[-1][2]["access_token"] == LONG_LIVED
    assert adjo_graph.calls[-1][1].endswith(f"/{ME_ID}/accounts")

    # AND NOTHING MOVED. Not the handle, not the count, not the provenance.
    after = _only_account(auth_client, adjo)
    assert after == before
    assert after["handle"] == ME_ID
    assert after["follower_count"] is None
    assert after["follower_source"] is None
    assert after["follower_verified_at"] is None

    # The stranger's own row is untouched too: a refused pick writes nowhere.
    assert _only_account(auth_client, stranger)["handle"] == "Someone Else Media"


def test_choosing_again_replaces_the_answer_rather_than_adding_a_row(
    auth_client, monkeypatch
):
    """One row per platform is the model, and it is unchanged by this feature.
    A creator who picked the wrong Page is changing their mind, not opening a
    second storefront."""
    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(pages=FOUR_PAGES))
    uid, _done = _connect(auth_client, monkeypatch, "+22990003015")

    first = _choose(auth_client, uid, "page-buzz").json()
    assert first["handle"] == "Adjo Buzz"
    assert first["follower_count"] == 42000

    second = _choose(auth_client, uid, "page-beauty").json()
    assert second["id"] == first["id"]
    assert second["handle"] == "Beaute by Adjo"
    assert second["follower_count"] == 9100
    _only_account(auth_client, uid)


def test_choosing_a_page_records_exactly_what_a_one_page_connection_would_have(
    auth_client, monkeypatch
):
    """THE TWO PATHS CANNOT DISAGREE, written as a test.

    One creator whose single Page was read for them at connection, one who
    chose the same Page out of four. Same handle, same count, same provenance,
    because oauth_service._write_audience is literally the same function on
    both paths.
    """
    monkeypatch.setattr(
        oauth.httpx, "get", FakeGraph(pages=[PAGE_BY_ID["page-beauty"]])
    )
    _auto_uid, auto_done = _connect(auth_client, monkeypatch, "+22990003016")
    automatic = auto_done.json()["account"]

    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(pages=FOUR_PAGES))
    picked_uid, _picked_done = _connect(auth_client, monkeypatch, "+22990003017")
    picked = _choose(auth_client, picked_uid, "page-beauty").json()

    for field in ("handle", "follower_count", "follower_source"):
        assert automatic[field] == picked[field], field
    assert automatic["follower_verified_at"] is not None
    assert picked["follower_verified_at"] is not None


def test_listing_without_a_connected_account_is_refused_cleanly(
    auth_client, monkeypatch, graph
):
    """Nothing is connected, so there is no token to read a Page list with.
    oauth_token_expired is this module's one sentence for "no usable
    credentials", which load_access_token already answers for a missing token
    row, and it names the only thing that helps."""
    monkeypatch.setattr(oauth_service, "providers", {PLATFORM: _provider()})
    uid = _user(auth_client, "+22990003018")

    refused = _pages(auth_client, uid)
    assert refused.status_code == 409
    assert refused.json()["code"] == "oauth_token_expired"
    assert graph.calls == [], "nothing was asked of Meta"


def test_selecting_without_a_connected_account_is_refused_cleanly(
    auth_client, monkeypatch, graph
):
    """Same refusal, and no account is conjured to hang the answer on."""
    monkeypatch.setattr(oauth_service, "providers", {PLATFORM: _provider()})
    uid = _user(auth_client, "+22990003019")

    refused = _choose(auth_client, uid, "page-gossip")
    assert refused.status_code == 409
    assert refused.json()["code"] == "oauth_token_expired"
    assert graph.calls == []
    assert auth_client.get(f"/profiles/{uid}/social-accounts").json() == []


def test_a_platform_with_no_provider_cannot_be_asked_for_pages(auth_client):
    """Deliberately NOT monkeypatched: this is the honest answer on a platform
    this deployment holds no credentials for, and it is the same sentence
    `start` gives."""
    uid = _user(auth_client, "+22990003020")
    refused = _pages(auth_client, uid, platform="tiktok")
    assert refused.status_code == 400
    assert refused.json()["code"] == "oauth_platform_unsupported"


def test_a_lapsed_connection_cannot_be_used_to_list_pages(auth_client, monkeypatch):
    """The picker goes through load_access_token, so it gets the right refusal
    for a dead Meta token without knowing anything about Meta."""
    graph = FakeGraph(pages=FOUR_PAGES)
    monkeypatch.setattr(oauth.httpx, "get", graph)
    uid, done = _connect(auth_client, monkeypatch, "+22990003021")
    account_id = done.json()["account"]["id"]

    db = auth_client.session_factory()
    try:
        row = (
            db.query(models.SocialToken)
            .filter(models.SocialToken.social_account_id == account_id)
            .first()
        )
        row.access_expires_at = models.utcnow() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    calls_before = len(graph.calls)
    refused = _pages(auth_client, uid)
    assert refused.status_code == 409
    assert refused.json()["code"] == "oauth_token_expired"
    assert len(graph.calls) == calls_before, "a dead token is not spent on a request"


def test_a_page_list_that_cannot_be_read_refuses_rather_than_answering_empty(
    auth_client, monkeypatch
):
    """"We could not ask" is not "you manage no Pages".

    Answering an unreachable Graph with [] would tell a creator with four Pages
    that they have none, which is the one wrong answer available here.
    """
    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(pages=FOUR_PAGES))
    uid, _done = _connect(auth_client, monkeypatch, "+22990003022")

    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(raise_on={"accounts"}))
    refused = _pages(auth_client, uid)
    assert refused.status_code == 502
    assert refused.json()["code"] == "oauth_exchange_failed"

    # And the same for a pick, which must not fall through to a write.
    before = _only_account(auth_client, uid)
    assert _choose(auth_client, uid, "page-beauty").status_code == 502
    assert _only_account(auth_client, uid) == before


def test_a_creator_with_no_pages_gets_an_empty_list_rather_than_a_refusal(
    auth_client, monkeypatch
):
    """Zero Pages is an ordinary answer: somebody who has not made one, or who
    declined pages_show_list on the consent screen. It is not an error, and the
    client shows an empty picker and says so in its own words."""
    monkeypatch.setattr(oauth.httpx, "get", FakeGraph(pages=[]))
    uid, done = _connect(auth_client, monkeypatch, "+22990003023")
    assert done.status_code == 200, done.text

    listed = _pages(auth_client, uid)
    assert listed.status_code == 200, listed.text
    assert listed.json() == []

    # And nothing can be chosen out of nothing.
    refused = _choose(auth_client, uid, "page-gossip")
    assert refused.status_code == 404
    assert refused.json()["code"] == "oauth_page_not_found"

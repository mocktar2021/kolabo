"""The browser check, and the four states it has.

WHAT IS ACTUALLY WORTH TESTING HERE is not that a good token passes. It is
the three ways this can be wrong in production:

  - A box with no secret key must behave exactly as it did before the feature
    existed. That is every developer laptop, CI, and any box deployed before
    somebody sets the key. If this one breaks, the whole suite breaks with it.
  - A missing token and a bad token are DIFFERENT questions. The mobile app
    sends no token at all, so refusing an absent one is a setting somebody
    turns on knowing it breaks the shipped app, while refusing a bad one is
    always right.
  - Cloudflare being unreachable must not lock everybody out of signing in.
    An outage there is not a reason for an outage here, and the difference
    between "no answer" and "the answer was no" is the whole of that.
"""
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import turnstile
from app.core.config import settings
from app.core.db import Base, get_db
from app.core.errors import AppError, app_error_handler
from app.modules.auth.router import router as auth_router

PASSWORD = "strongpass1"


class _Answer:
    """Stands in for an httpx response carrying a siteverify verdict."""

    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


class TestSwitches:
    def test_nothing_happens_without_a_secret(self, monkeypatch):
        """Every laptop and every CI run is this case."""
        monkeypatch.setattr(settings, "turnstile_secret_key", "")
        assert turnstile.configured() is False
        assert turnstile.required() is False

    def test_required_needs_a_secret_too(self, monkeypatch):
        """TURNSTILE_REQUIRED=true on a box with no key is a configuration
        mistake, and the safe reading of it is off rather than refuse
        everything."""
        monkeypatch.setattr(settings, "turnstile_secret_key", "")
        monkeypatch.setattr(settings, "turnstile_required", True)
        assert turnstile.required() is False

    def test_required_is_off_even_with_a_secret_until_asked_for(self, monkeypatch):
        """Setting the key protects the web. It must not silently start
        refusing the mobile app, which sends no token at all."""
        monkeypatch.setattr(settings, "turnstile_secret_key", "sekrit")
        monkeypatch.setattr(settings, "turnstile_required", False)
        assert turnstile.configured() is True
        assert turnstile.required() is False


class TestVerify:
    def setup_method(self):
        self.sent = {}

    def _capture(self, body):
        def post(url, data=None, timeout=None):
            self.sent["url"] = url
            self.sent["data"] = data
            return _Answer(body)

        return post

    def test_a_successful_verdict_passes(self, monkeypatch):
        monkeypatch.setattr(settings, "turnstile_secret_key", "sekrit")
        monkeypatch.setattr(httpx, "post", self._capture({"success": True}))
        assert turnstile.verify("a-token", "203.0.113.7") is True
        assert self.sent["url"] == turnstile.VERIFY_URL
        assert self.sent["data"]["secret"] == "sekrit"
        assert self.sent["data"]["response"] == "a-token"
        assert self.sent["data"]["remoteip"] == "203.0.113.7"

    def test_the_address_is_omitted_when_unknown_rather_than_sent_empty(self, monkeypatch):
        monkeypatch.setattr(settings, "turnstile_secret_key", "sekrit")
        monkeypatch.setattr(httpx, "post", self._capture({"success": True}))
        turnstile.verify("a-token", None)
        assert "remoteip" not in self.sent["data"]

    def test_an_explicit_refusal_is_refused(self, monkeypatch):
        """An answer of no is an answer. This is the one case that must never
        fail open."""
        monkeypatch.setattr(settings, "turnstile_secret_key", "sekrit")
        monkeypatch.setattr(
            httpx, "post", self._capture({"success": False, "error-codes": ["invalid-input-response"]})
        )
        assert turnstile.verify("a-token") is False

    def test_a_replayed_token_is_refused(self, monkeypatch):
        """Tokens are single use and expire after 300 seconds; Cloudflare says
        timeout-or-duplicate. Usually a double submit rather than an attack,
        but it is still not a solved challenge."""
        monkeypatch.setattr(settings, "turnstile_secret_key", "sekrit")
        monkeypatch.setattr(
            httpx, "post", self._capture({"success": False, "error-codes": ["timeout-or-duplicate"]})
        )
        assert turnstile.verify("a-token") is False

    def test_an_unreachable_cloudflare_fails_open(self, monkeypatch):
        """A Cloudflare incident must not become "nobody can sign in to
        Kolabo". The trade is argued in the module docstring; what is tested
        here is that it is the behaviour and not an accident."""
        monkeypatch.setattr(settings, "turnstile_secret_key", "sekrit")

        def explode(url, data=None, timeout=None):
            raise httpx.ConnectTimeout("siteverify is not answering")

        monkeypatch.setattr(httpx, "post", explode)
        assert turnstile.verify("a-token") is True

    def test_a_response_that_is_not_json_fails_open(self, monkeypatch):
        """A captive portal or a proxy error page is an absence of an answer,
        not a verdict."""
        monkeypatch.setattr(settings, "turnstile_secret_key", "sekrit")

        class _NotJson(_Answer):
            def json(self):
                raise ValueError("not json")

        monkeypatch.setattr(httpx, "post", lambda url, data=None, timeout=None: _NotJson(None))
        assert turnstile.verify("a-token") is True


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
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(auth_router, prefix="/auth")
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _register(client, headers=None, email="ama@example.com"):
    return client.post(
        "/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "country_code": "BJ",
            "role": "influencer",
        },
        headers=headers or {},
    )


class TestTheEndpointsBehindIt:
    def test_an_unconfigured_box_asks_for_nothing(self, client, monkeypatch):
        monkeypatch.setattr(settings, "turnstile_secret_key", "")
        assert _register(client).status_code == 201

    def test_a_missing_token_passes_while_required_is_off(self, client, monkeypatch):
        """This is the mobile app, and the whole reason the two switches are
        separate. Breaking it would break every shipped build."""
        monkeypatch.setattr(settings, "turnstile_secret_key", "sekrit")
        monkeypatch.setattr(settings, "turnstile_required", False)
        assert _register(client).status_code == 201

    def test_a_missing_token_is_refused_once_required_is_on(self, client, monkeypatch):
        monkeypatch.setattr(settings, "turnstile_secret_key", "sekrit")
        monkeypatch.setattr(settings, "turnstile_required", True)
        res = _register(client)
        assert res.status_code == 403
        assert res.json()["code"] == "auth_challenge_failed"

    def test_a_bad_token_is_refused_even_while_required_is_off(self, client, monkeypatch):
        """A token that ARRIVED and did not verify is a different thing from
        no token: somebody tried, and failed, and there is nothing to be
        permissive about."""
        monkeypatch.setattr(settings, "turnstile_secret_key", "sekrit")
        monkeypatch.setattr(settings, "turnstile_required", False)
        monkeypatch.setattr(turnstile, "verify", lambda token, ip=None: False)
        res = _register(client, headers={turnstile.HEADER: "a-bad-token"})
        assert res.status_code == 403
        assert res.json()["code"] == "auth_challenge_failed"

    def test_a_good_token_gets_through(self, client, monkeypatch):
        monkeypatch.setattr(settings, "turnstile_secret_key", "sekrit")
        monkeypatch.setattr(turnstile, "verify", lambda token, ip=None: True)
        res = _register(client, headers={turnstile.HEADER: "a-good-token"})
        assert res.status_code == 201

    def test_login_is_behind_it_too(self, client, monkeypatch):
        monkeypatch.setattr(settings, "turnstile_secret_key", "sekrit")
        monkeypatch.setattr(settings, "turnstile_required", True)
        res = client.post("/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
        assert res.status_code == 403

    def test_password_reset_is_behind_it_too(self, client, monkeypatch):
        monkeypatch.setattr(settings, "turnstile_secret_key", "sekrit")
        monkeypatch.setattr(settings, "turnstile_required", True)
        res = client.post("/auth/password-reset/request", json={"email": "nobody@example.com"})
        assert res.status_code == 403

    def test_verify_otp_is_deliberately_not_behind_it(self, client, monkeypatch):
        """Reached with a code we only email to somebody who already passed
        the challenge. A second widget there would sit between a person and
        the account they are three keystrokes from finishing."""
        monkeypatch.setattr(settings, "turnstile_secret_key", "sekrit")
        monkeypatch.setattr(settings, "turnstile_required", True)
        res = client.post("/auth/verify-otp", json={"email": "nobody@example.com", "code": "000000"})
        assert res.status_code != 403

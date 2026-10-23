"""The per IP ceilings, and the one thing that makes them worth having.

THE SPOOFING TEST IS THE IMPORTANT ONE. Every limit here is keyed on an
address taken out of X-Forwarded-For, and Caddy augments that header rather
than replacing it, so a caller who sends one of their own ends up at the LEFT
of the list with their real address appended on the right. Read the left hand
end and anybody can choose their own bucket, which is the same as having no
rate limiting while appearing to have some. That failure is silent, it looks
exactly like working code, and it is the reason this file leads with it.
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import ratelimit
from app.core.db import Base, get_db
from app.core.errors import AppError, app_error_handler
from app.modules.auth.router import router as auth_router

PASSWORD = "strongpass1"


def _request(headers: dict[str, str] | None = None, peer: str | None = "10.0.0.9") -> Request:
    """A bare ASGI scope, which is all client_ip reads."""
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": (peer, 1234) if peer else None,
    }
    return Request(scope)


class TestClientIp:
    def test_takes_the_rightmost_forwarded_entry(self):
        """The address the proxy observed, not the one the caller claimed."""
        req = _request({"X-Forwarded-For": "1.2.3.4, 203.0.113.7"})
        assert ratelimit.client_ip(req) == "203.0.113.7"

    def test_a_forged_header_cannot_choose_its_own_bucket(self):
        """Two callers behind the same proxy share a bucket however they lie.

        This is the whole point. If a spoofed left hand entry were read, each
        request could present a different address and no ceiling would ever
        be reached.
        """
        a = _request({"X-Forwarded-For": "9.9.9.9, 203.0.113.7"})
        b = _request({"X-Forwarded-For": "8.8.8.8, 203.0.113.7"})
        assert ratelimit.client_ip(a) == ratelimit.client_ip(b)

    def test_falls_back_to_the_peer_when_there_is_no_proxy(self):
        """Local development and the test suite have no Caddy in front."""
        assert ratelimit.client_ip(_request()) == "10.0.0.9"

    def test_buckets_the_unknowable_together(self):
        """Sharing one allowance is the safe failure; an unlimited one is not."""
        assert ratelimit.client_ip(_request(peer=None)) == "unknown"

    def test_ignores_a_header_that_is_only_whitespace(self):
        assert ratelimit.client_ip(_request({"X-Forwarded-For": "  "})) == "10.0.0.9"


class TestAllow:
    def setup_method(self):
        ratelimit.reset()

    def test_permits_exactly_the_allowance_then_refuses(self):
        for _ in range(3):
            assert ratelimit.allow("b", "ip", 3, 60) is True
        assert ratelimit.allow("b", "ip", 3, 60) is False

    def test_a_refused_request_is_not_recorded(self):
        """Otherwise hammering extends your own lockout indefinitely, which
        turns a speed limit into a ban nobody decided to impose."""
        for _ in range(2):
            ratelimit.allow("b", "ip", 2, 10, now=0.0)
        # Refused, repeatedly, while the window is full.
        for t in (1.0, 2.0, 3.0):
            assert ratelimit.allow("b", "ip", 2, 10, now=t) is False
        # The window drains from the ORIGINAL hits, not from the refusals.
        assert ratelimit.allow("b", "ip", 2, 10, now=10.5) is True

    def test_the_window_slides(self):
        assert ratelimit.allow("b", "ip", 1, 10, now=0.0) is True
        assert ratelimit.allow("b", "ip", 1, 10, now=9.9) is False
        assert ratelimit.allow("b", "ip", 1, 10, now=10.1) is True

    def test_addresses_do_not_share_an_allowance(self):
        assert ratelimit.allow("b", "one", 1, 60) is True
        assert ratelimit.allow("b", "one", 1, 60) is False
        assert ratelimit.allow("b", "two", 1, 60) is True

    def test_endpoints_do_not_share_an_allowance(self):
        """A spent login allowance must not stop somebody registering."""
        assert ratelimit.allow("login", "ip", 1, 60) is True
        assert ratelimit.allow("login", "ip", 1, 60) is False
        assert ratelimit.allow("register", "ip", 1, 60) is True

    def test_the_table_does_not_grow_without_bound(self):
        """An attacker rotating addresses costs memory, so there is a ceiling.

        Deliberately not a performance test: what it checks is that the cap
        holds and that serving continues, because evicting is the right answer
        and refusing everybody is not.
        """
        for n in range(ratelimit.MAX_KEYS + 50):
            ratelimit.allow("b", f"10.0.{n // 256}.{n % 256}", 5, 3600)
        assert len(ratelimit._HITS) <= ratelimit.MAX_KEYS
        assert ratelimit.allow("b", "a-new-caller", 5, 3600) is True


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
    # The real handler, because these assertions are about the `code` in the
    # body and not merely the status. Same reason as tests/test_auth.py.
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(auth_router, prefix="/auth")
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _login(client, ip, email="nobody@example.com"):
    return client.post(
        "/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"X-Forwarded-For": f"1.1.1.1, {ip}"},
    )


class TestLoginIsThrottled:
    """KOL-65. Before this, a password was guessable as fast as the server
    could answer: no attempt counter, no lockout, no delay anywhere."""

    def test_refuses_once_the_allowance_is_spent(self, client):
        allowance, _ = ratelimit.LOGIN
        for _ in range(allowance):
            # Wrong credentials, so these are 4xx either way. What is under
            # test is that they are NOT yet the 429.
            assert _login(client, "203.0.113.7").status_code != 429

        refused = _login(client, "203.0.113.7")
        assert refused.status_code == 429
        assert refused.json()["code"] == "auth_rate_limited"

    def test_one_address_running_out_does_not_lock_out_another(self, client):
        """The failure the global OTP ceiling has and this does not: one
        caller must never be able to deny the service to everybody else."""
        allowance, _ = ratelimit.LOGIN
        for _ in range(allowance + 1):
            _login(client, "203.0.113.7")
        assert _login(client, "198.51.100.4").status_code != 429

    def test_a_forged_header_does_not_buy_a_fresh_allowance(self, client):
        """Each request claims a different origin; all of them are behind the
        same real address and all of them share its allowance."""
        allowance, _ = ratelimit.LOGIN
        for n in range(allowance):
            client.post(
                "/auth/login",
                json={"email": "nobody@example.com", "password": PASSWORD},
                headers={"X-Forwarded-For": f"10.0.0.{n}, 203.0.113.7"},
            )
        refused = client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": PASSWORD},
            headers={"X-Forwarded-For": "10.0.0.250, 203.0.113.7"},
        )
        assert refused.status_code == 429


class TestRegisterIsThrottled:
    def test_refuses_once_the_allowance_is_spent(self, client):
        allowance, _ = ratelimit.REGISTER
        for n in range(allowance):
            res = client.post(
                "/auth/register",
                json={
                    "email": f"creator{n}@example.com",
                    "password": PASSWORD,
                    "country_code": "BJ",
                    "role": "influencer",
                },
                headers={"X-Forwarded-For": "203.0.113.7"},
            )
            assert res.status_code != 429

        refused = client.post(
            "/auth/register",
            json={
                "email": "one-too-many@example.com",
                "password": PASSWORD,
                "country_code": "BJ",
                "role": "influencer",
            },
            headers={"X-Forwarded-For": "203.0.113.7"},
        )
        assert refused.status_code == 429
        # Borrowed rather than minted: the sentence this code already carries
        # says the right thing, and a caller does not need to know whether it
        # was their address or their connection that ran out.
        assert refused.json()["code"] == "auth_otp_too_many"

    def test_the_flood_that_used_to_lock_everybody_out_now_stops_at_its_own_address(self, client):
        """The global ceiling in auth.service is a shared fuse by design, and
        its own comment says so. This is what keeps a script from reaching it:
        one address runs out long before the platform's allowance does, and a
        second address is unaffected."""
        allowance, _ = ratelimit.REGISTER
        for n in range(allowance + 5):
            client.post(
                "/auth/register",
                json={
                    "email": f"flood{n}@example.com",
                    "password": PASSWORD,
                    "country_code": "BJ",
                    "role": "influencer",
                },
                headers={"X-Forwarded-For": "203.0.113.7"},
            )
        res = client.post(
            "/auth/register",
            json={
                "email": "honest@example.com",
                "password": PASSWORD,
                "country_code": "BJ",
                "role": "influencer",
            },
            headers={"X-Forwarded-For": "198.51.100.4"},
        )
        assert res.status_code != 429

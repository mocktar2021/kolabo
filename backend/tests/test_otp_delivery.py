"""What happens when the code does not leave the server (KOL-74).

BEFORE THIS, NOTHING. Sender.send returned None, both call sites committed the
challenge row and then sent, and the outcome was thrown away. A provider that
failed left the client reading "code sent" for a code that never left, and a
provider that raised turned a registration whose row was already committed
into a 500. Neither had a test because neither had a behaviour.

Registration is tested through the router, the way test_auth.py tests the
caps, because what matters is what the CLIENT is told: the status, the code
in the body, and that the phantom challenge does not eat the caller's
allowance. The chain and the router are tested on their own, because they
are the shape a real provider will be dropped into and the shape is what has
to hold.
"""
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.errors import AppError, app_error_handler
from app.modules.auth import account, models, otp, service
from app.modules.auth.router import router as auth_router

PHONE = "+22990000301"
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
    # The real handler, because these tests assert on the `code` in the body.
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(auth_router, prefix="/auth")
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    test_client.session_factory = testing_session
    return test_client


class _Accepting:
    """A provider that takes everything."""

    def __init__(self, name="good"):
        self.name = name
        self.sent = []

    def send(self, phone, message):
        self.sent.append((phone, message))
        return otp.SendResult(ok=True, provider=self.name)


class _Refusing:
    """A provider that answers, and the answer is no."""

    def __init__(self, name="bad", error="insufficient balance"):
        self.name = name
        self.error = error
        self.sent = []

    def send(self, phone, message):
        self.sent.append((phone, message))
        return otp.SendResult(ok=False, provider=self.name, error=self.error)


class _Raising:
    """A provider whose adapter blows up: a timeout, a 500, a bug."""

    name = "raising"

    def send(self, phone, message):
        raise ConnectionError("gateway timed out")


class _Silent:
    """The old protocol: sends, says nothing. Must read as a failure now."""

    name = "silent"

    def send(self, phone, message):
        return None


def _register(client, phone=PHONE, country="BJ", role="influencer", password=PASSWORD):
    return client.post(
        "/auth/register",
        json={"phone": phone, "password": password, "country_code": country, "role": role},
    )


def _challenges(client, phone=PHONE):
    db = client.session_factory()
    try:
        user = db.query(models.User).filter(models.User.phone == phone).first()
        if user is None:
            return []
        return (
            db.query(models.OtpChallenge)
            .filter(models.OtpChallenge.user_id == user.id)
            .order_by(models.OtpChallenge.created_at.asc())
            .all()
        )
    finally:
        db.close()


class TestRegistration:
    def test_a_refused_send_refuses_the_request_and_names_why(self, client, monkeypatch):
        """The whole point: nobody is told a code is on its way when it is not."""
        monkeypatch.setattr(service, "_sender", _Refusing())
        r = _register(client)
        assert r.status_code == 503
        assert r.json()["code"] == "auth_otp_delivery_failed"

    def test_a_raising_provider_is_a_503_and_not_a_500(self, client, monkeypatch):
        """The row is committed before the send. An exception after that used to
        be a 500 on a request that had already half happened."""
        monkeypatch.setattr(service, "_sender", _Raising())
        r = _register(client)
        assert r.status_code == 503
        assert r.json()["code"] == "auth_otp_delivery_failed"

    def test_the_account_survives_and_the_code_does_not(self, client, monkeypatch):
        """The user row stays, so registering again is the resend. The challenge
        that never flew is consumed, so it cannot be verified against and does
        not count as a code in flight."""
        monkeypatch.setattr(service, "_sender", _Refusing())
        _register(client)
        rows = _challenges(client)
        assert len(rows) == 1
        assert rows[0].consumed is True
        # And it is not the "newest unconsumed challenge" a guess resolves
        # against: the honest answer is that there is no live code at all.
        r = client.post("/auth/verify-otp", json={"phone": PHONE, "code": rows[0].code})
        assert r.status_code == 400
        assert r.json()["code"] == "auth_code_expired"

    def test_a_phantom_code_does_not_spend_the_callers_allowance(self, client, monkeypatch):
        """Three failed sends and then a working provider: the fourth request
        must go through. The per-phone cap counts codes in flight, and a code
        that never left is not in flight. Without the consume in _issue_otp,
        an outage would lock every affected number out for an hour after the
        provider came back."""
        monkeypatch.setattr(service, "_sender", _Refusing())
        for _ in range(3):
            assert _register(client).status_code == 503
        good = _Accepting()
        monkeypatch.setattr(service, "_sender", good)
        assert _register(client).status_code == 201
        assert len(good.sent) == 1
        rows = _challenges(client)
        assert len(rows) == 4
        assert sum(1 for row in rows if row.consumed) == 3
        assert sum(1 for row in rows if not row.consumed) == 1

    def test_a_working_provider_is_unchanged(self, client, monkeypatch):
        good = _Accepting()
        monkeypatch.setattr(service, "_sender", good)
        r = _register(client)
        assert r.status_code == 201
        assert r.json()["message"] == "Verification code sent"
        assert len(good.sent) == 1
        assert good.sent[0][0] == PHONE

    def test_the_failure_is_logged_with_the_providers_words(self, client, monkeypatch, caplog):
        """Support will read this line. It has to say which provider and what
        it said, not only that something went wrong."""
        monkeypatch.setattr(service, "_sender", _Refusing(name="termii", error="account suspended"))
        with caplog.at_level(logging.ERROR, logger="kolabo.auth.service"):
            _register(client)
        assert any(
            "termii" in rec.getMessage() and "account suspended" in rec.getMessage()
            for rec in caplog.records
        )


class TestPasswordReset:
    """The one call site that keeps its answer, and why is in account.py."""

    def _registered(self, client, monkeypatch):
        monkeypatch.setattr(service, "_sender", _Accepting())
        _register(client)

    def test_a_failed_send_still_answers_the_generic_202(self, client, monkeypatch):
        """A 503 only for numbers that have an account would make a provider
        outage into an enumeration oracle. The endpoint's privacy contract
        outranks the honesty of one sentence, and the sentence was already
        conditional."""
        self._registered(client, monkeypatch)
        monkeypatch.setattr(account, "_sender", _Refusing())
        r = client.post("/auth/password-reset/request", json={"phone": PHONE})
        assert r.status_code == 202
        assert r.json() == account.GENERIC_RESET_RESPONSE

    def test_the_undelivered_token_is_consumed(self, client, monkeypatch):
        """So the person can ask again the moment delivery is back, instead of
        finding three phantom codes have eaten their hourly allowance."""
        self._registered(client, monkeypatch)
        monkeypatch.setattr(account, "_sender", _Refusing())
        for _ in range(3):
            assert client.post("/auth/password-reset/request", json={"phone": PHONE}).status_code == 202
        db = client.session_factory()
        try:
            tokens = db.query(models.PasswordResetToken).all()
            assert len(tokens) == 3
            assert all(t.consumed for t in tokens)
        finally:
            db.close()
        # Not rate limited: none of those counted.
        monkeypatch.setattr(account, "_sender", _Accepting())
        assert client.post("/auth/password-reset/request", json={"phone": PHONE}).status_code == 202
        db = client.session_factory()
        try:
            live = [t for t in db.query(models.PasswordResetToken).all() if not t.consumed]
            assert len(live) == 1
        finally:
            db.close()

    def test_a_raising_provider_does_not_500_the_reset(self, client, monkeypatch):
        self._registered(client, monkeypatch)
        monkeypatch.setattr(account, "_sender", _Raising())
        r = client.post("/auth/password-reset/request", json={"phone": PHONE})
        assert r.status_code == 202

    def test_the_failure_is_logged_loudly(self, client, monkeypatch, caplog):
        """A silent 202 over a dead provider is how an outage goes unnoticed."""
        self._registered(client, monkeypatch)
        monkeypatch.setattr(account, "_sender", _Refusing(name="termii", error="account suspended"))
        with caplog.at_level(logging.ERROR, logger="kolabo.auth.account"):
            client.post("/auth/password-reset/request", json={"phone": PHONE})
        assert any(
            "termii" in rec.getMessage() and "account suspended" in rec.getMessage()
            for rec in caplog.records
        )


class TestDeliver:
    """The wrapper every call site goes through."""

    def test_a_result_passes_through(self):
        assert otp.deliver(_Accepting("x"), PHONE, "m") == otp.SendResult(ok=True, provider="x")

    def test_an_exception_becomes_a_failed_result(self):
        result = otp.deliver(_Raising(), PHONE, "m")
        assert result.ok is False
        assert result.provider == "raising"
        assert "ConnectionError" in result.error
        assert "gateway timed out" in result.error

    def test_a_sender_that_returns_nothing_is_a_failure(self):
        """The old protocol, and the silent failure this change exists to end:
        an adapter that forgot to return must not look like one that worked."""
        result = otp.deliver(_Silent(), PHONE, "m")
        assert result.ok is False
        assert result.provider == "silent"

    def test_the_logging_sender_reports_success(self):
        result = otp.deliver(otp.LoggingSender(), PHONE, "m")
        assert result == otp.SendResult(ok=True, provider="logging")


class TestCompositeSender:
    def test_the_first_that_accepts_wins_and_is_named(self):
        first, second = _Accepting("first"), _Accepting("second")
        result = otp.CompositeSender([first, second]).send(PHONE, "m")
        assert result.ok is True
        assert result.provider == "first"
        assert len(first.sent) == 1
        # Never reached: a fallback that also sends is a double SMS bill.
        assert second.sent == []

    def test_first_fails_second_succeeds(self):
        first, second = _Refusing("first"), _Accepting("second")
        result = otp.CompositeSender([first, second]).send(PHONE, "m")
        assert result.ok is True
        assert result.provider == "second"
        assert len(first.sent) == 1 and len(second.sent) == 1

    def test_a_raising_child_does_not_take_the_chain_down(self):
        result = otp.CompositeSender([_Raising(), _Accepting("second")]).send(PHONE, "m")
        assert result.ok is True
        assert result.provider == "second"

    def test_all_fail_and_every_error_is_reported(self):
        chain = otp.CompositeSender([_Refusing("a", "no credit"), _Refusing("b", "bad number")])
        result = chain.send(PHONE, "m")
        assert result.ok is False
        assert result.provider == "composite"
        assert "a: no credit" in result.error
        assert "b: bad number" in result.error

    def test_an_empty_chain_is_a_refusal_not_a_crash(self):
        result = otp.CompositeSender([]).send(PHONE, "m")
        assert result.ok is False
        assert "no senders" in result.error

    def test_a_fallback_success_is_warned_about(self, caplog):
        """A primary that is failing is a bill and a latency somebody should
        hear about before the secondary fails too."""
        with caplog.at_level(logging.WARNING, logger="kolabo.auth.otp"):
            otp.CompositeSender([_Refusing("first"), _Accepting("second")]).send(PHONE, "m")
        assert any("first" in rec.getMessage() and "second" in rec.getMessage() for rec in caplog.records)


class TestRoutingSender:
    def test_routes_by_dialling_prefix(self):
        benin, ghana, rest = _Accepting("benin"), _Accepting("ghana"), _Accepting("rest")
        router = otp.RoutingSender({"+229": benin, "+233": ghana}, default=rest)
        assert router.send("+22997000000", "m").provider == "benin"
        assert router.send("+233240000000", "m").provider == "ghana"
        # Nigeria has no route of its own and lands on the default.
        assert router.send("+2348000000000", "m").provider == "rest"

    def test_the_longest_prefix_wins(self):
        """An operator range can sit beside the route for its country."""
        country, operator = _Accepting("country"), _Accepting("operator")
        router = otp.RoutingSender({"+229": country, "+22997": operator})
        assert router.send("+22997000000", "m").provider == "operator"
        assert router.send("+22961000000", "m").provider == "country"

    def test_no_route_and_no_default_is_a_refusal_that_names_the_prefix(self):
        result = otp.RoutingSender({"+229": _Accepting()}).send("+2348000000000", "m")
        assert result.ok is False
        assert result.provider == "routing"
        assert "+234" in result.error

    def test_a_chain_can_be_a_route(self):
        """The shape a second provider drops into: a route per market, and a
        chain as the default so every number has a fallback."""
        primary, backup = _Refusing("primary"), _Accepting("backup")
        router = otp.RoutingSender({}, default=otp.CompositeSender([primary, backup]))
        result = router.send(PHONE, "m")
        assert result.ok is True
        assert result.provider == "backup"


def test_the_default_sender_is_the_logging_one_until_a_provider_exists():
    assert isinstance(otp.build_default_sender(), otp.LoggingSender)
    assert otp.default_sender.name == "logging"

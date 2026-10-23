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

THE CODE GOES TO A MAILBOX NOW. The Sender protocol is unchanged in shape and
the parameter is called `target`, so every stand-in below is the same class it
always was with one word renamed. What is new at the bottom of this file is the
adapter onto the notifications mail provider, and the bilingual message the
target actually receives.
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

EMAIL = "delivery@example.com"
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

    def send(self, target, message):
        self.sent.append((target, message))
        return otp.SendResult(ok=True, provider=self.name)


class _Refusing:
    """A provider that answers, and the answer is no."""

    def __init__(self, name="bad", error="insufficient balance"):
        self.name = name
        self.error = error
        self.sent = []

    def send(self, target, message):
        self.sent.append((target, message))
        return otp.SendResult(ok=False, provider=self.name, error=self.error)


class _Raising:
    """A provider whose adapter blows up: a timeout, a 500, a bug."""

    name = "raising"

    def send(self, target, message):
        raise ConnectionError("gateway timed out")


class _Silent:
    """The old protocol: sends, says nothing. Must read as a failure now."""

    name = "silent"

    def send(self, target, message):
        return None


def _register(client, email=EMAIL, country="BJ", role="influencer", password=PASSWORD):
    return client.post(
        "/auth/register",
        json={"email": email, "password": password, "country_code": country, "role": role},
    )


def _challenges(client, email=EMAIL):
    db = client.session_factory()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
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
        r = client.post("/auth/verify-otp", json={"email": EMAIL, "code": rows[0].code})
        assert r.status_code == 400
        assert r.json()["code"] == "auth_code_expired"

    def test_a_phantom_code_does_not_spend_the_callers_allowance(self, client, monkeypatch):
        """Three failed sends and then a working provider: the fourth request
        must go through. The per-account cap counts codes in flight, and a code
        that never left is not in flight. Without the consume in _issue_otp,
        an outage would lock every affected address out for an hour after the
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
        assert good.sent[0][0] == EMAIL
        # And the message is the bilingual one, with the subject on the first
        # line where notifications/email.py's _subject will find it. Benin, so
        # French: five of the seven configured countries default to it.
        subject, blank, first_body_line = good.sent[0][1].split("\n")[:3]
        assert subject == "Votre code de vérification Kolabo"
        assert blank == ""
        assert first_body_line.startswith("Votre code de vérification Kolabo est ")

    def test_the_language_follows_the_country_on_the_account(self, client, monkeypatch):
        """Asserted through the router rather than on the template function,
        because what can break is the WIRING: _issue_otp has to pass the
        account's country, and a signup that quietly sent French to Accra would
        look perfectly healthy from every other test in this file.

        THIS USED TO REGISTER IN GHANA, which was the only anglophone market a
        signup could reach. The launch list is Benin, Togo, Cote d'Ivoire and
        Senegal, and all four default to French, so no country reachable
        through registration produces an English message any more.

        Weakening it to "French came out" would have proved nothing, because
        French is also the fallback: a signup that ignored the account's
        country entirely would pass that assertion. So an open market's
        language is patched instead. The test still points at the wiring, and
        it no longer depends on which countries happen to be open. If
        _issue_otp stops passing the country, the message falls back to French
        and this goes red, which is the only thing it was ever testing.

        The template itself keeps its own coverage in TestTheMessageItself,
        which calls verification_message("GH", ...) directly.
        """
        from app.core import country_config

        monkeypatch.setitem(
            country_config.COUNTRY_CONFIG,
            "BJ",
            {**country_config.COUNTRY_CONFIG["BJ"], "language": "en"},
        )
        good = _Accepting()
        monkeypatch.setattr(service, "_sender", good)
        assert _register(client, email="anglophone@example.com", country="BJ").status_code == 201
        assert good.sent[0][1].startswith("Your Kolabo verification code\n")

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
        """A 503 only for addresses that have an account would make a provider
        outage into an enumeration oracle. The endpoint's privacy contract
        outranks the honesty of one sentence, and the sentence was already
        conditional."""
        self._registered(client, monkeypatch)
        monkeypatch.setattr(account, "_sender", _Refusing())
        r = client.post("/auth/password-reset/request", json={"email": EMAIL})
        assert r.status_code == 202
        assert r.json() == account.GENERIC_RESET_RESPONSE

    def test_the_undelivered_token_is_consumed(self, client, monkeypatch):
        """So the person can ask again the moment delivery is back, instead of
        finding three phantom codes have eaten their hourly allowance."""
        self._registered(client, monkeypatch)
        monkeypatch.setattr(account, "_sender", _Refusing())
        for _ in range(3):
            assert client.post("/auth/password-reset/request", json={"email": EMAIL}).status_code == 202
        db = client.session_factory()
        try:
            tokens = db.query(models.PasswordResetToken).all()
            assert len(tokens) == 3
            assert all(t.consumed for t in tokens)
        finally:
            db.close()
        # Not rate limited: none of those counted.
        monkeypatch.setattr(account, "_sender", _Accepting())
        assert client.post("/auth/password-reset/request", json={"email": EMAIL}).status_code == 202
        db = client.session_factory()
        try:
            live = [t for t in db.query(models.PasswordResetToken).all() if not t.consumed]
            assert len(live) == 1
        finally:
            db.close()

    def test_a_raising_provider_does_not_500_the_reset(self, client, monkeypatch):
        self._registered(client, monkeypatch)
        monkeypatch.setattr(account, "_sender", _Raising())
        r = client.post("/auth/password-reset/request", json={"email": EMAIL})
        assert r.status_code == 202

    def test_the_failure_is_logged_loudly(self, client, monkeypatch, caplog):
        """A silent 202 over a dead provider is how an outage goes unnoticed."""
        self._registered(client, monkeypatch)
        monkeypatch.setattr(account, "_sender", _Refusing(name="termii", error="account suspended"))
        with caplog.at_level(logging.ERROR, logger="kolabo.auth.account"):
            client.post("/auth/password-reset/request", json={"email": EMAIL})
        assert any(
            "termii" in rec.getMessage() and "account suspended" in rec.getMessage()
            for rec in caplog.records
        )


class TestDeliver:
    """The wrapper every call site goes through."""

    def test_a_result_passes_through(self):
        assert otp.deliver(_Accepting("x"), EMAIL, "m") == otp.SendResult(ok=True, provider="x")

    def test_an_exception_becomes_a_failed_result(self):
        result = otp.deliver(_Raising(), EMAIL, "m")
        assert result.ok is False
        assert result.provider == "raising"
        assert "ConnectionError" in result.error
        assert "gateway timed out" in result.error

    def test_a_sender_that_returns_nothing_is_a_failure(self):
        """The old protocol, and the silent failure this change exists to end:
        an adapter that forgot to return must not look like one that worked."""
        result = otp.deliver(_Silent(), EMAIL, "m")
        assert result.ok is False
        assert result.provider == "silent"

    def test_the_logging_sender_reports_success(self):
        result = otp.deliver(otp.LoggingSender(), EMAIL, "m")
        assert result == otp.SendResult(ok=True, provider="logging")


class TestCompositeSender:
    def test_the_first_that_accepts_wins_and_is_named(self):
        first, second = _Accepting("first"), _Accepting("second")
        result = otp.CompositeSender([first, second]).send(EMAIL, "m")
        assert result.ok is True
        assert result.provider == "first"
        assert len(first.sent) == 1
        # Never reached: a fallback that also sends is a second message the
        # recipient never asked for, and a second line on the bill.
        assert second.sent == []

    def test_first_fails_second_succeeds(self):
        first, second = _Refusing("first"), _Accepting("second")
        result = otp.CompositeSender([first, second]).send(EMAIL, "m")
        assert result.ok is True
        assert result.provider == "second"
        assert len(first.sent) == 1 and len(second.sent) == 1

    def test_a_raising_child_does_not_take_the_chain_down(self):
        result = otp.CompositeSender([_Raising(), _Accepting("second")]).send(EMAIL, "m")
        assert result.ok is True
        assert result.provider == "second"

    def test_all_fail_and_every_error_is_reported(self):
        chain = otp.CompositeSender([_Refusing("a", "no credit"), _Refusing("b", "bad number")])
        result = chain.send(EMAIL, "m")
        assert result.ok is False
        assert result.provider == "composite"
        assert "a: no credit" in result.error
        assert "b: bad number" in result.error

    def test_an_empty_chain_is_a_refusal_not_a_crash(self):
        result = otp.CompositeSender([]).send(EMAIL, "m")
        assert result.ok is False
        assert "no senders" in result.error

    def test_a_fallback_success_is_warned_about(self, caplog):
        """A primary that is failing is a bill and a latency somebody should
        hear about before the secondary fails too."""
        with caplog.at_level(logging.WARNING, logger="kolabo.auth.otp"):
            otp.CompositeSender([_Refusing("first"), _Accepting("second")]).send(EMAIL, "m")
        assert any("first" in rec.getMessage() and "second" in rec.getMessage() for rec in caplog.records)


class TestRoutingSender:
    """Kept green over code nothing calls, and that is deliberate.

    RoutingSender routes on the dialling prefix of a phone number and codes go
    to mailboxes now, so nothing in the application builds one. It is kept for
    the day an SMS channel returns (see its docstring), and a class that is
    kept without tests is a class that has quietly rotted by the time anybody
    wants it. These still use phone numbers because that is what it routes on.
    """

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
        result = router.send(EMAIL, "m")
        assert result.ok is True
        assert result.provider == "backup"


class TestTheDefaultSender:
    """Which sender a deployment gets, and the rule that decides.

    The rule is notifications.email.build_default_email_sender's and is asked
    rather than restated, so there is one definition of "configured" rather
    than two that can disagree about a half-filled .env.
    """

    def test_it_is_the_logging_one_until_mail_is_configured(self):
        """A laptop and the test suite have no mail credentials and must keep
        printing the code, not acquire a mail client that fails every send."""
        assert isinstance(otp.build_default_sender(), otp.LoggingSender)
        assert otp.default_sender.name == "logging"

    def test_a_configured_deployment_gets_the_email_adapter(self, monkeypatch):
        """Both a key and a from address, or neither counts. Set through the
        settings object the email module actually reads."""
        from app.modules.notifications import email as email_module

        monkeypatch.setattr(email_module.settings, "resend_api_key", "re_test", raising=False)
        monkeypatch.setattr(email_module.settings, "mail_from", "no-reply@kolabo.test", raising=False)
        sender = otp.build_default_sender()
        assert isinstance(sender, otp.EmailSender)
        assert sender.name == "email"
        assert isinstance(sender.mail, email_module.ResendSender)

    def test_a_key_with_no_from_address_is_still_unconfigured(self, monkeypatch):
        """An unconfigured provider is ABSENT rather than present and broken.
        Half a configuration would accept every send and fail every one of
        them somewhere only the logs can see."""
        from app.modules.notifications import email as email_module

        monkeypatch.setattr(email_module.settings, "resend_api_key", "re_test", raising=False)
        monkeypatch.setattr(email_module.settings, "mail_from", "", raising=False)
        assert isinstance(otp.build_default_sender(), otp.LoggingSender)


class TestEmailSender:
    """The adapter from this module's Sender onto the notifications one."""

    def test_it_hands_the_target_and_the_body_to_the_mail_provider(self):
        from app.modules.notifications import email as email_module

        mail = email_module.LoggingEmailSender()
        result = otp.EmailSender(mail).send(EMAIL, "Subject line\n\nbody")
        assert result == otp.SendResult(ok=True, provider="email")
        assert mail.outbox == [
            {"target": EMAIL, "type": "security", "message": "Subject line\n\nbody"}
        ]

    def test_a_mail_provider_that_raises_is_still_a_failed_result(self):
        """The one failure it CAN see. notifications.email.Sender.send returns
        None and ResendSender swallows HTTP errors, so a refusal is invisible
        to this adapter and is reported as ok — which EmailSender's docstring
        says out loud. An exception is not, because deliver catches it."""

        class _Exploding:
            def send(self, target, type, message):
                raise RuntimeError("no credentials")

        result = otp.deliver(otp.EmailSender(_Exploding()), EMAIL, "m")
        assert result.ok is False
        assert "RuntimeError" in result.error


class TestTheMessageItself:
    """Subject and body, in the language the account's country defaults to.

    These call the template directly, which is why closing Ghana and Nigeria to
    registration costs them nothing: default_language still knows both, because
    a party may contract from a country Kolabo does not sell in.
    """

    def test_french_for_a_francophone_market(self):
        message = otp.verification_message("BJ", "123456", 10)
        assert message.startswith("Votre code de vérification Kolabo\n\n")
        assert "123456" in message
        assert "10 minutes" in message

    def test_english_for_an_anglophone_market(self):
        message = otp.verification_message("GH", "123456", 10)
        assert message.startswith("Your Kolabo verification code\n\n")

    def test_the_reset_message_is_treated_the_same_way(self):
        assert otp.password_reset_message("CI", "654321", 15).startswith(
            "Votre code de réinitialisation Kolabo\n\n"
        )
        assert otp.password_reset_message("NG", "654321", 15).startswith(
            "Your Kolabo password reset code\n\n"
        )

    def test_an_unknown_country_gets_the_default_language_rather_than_a_crash(self):
        """default_language already falls back for an unconfigured country; this
        asserts the template lookup does too, because a KeyError here would be
        a 500 on somebody's signup."""
        assert otp.verification_message(None, "123456", 10).startswith("Votre code")
        assert otp.verification_message("ZZ", "123456", 10).startswith("Votre code")

    def test_the_first_line_is_what_the_mail_module_will_use_as_a_subject(self):
        """The whole subject mechanism, asserted across the seam rather than
        assumed: otp composes the message, notifications/email.py reads its
        first line. Two modules agreeing by convention is worth one test."""
        from app.modules.notifications.email import _subject

        assert _subject(otp.verification_message("GH", "123456", 10)) == (
            "Your Kolabo verification code"
        )
        assert _subject(otp.password_reset_message("BJ", "654321", 15)) == (
            "Votre code de réinitialisation Kolabo"
        )

    def test_nothing_in_a_credential_email_looks_like_marketing(self):
        """No unsubscribe link on a message somebody needs in order to sign in,
        no tracking, no HTML. A credential email that carries any of those is
        harder to tell from a phishing attempt."""
        for message in (
            otp.verification_message("BJ", "123456", 10),
            otp.verification_message("GH", "123456", 10),
            otp.password_reset_message("BJ", "654321", 15),
            otp.password_reset_message("GH", "654321", 15),
        ):
            lowered = message.lower()
            assert "http" not in lowered
            assert "unsubscribe" not in lowered
            assert "désabonner" not in lowered
            assert "<" not in message
            # No em dash and no en dash in anything a user reads.
            assert "—" not in message
            assert "–" not in message

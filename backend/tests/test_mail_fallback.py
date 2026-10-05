"""A production deployment must not fall back to the logging senders.

WHY THIS FILE EXISTS, and it is not the thing the ticket that prompted it
described. The claim was that LoggingSender's comment "this is never enabled in
production" is false. It is not: that sentence is about the `print("[DEV OTP]
...")` line directly under it, which really is wrapped in `if settings.env ==
"development"`. What is unguarded is the `_log.info` ABOVE it, which carries the
code, and more importantly what is unguarded is the FALLBACK ITSELF.

THE FAILURE THIS GUARDS, which is worse than a code in a log.
notifications/email.build_default_email_sender returns the real provider only
when RESEND_API_KEY and MAIL_FROM are BOTH set, and LoggingEmailSender
otherwise. auth/otp.build_default_sender sees that and returns its own
LoggingSender, which answers SendResult(ok=True). So a production box missing
either value tells every person registering that their code is on the way,
writes the code to the container log, sends no mail, and leaves nobody able to
verify an account. Registration looks like it works.

TWO LAYERS, AND THIS ASSERTS BOTH. deploy/checks/preflight-env.sh refuses the
deploy, which is where the refusal belongs: app/core/config.py keeps
RESEND_API_KEY out of its production validator on the stated grounds that a
deployment without mail should not refuse to boot, and that decision is left
standing rather than overturned here. The ERROR log is the second layer, for a
container started without the preflight.

Development is asserted too, and that assertion matters as much as the others:
a laptop and this test suite have no mail credentials and must keep printing the
code, so the fallback has to stay silent there.
"""
import logging
from pathlib import Path

import pytest

from app.core.config import settings
from app.modules.auth import otp
from app.modules.notifications import email as email_module

OTP_LOGGER = "kolabo.auth.otp"


@pytest.fixture
def mail_config(monkeypatch):
    """Set the three values that decide which sender a deployment gets."""

    def configure(env: str, key: str, mail_from: str) -> None:
        monkeypatch.setattr(settings, "env", env)
        monkeypatch.setattr(settings, "resend_api_key", key)
        monkeypatch.setattr(settings, "mail_from", mail_from)

    return configure


KEY = "re_test_key_not_a_real_one"
FROM = "Kolabo <codes@example.test>"


class TestWhichSenderADeploymentGets:
    def test_both_values_give_the_real_provider(self, mail_config):
        mail_config("production", KEY, FROM)
        assert isinstance(email_module.build_default_email_sender(), email_module.ResendSender)
        assert isinstance(otp.build_default_sender(), otp.EmailSender)

    @pytest.mark.parametrize(
        "key,mail_from",
        [
            pytest.param(KEY, "", id="key without from address"),
            pytest.param("", FROM, id="from address without key"),
            pytest.param("", "", id="neither"),
        ],
    )
    def test_either_value_missing_falls_back(self, mail_config, key, mail_from):
        """BOTH halves are required, which is the part easy to get wrong.

        A deployment that set the key and forgot the from address is in exactly
        the same state as one that set neither, and the person who set the key
        is the most likely to believe mail works.
        """
        mail_config("production", key, mail_from)
        assert isinstance(
            email_module.build_default_email_sender(), email_module.LoggingEmailSender
        )
        assert isinstance(otp.build_default_sender(), otp.LoggingSender)


class TestTheFallbackIsLoudInProductionAndSilentInDevelopment:
    def test_production_logs_an_error_naming_both_variables(self, mail_config, caplog):
        mail_config("production", "", "")
        with caplog.at_level(logging.ERROR, logger=OTP_LOGGER):
            otp.build_default_sender()
        errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(errors) == 1, "exactly one error, so a restart loop is readable"
        message = errors[0].getMessage()
        # The person reading this is mid-deploy and needs the fix, not a hint.
        assert "RESEND_API_KEY" in message
        assert "MAIL_FROM" in message
        assert "preflight-env.sh" in message

    def test_development_says_nothing(self, mail_config, caplog):
        """The quiet case, and it has to stay quiet.

        Every local run and every test in this suite takes this branch. An
        error here would put a line nobody can act on into the output of every
        developer who has ever cloned this repository.
        """
        mail_config("development", "", "")
        with caplog.at_level(logging.DEBUG, logger=OTP_LOGGER):
            assert isinstance(otp.build_default_sender(), otp.LoggingSender)
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


class TestTheDeployRefusesBeforeAnyOfThatMatters:
    """The preflight is the first layer, and it lives outside Python.

    Asserted as source text rather than executed, the same way
    web/src/lib/env.test.ts pins its build arg chain: what can break silently
    here is the LINK between a script in deploy/ and the behaviour in this
    module, and nothing in a Python test run would notice that link being cut.
    """

    SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "checks" / "preflight-env.sh"

    def test_the_script_is_where_this_test_thinks_it_is(self):
        assert self.SCRIPT.is_file(), f"not found: {self.SCRIPT}"

    def test_production_requires_both_mail_values(self):
        text = self.SCRIPT.read_text(encoding="utf-8")
        assert "RESEND_API_KEY MAIL_FROM" in text, "the required pair, in one loop"
        assert 'if [[ "$APP_ENV" == "production" ]]; then' in text, "guarded on production"

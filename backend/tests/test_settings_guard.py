"""Production refuses to start on a committed default secret (KOL-52).

WHAT WAS WRONG. Settings() has working defaults for every secret so a laptop
runs with no setup, and nothing checked whether a production deployment had
replaced them. A deploy that forgot JWT_SECRET ran happily on "change-me",
which is in a public git history, and a forged admin token reaches
POST /payments/escrow/{id}/resolve. One missed environment variable was a full
compromise that announced itself nowhere.

Settings is constructed directly here rather than through the module-level
`settings` object: that object is built at import from whatever environment
the test process has, and what is under test is the RULE, not this machine's
environment. Every secret is passed explicitly so a stray JWT_SECRET in the
CI environment cannot turn a red test green or a green one red, and
_env_file=None keeps a developer's own .env out of it.
"""
import pytest

from app.core.config import DEFAULT_DOCUMENT_ENCRYPTION_KEY, DEFAULT_JWT_SECRET, Settings

REAL_SECRET = "0f7c1d0e8c9a4c2f9b6e1a3d5f7b9c2e4a6c8e0b2d4f6a8c0e2b4d6f8a0c2e4b"
REAL_KEY = "Zm9yLXRlc3RzLW9ubHktbm90LWEtcmVhbC1mZXJuZXQta2V5PT0="


def _settings(**overrides):
    values = dict(
        jwt_secret=REAL_SECRET,
        document_encryption_key=REAL_KEY,
        fedapay_secret_key="",
        fedapay_webhook_secret="",
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


class TestProduction:
    def test_refuses_the_committed_jwt_secret_and_names_it(self):
        with pytest.raises(RuntimeError) as exc:
            _settings(env="production", jwt_secret=DEFAULT_JWT_SECRET)
        message = str(exc.value)
        assert "JWT_SECRET" in message
        assert "ENV=production" in message
        # Only the offender is named; a correct key is not dragged in.
        assert "DOCUMENT_ENCRYPTION_KEY" not in message

    def test_refuses_the_committed_document_key_and_names_it(self):
        with pytest.raises(RuntimeError) as exc:
            _settings(env="production", document_encryption_key=DEFAULT_DOCUMENT_ENCRYPTION_KEY)
        message = str(exc.value)
        assert "DOCUMENT_ENCRYPTION_KEY" in message
        assert "JWT_SECRET" not in message

    def test_names_every_offender_at_once(self):
        """The person reading this is mid-deploy. One traceback, every fix."""
        with pytest.raises(RuntimeError) as exc:
            _settings(
                env="production",
                jwt_secret=DEFAULT_JWT_SECRET,
                document_encryption_key=DEFAULT_DOCUMENT_ENCRYPTION_KEY,
            )
        message = str(exc.value)
        assert "JWT_SECRET" in message
        assert "DOCUMENT_ENCRYPTION_KEY" in message

    def test_refuses_live_payments_without_a_webhook_secret(self):
        """Nothing surfaced this before: /payments/config reported healthy
        right up until the first webhook was rejected."""
        with pytest.raises(RuntimeError) as exc:
            _settings(env="production", fedapay_secret_key="sk_live_x", fedapay_webhook_secret="")
        assert "FEDAPAY_WEBHOOK_SECRET" in str(exc.value)

    def test_an_empty_webhook_secret_is_fine_while_payments_are_off(self):
        """With no secret key the registry is empty and no webhook will ever
        arrive, so there is nothing to verify and nothing to refuse."""
        assert _settings(env="production", fedapay_secret_key="", fedapay_webhook_secret="").env == "production"

    def test_accepts_real_secrets(self):
        s = _settings(env="production", fedapay_secret_key="sk_live_x", fedapay_webhook_secret="wh_x")
        assert s.jwt_secret == REAL_SECRET
        assert s.document_encryption_key == REAL_KEY


class TestDevelopment:
    """Unchanged: a laptop still runs with no setup."""

    def test_the_defaults_construct(self):
        s = Settings(_env_file=None, env="development", jwt_secret=DEFAULT_JWT_SECRET,
                     document_encryption_key=DEFAULT_DOCUMENT_ENCRYPTION_KEY)
        assert s.jwt_secret == DEFAULT_JWT_SECRET

    def test_the_env_default_itself_is_development(self):
        s = Settings(_env_file=None, jwt_secret=DEFAULT_JWT_SECRET,
                     document_encryption_key=DEFAULT_DOCUMENT_ENCRYPTION_KEY)
        assert s.env == "development"

    def test_any_other_environment_name_is_left_alone(self):
        """Only production refuses. A staging box on the defaults is a choice,
        and not the one this guard exists to prevent."""
        s = Settings(_env_file=None, env="staging", jwt_secret=DEFAULT_JWT_SECRET,
                     document_encryption_key=DEFAULT_DOCUMENT_ENCRYPTION_KEY)
        assert s.env == "staging"

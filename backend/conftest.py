"""Test configuration.

Force an in memory SQLite database for the test suite so tests do not require a
running PostgreSQL instance. A CI job that provides its own DATABASE_URL still
takes precedence because setdefault does not overwrite an existing value.
"""
import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite://")

# Deliberately outside the +2299000... space the test files seed their own
# users in, so the shared admin below can never collide with one of theirs.
ADMIN_PHONE = "+22999000001"


@pytest.fixture()
def admin_user_id(client):
    """A real admin account, in whatever database the test's client is using.

    X-Admin-Id used to be the whole credential. It is now an unrecognised
    header, so every test that acts as an admin needs an account with
    is_admin set and a token for it — see app.modules.auth.admins.

    is_admin is set directly rather than via sync_admins, because what these
    tests are about is what an admin may DO, not how somebody becomes one.
    test_admin_auth.py owns the granting.

    Depends on the per-file `client` fixture, every one of which hangs its
    sessionmaker on the TestClient as `session_factory`.

    The import is inside the function so that the DATABASE_URL default above
    is already set before any app module reads the settings.
    """
    from app.modules.auth.models import User

    db = client.session_factory()
    try:
        admin = User(
            phone=ADMIN_PHONE,
            password_hash="x",
            country_code="BJ",
            role="business",
            is_verified=True,
            is_admin=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        return admin.id
    finally:
        db.close()


@pytest.fixture()
def admin_headers(admin_user_id):
    """The bearer token that proves the account above is an admin.

    Two fixtures rather than one so that a test which has to NAME the admin —
    the resolved_by assertion in test_dispute_resolution.py — can ask for the
    id on its own, and still gets the same account the headers authenticate.
    """
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(admin_user_id)}"}

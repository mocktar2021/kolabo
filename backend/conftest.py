"""Test configuration.

Force an in memory SQLite database for the test suite so tests do not require a
running PostgreSQL instance. A CI job that provides its own DATABASE_URL still
takes precedence because setdefault does not overwrite an existing value.
"""
import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite://")

# Deliberately outside the space the test files seed their own users in, so the
# shared admin below can never collide with one of theirs.
#
# BOTH COLUMNS, because the fixture writes both. The address is what the
# account IS since the identity flip and is the column auth.admins matches on;
# the phone is kept because users.phone still exists, still has no unique index
# to collide on, and a seeded admin that looks like a real pre-flip account is
# a better fixture than one that is missing half its contact details.
ADMIN_EMAIL = "conftest-admin@kolabo.test"
ADMIN_PHONE = "+22999000001"


@pytest.fixture(autouse=True)
def profile_owner_from_path(request):
    """Keep the 168 existing profile tests testing PROFILES, not tokens.

    The profiles router used to take the account being written to straight out
    of the URL, with no authentication anywhere on it. It now takes it from the
    bearer token and ignores the path entirely — see the module docstring in
    app/modules/profiles/router.py for why that is stronger than comparing the
    two and refusing a mismatch.

    Five test files make 168 calls to that router and not one of them sends a
    token, because until now there was nothing to send one to. Rewriting all
    168 to mint a token each would be a very large diff whose only effect is to
    re-state, 168 times, a rule that has exactly one place worth testing. So
    the seam is overridden here instead: `profile_owner` resolves to the id in
    the path, which is precisely what those tests assumed before this change.
    Their behaviour is unchanged, including the ones that assert a 403 when one
    creator touches another's package — that check lives in the service and is
    untouched.

    The guard itself is tested properly, without this override, in
    test_profiles_auth.py. It gets there by naming its fixture `auth_client`
    rather than `client`, which is what the guard below keys on.

    Migrating the five files to real tokens is worth doing and is deliberately
    not in the same change as the security fix.
    """
    if "client" not in request.fixturenames:
        yield
        return

    client = request.getfixturevalue("client")
    app = getattr(client, "app", None)
    if app is None:
        yield
        return

    from app.modules.profiles.router import profile_owner

    app.dependency_overrides[profile_owner] = lambda user_id: user_id
    try:
        yield
    finally:
        app.dependency_overrides.pop(profile_owner, None)


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
            email=ADMIN_EMAIL,
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

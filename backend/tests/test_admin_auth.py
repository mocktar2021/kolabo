"""An admin is an account, not a header.

`get_current_admin` used to accept any non-empty X-Admin-Id header and return
it as an identity. That gate stood in front of splitting a disputed escrow —
which moves real money — as well as approving identity documents and enabling
countries, and anybody who could reach the API could set a header.

The first test in this file is the one that matters most: the old credential
must now be REFUSED. A change like this is only worth anything if the door it
replaced is actually shut, and "we added a better lock" is not the same
sentence as "the old key no longer works".
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import config as config_module
from app.core.db import Base, get_db, import_all_models
from app.core.errors import AppError, app_error_handler
from app.core.security import create_access_token
from app.modules.admin.router import router as admin_router
from app.modules.auth.admins import sync_admins
from app.modules.auth.models import User

ADMIN_PHONE = "+22990000100"
CIVILIAN_PHONE = "+22990000200"


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    import_all_models()
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    # The REAL error handler, because one of these tests asserts on the `code`
    # in the body and AppError subclasses HTTPException — without this,
    # FastAPI's default renders {"detail": ...} alone and the assertion fails
    # on a missing key rather than on a wrong answer. Same reason and same
    # registration as backend/tests/test_error_codes.py.
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(admin_router, prefix="/admin")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


@pytest.fixture()
def people(client):
    """One user who will be made an admin, one who will not."""
    db = client.session_factory()
    try:
        admin = User(phone=ADMIN_PHONE, password_hash="x", country_code="BJ",
                     role="business", is_verified=True)
        civilian = User(phone=CIVILIAN_PHONE, password_hash="x", country_code="BJ",
                        role="influencer", is_verified=True)
        db.add_all([admin, civilian]); db.commit(); db.refresh(admin); db.refresh(civilian)
        return {"admin": admin.id, "civilian": civilian.id}
    finally:
        db.close()


def _configure(monkeypatch, phones: str):
    monkeypatch.setattr(config_module.settings, "admin_phones", phones, raising=False)
    # auth.admins reads the same settings object by reference.
    from app.modules.auth import admins as admins_module

    monkeypatch.setattr(admins_module.settings, "admin_phones", phones, raising=False)


def _sync(client):
    db = client.session_factory()
    try:
        return sync_admins(db)
    finally:
        db.close()


def _is_admin(client, user_id):
    db = client.session_factory()
    try:
        return db.query(User).filter(User.id == user_id).first().is_admin
    finally:
        db.close()


def _token(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


# --------------------------------------------------------------------------
# The old key does not work
# --------------------------------------------------------------------------


def test_the_admin_id_header_alone_is_refused(client, people, monkeypatch):
    """THE POINT OF THE WHOLE CHANGE.

    Any string in X-Admin-Id used to be a valid admin credential. It is now
    just an unknown header, and a request carrying nothing else is
    unauthenticated.
    """
    _configure(monkeypatch, ADMIN_PHONE)
    _sync(client)
    r = client.get("/admin/dashboard", headers={"X-Admin-Id": "anyone-at-all"})
    assert r.status_code == 401


def test_the_header_cannot_upgrade_an_ordinary_token(client, people, monkeypatch):
    """Belt and braces: a real login PLUS the old header is still not an admin.

    Worth its own test because a half-finished migration — the dependency
    changed but the header still consulted somewhere — would pass the test
    above and fail this one.
    """
    _configure(monkeypatch, ADMIN_PHONE)
    _sync(client)
    r = client.get(
        "/admin/dashboard",
        headers={**_token(people["civilian"]), "X-Admin-Id": people["admin"]},
    )
    assert r.status_code == 403


# --------------------------------------------------------------------------
# The new key does
# --------------------------------------------------------------------------


def test_no_credential_at_all_is_401(client, people):
    assert client.get("/admin/dashboard").status_code == 401


def test_an_ordinary_user_is_403(client, people, monkeypatch):
    """We know exactly who you are, and the answer is still no."""
    _configure(monkeypatch, ADMIN_PHONE)
    _sync(client)
    r = client.get("/admin/dashboard", headers=_token(people["civilian"]))
    assert r.status_code == 403
    assert r.json()["code"] == "admin_not_authorised"


def test_a_configured_admin_gets_in(client, people, monkeypatch):
    _configure(monkeypatch, ADMIN_PHONE)
    _sync(client)
    assert client.get("/admin/dashboard", headers=_token(people["admin"])).status_code == 200


def test_a_deleted_account_with_a_live_token_is_403(client, people, monkeypatch):
    """A token outlives the row it names. The gate loads the user rather than
    trusting the subject claim, so a deleted admin's unexpired token is not a
    way back in."""
    _configure(monkeypatch, ADMIN_PHONE)
    _sync(client)
    db = client.session_factory()
    try:
        db.query(User).filter(User.id == people["admin"]).delete()
        db.commit()
    finally:
        db.close()
    assert client.get("/admin/dashboard", headers=_token(people["admin"])).status_code == 403


# --------------------------------------------------------------------------
# The list is the source of truth, in both directions
# --------------------------------------------------------------------------


def test_nobody_is_an_admin_by_default(client, people, monkeypatch):
    """An unconfigured deployment locks the admin surface rather than opening
    it — the opposite of what the header did."""
    _configure(monkeypatch, "")
    assert _sync(client) == {"granted": 0, "revoked": 0, "no_account": 0}
    assert _is_admin(client, people["admin"]) is False
    assert client.get("/admin/dashboard", headers=_token(people["admin"])).status_code == 403


def test_listing_a_phone_grants_it(client, people, monkeypatch):
    _configure(monkeypatch, ADMIN_PHONE)
    assert _sync(client)["granted"] == 1
    assert _is_admin(client, people["admin"]) is True


def test_the_sync_is_idempotent(client, people, monkeypatch):
    """It runs on every boot, so a second run must be a no-op."""
    _configure(monkeypatch, ADMIN_PHONE)
    _sync(client)
    assert _sync(client) == {"granted": 0, "revoked": 0, "no_account": 0}


def test_removing_a_phone_revokes_it(client, people, monkeypatch):
    """THE HALF THAT MAKES IT A SYNC RATHER THAN A SEED.

    Without this, removing somebody's access means remembering to go and edit
    a row by hand — on precisely the day nobody wants to be hand-editing
    production data.
    """
    _configure(monkeypatch, ADMIN_PHONE)
    _sync(client)
    _configure(monkeypatch, "")
    assert _sync(client)["revoked"] == 1
    assert _is_admin(client, people["admin"]) is False
    assert client.get("/admin/dashboard", headers=_token(people["admin"])).status_code == 403


def test_a_listed_phone_with_no_account_is_counted_not_created(client, people, monkeypatch):
    """Creating a passwordless user from a config file would be a worse hole
    than the one this closes. They become an admin at the next boot after they
    register, and until then it is reported rather than silently ignored."""
    _configure(monkeypatch, f"{ADMIN_PHONE},+22990000999")
    result = _sync(client)
    assert result["granted"] == 1
    assert result["no_account"] == 1
    db = client.session_factory()
    try:
        assert db.query(User).filter(User.phone == "+22990000999").first() is None
    finally:
        db.close()


def test_the_list_tolerates_spaces_and_blanks(client, people, monkeypatch):
    """It is hand-edited deployment config, so it is written by a person."""
    _configure(monkeypatch, f"  {ADMIN_PHONE} , , ")
    assert _sync(client)["granted"] == 1
    assert _is_admin(client, people["admin"]) is True


def test_several_admins_coexist(client, people, monkeypatch):
    _configure(monkeypatch, f"{ADMIN_PHONE},{CIVILIAN_PHONE}")
    assert _sync(client)["granted"] == 2
    for who in ("admin", "civilian"):
        assert client.get("/admin/dashboard", headers=_token(people[who])).status_code == 200

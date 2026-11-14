"""Creating, undoing and listing a block.

The guards merged before this all enforce a row nothing could create. These
are the three routes that make the feature exist, and two of the tests here
are about privacy rather than about mechanics:

  * the list shows only rows the CALLER made. If it showed blocks made
    against them, the settings screen would become a way to find out who has
    blocked you, which is the single thing a block exists to keep somebody
    from learning.

  * unblocking removes one row and not the pair. Two people who have both
    blocked each other have made two decisions, and changing your mind is
    not permission to change theirs.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db, import_all_models
from app.core.errors import AppError, app_error_handler
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.profiles import models as pmodels
from app.modules.trust_safety.models import Block
from app.modules.trust_safety.router import router as ts_router


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
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
    app.include_router(ts_router, prefix="/trust-safety")
    # The real handler, not a lookalike: without it an AppError loses its
    # `code` to FastAPI's default serialiser and every assertion below reads
    # a KeyError instead of a refusal. core/errors.py keeps it importable for
    # exactly this.
    app.add_exception_handler(AppError, app_error_handler)
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _creator(client, phone, display_name):
    db = client.session_factory()
    try:
        user = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x",
                    country_code="BJ", role="influencer", is_verified=True)
        db.add(user); db.commit(); db.refresh(user)
        db.add(pmodels.InfluencerProfile(
            user_id=user.id, bio="Creator", categories=["fashion"], rate_card={},
            follower_count=5000, display_name=display_name,
        ))
        db.commit()
        return user.id
    finally:
        db.close()


def _business(client, phone, company_name="Maison Kola"):
    db = client.session_factory()
    try:
        user = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x",
                    country_code="BJ", role="business", is_verified=True)
        db.add(user); db.commit(); db.refresh(user)
        db.add(pmodels.BusinessProfile(user_id=user.id, company_name=company_name))
        db.commit()
        return user.id
    finally:
        db.close()


def _rows(client):
    db = client.session_factory()
    try:
        return db.query(Block).all()
    finally:
        db.close()


# ---- creating ----

def test_blocking_writes_a_row_and_names_the_person(client):
    me = _business(client, "+22990100001")
    them = _creator(client, "+22990100002", "Ama K.")

    r = client.post(f"/trust-safety/blocks/{them}", headers=_headers(me))
    assert r.status_code == 201
    body = r.json()
    assert body["user_id"] == them
    assert body["display_name"] == "Ama K."
    assert body["reason_code"] is None


def test_a_brand_is_named_by_its_company_name(client):
    """A blocked account can be on either side, and a list that could only
    name creators would show a creator's own blocks as blank rows."""
    me = _creator(client, "+22990100010", "Ama K.")
    them = _business(client, "+22990100011", company_name="Maison Kola")

    assert client.post(f"/trust-safety/blocks/{them}", headers=_headers(me)).json()["display_name"] == "Maison Kola"


def test_blocking_twice_is_not_a_conflict(client):
    """Somebody on a slow connection tapping the button again."""
    me = _business(client, "+22990100020")
    them = _creator(client, "+22990100021", "Ama K.")

    first = client.post(f"/trust-safety/blocks/{them}", headers=_headers(me))
    second = client.post(f"/trust-safety/blocks/{them}", headers=_headers(me))
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["created_at"] == second.json()["created_at"]
    assert len(_rows(client)) == 1


def test_you_cannot_block_yourself(client):
    me = _business(client, "+22990100030")
    r = client.post(f"/trust-safety/blocks/{me}", headers=_headers(me))
    assert r.status_code == 400
    assert r.json()["code"] == "block_self"
    assert _rows(client) == []


def test_an_unknown_account_is_a_404_and_not_a_500(client):
    """Both columns are foreign keys, so an unknown id would otherwise be an
    integrity error surfacing as a 500 on a safety control."""
    me = _business(client, "+22990100040")
    r = client.post("/trust-safety/blocks/nobody", headers=_headers(me))
    assert r.status_code == 404
    assert r.json()["code"] == "block_target_not_found"


def test_a_reason_code_is_kept_and_an_invented_one_is_refused(client):
    me = _business(client, "+22990100050")
    them = _creator(client, "+22990100051", "Ama K.")

    r = client.post(
        f"/trust-safety/blocks/{them}", json={"reason_code": "harassment"}, headers=_headers(me)
    )
    assert r.json()["reason_code"] == "harassment"

    other = _creator(client, "+22990100052", "Kofi")
    bad = client.post(
        f"/trust-safety/blocks/{other}", json={"reason_code": "banana"}, headers=_headers(me)
    )
    assert bad.status_code == 400
    assert bad.json()["code"] == "report_reason_unknown"


# ---- undoing ----

def test_unblocking_removes_the_row_and_is_silent_when_there_is_nothing(client):
    me = _business(client, "+22990100100")
    them = _creator(client, "+22990100101", "Ama K.")
    client.post(f"/trust-safety/blocks/{them}", headers=_headers(me))

    assert client.delete(f"/trust-safety/blocks/{them}", headers=_headers(me)).status_code == 204
    assert _rows(client) == []
    # Again, with nothing to undo. The caller asked for a state, not an
    # operation, and they have it either way.
    assert client.delete(f"/trust-safety/blocks/{them}", headers=_headers(me)).status_code == 204


def test_unblocking_undoes_your_row_and_never_theirs(client):
    """Two people who have both blocked each other made two decisions."""
    a = _business(client, "+22990100110")
    b = _creator(client, "+22990100111", "Ama K.")
    client.post(f"/trust-safety/blocks/{b}", headers=_headers(a))
    client.post(f"/trust-safety/blocks/{a}", headers=_headers(b))
    assert len(_rows(client)) == 2

    client.delete(f"/trust-safety/blocks/{b}", headers=_headers(a))
    remaining = _rows(client)
    assert len(remaining) == 1
    assert remaining[0].blocker_user_id == b


# ---- listing ----

def test_the_list_is_newest_first_and_carries_names(client):
    me = _business(client, "+22990100200")
    first = _creator(client, "+22990100201", "First")
    second = _creator(client, "+22990100202", "Second")
    client.post(f"/trust-safety/blocks/{first}", headers=_headers(me))
    client.post(f"/trust-safety/blocks/{second}", headers=_headers(me))

    rows = client.get("/trust-safety/blocks", headers=_headers(me)).json()
    assert [r["user_id"] for r in rows] == [second, first]
    assert {r["display_name"] for r in rows} == {"First", "Second"}


def test_the_list_never_shows_who_blocked_you(client):
    """THE PRIVACY LINE OF THE WHOLE FEATURE. A settings screen that showed
    this would be a tool for finding out who has blocked you."""
    me = _business(client, "+22990100210")
    them = _creator(client, "+22990100211", "Ama K.")
    client.post(f"/trust-safety/blocks/{me}", headers=_headers(them))

    assert client.get("/trust-safety/blocks", headers=_headers(me)).json() == []
    # And the person who DID block sees their own row, so the list is not
    # simply broken.
    assert len(client.get("/trust-safety/blocks", headers=_headers(them)).json()) == 1


def test_an_empty_list_is_an_empty_list(client):
    me = _business(client, "+22990100220")
    assert client.get("/trust-safety/blocks", headers=_headers(me)).json() == []


# ---- auth ----

def test_every_block_route_requires_a_token(client):
    them = _creator(client, "+22990100300", "Ama K.")
    assert client.post(f"/trust-safety/blocks/{them}").status_code == 401
    assert client.delete(f"/trust-safety/blocks/{them}").status_code == 401
    assert client.get("/trust-safety/blocks").status_code == 401

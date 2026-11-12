"""Closing your account works after you have blocked somebody.

WHY THIS FILE ENFORCES FOREIGN KEYS WHEN NOTHING ELSE IN THE SUITE DOES.

auth.service.delete_account removes a departing user's rows by hand, table by
table, and that list is maintained by remembering to add to it. It has been
wrong in production twice. KOL-144 is written into the function itself:
fk_social_tokens_social_account_id has no ON DELETE CASCADE, Postgres refused
the DELETE, the request 500ed, and the cascade test written in October passed
throughout because the account it built had never connected anything. The
second half of the same bug, oauth_states, was missed the same way.

THE REASON CI COULD NOT CATCH EITHER is one line of SQLite behaviour: foreign
keys are OFF by default, and every other fixture here leaves them off.
Postgres enforces them. So a forgotten cleanup is invisible in CI and fatal on
the production box, on a request made by somebody who was already leaving.

So this fixture turns the pragma on. The graph it builds is deliberately the
smallest one that can expose a missing block cleanup: two users and a block
between them, no profiles, no campaigns, no contracts. A failure here names
exactly one missing line rather than a tangle, and the test cannot pass for
the wrong reason.

THIS IS NOT A TEST ABOUT BLOCKS SO MUCH AS A SEAM. Anything added later that
references users and is forgotten in delete_account will fail here too, as
long as it is added to the graph below. That is the point of keeping it
separate from the big cascade test rather than folding it in.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db, import_all_models
from app.core.errors import AppError, app_error_handler
from app.core.security import create_access_token, hash_password
from app.modules.auth.models import User
from app.modules.auth.router import router as auth_router
from app.modules.trust_safety.models import Block

PASSWORD = "correct horse battery"


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )

    # THE WHOLE POINT OF THIS FILE. Without it SQLite accepts a DELETE that
    # leaves a child row pointing at nothing, and this test would pass
    # against the bug it exists to catch.
    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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
    app.include_router(auth_router, prefix="/auth")
    app.add_exception_handler(AppError, app_error_handler)
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _user(client, phone, role="influencer"):
    db = client.session_factory()
    try:
        user = User(
            phone=phone,
            email=f"{phone.lstrip('+')}@kolabo.test",
            password_hash=hash_password(PASSWORD),
            country_code="BJ",
            role=role,
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def _block(client, blocker, blocked):
    db = client.session_factory()
    try:
        db.add(Block(blocker_user_id=blocker, blocked_user_id=blocked))
        db.commit()
    finally:
        db.close()


def _counts(client):
    db = client.session_factory()
    try:
        return db.query(User).count(), db.query(Block).count()
    finally:
        db.close()


def _delete(client, user_id):
    return client.request(
        "DELETE",
        "/auth/me",
        json={"password": PASSWORD},
        headers={"Authorization": f"Bearer {create_access_token(user_id)}"},
    )


def test_the_person_who_blocked_can_still_close_their_account(client):
    """The blocker leaves. Their row is the parent of the block."""
    leaver = _user(client, "+22990110001")
    other = _user(client, "+22990110002", role="business")
    _block(client, leaver, other)

    r = _delete(client, leaver)
    assert r.status_code == 204, r.text
    assert _counts(client) == (1, 0)


def test_the_person_who_was_blocked_can_still_close_their_account(client):
    """The blocked user leaves, which is the direction easiest to forget: the
    row they are referenced by was created by somebody else entirely, and
    nothing on their own account hints that it exists."""
    leaver = _user(client, "+22990110010")
    other = _user(client, "+22990110011", role="business")
    _block(client, other, leaver)

    r = _delete(client, leaver)
    assert r.status_code == 204, r.text
    assert _counts(client) == (1, 0)


def test_blocks_in_both_directions_go_together(client):
    """Two people who blocked each other are two rows, and the leaver is a
    party to both."""
    leaver = _user(client, "+22990110020")
    other = _user(client, "+22990110021", role="business")
    _block(client, leaver, other)
    _block(client, other, leaver)

    r = _delete(client, leaver)
    assert r.status_code == 204, r.text
    assert _counts(client) == (1, 0)


def test_somebody_elses_block_survives_an_unrelated_deletion(client):
    """The cleanup is scoped to the leaver. A block between two other people
    is their business and has to still be there afterwards."""
    leaver = _user(client, "+22990110030")
    a = _user(client, "+22990110031", role="business")
    b = _user(client, "+22990110032")
    _block(client, a, b)

    assert _delete(client, leaver).status_code == 204
    assert _counts(client) == (2, 1)


def test_an_account_with_no_blocks_is_unaffected(client):
    """The control. If this one ever fails, the fixture is broken rather than
    the cleanup, and the three tests above mean nothing until it is fixed."""
    leaver = _user(client, "+22990110040")
    assert _delete(client, leaver).status_code == 204
    assert _counts(client) == (0, 0)

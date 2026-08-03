"""A notification carries where it opens and what it says, not just prose.

The bell used to store one thing per row: an English sentence. That made two
faults unfixable from the client. A click could only ever open a LIST screen,
because the row named no record to open; and the sentence was frozen in the
language it was written in, so a French reader read English. This PR adds two
nullable columns — `link` (the deep-link target, built at emit time where the
recipient's side is known) and `params` (a {"key", ...values} the client
renders the localised body from) — and this file pins the contract they add:

  * a call site that passes link/params has them survive the round trip through
    the model, the service reader, the Pydantic schema and the JSON;
  * a call site that passes NEITHER still writes a valid row, with both fields
    null — which is exactly what an un-migrated type and every pre-migration row
    look like, and what the client's fallback (routeForType + the stored
    English `message`) keys off.

Written at the service+endpoint level rather than through one feature's router:
the columns are shared infrastructure that every notify() call in the codebase
now feeds, so the test that guards them should not depend on any single event's
wiring being present.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db, import_all_models
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.notifications import email as email_module
from app.modules.notifications import service as notif_service
from app.modules.notifications.router import router as notifications_router


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    # notify() reaches for the User row to address the email, so the whole
    # metadata has to exist and not just the notifications tables.
    import_all_models()
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    # The default sender would try to reach a provider; this one records.
    notif_service.email_sender = email_module.LoggingEmailSender()

    app = FastAPI()
    app.include_router(notifications_router, prefix="/notifications")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _user(client, phone, role="influencer"):
    db = client.session_factory()
    try:
        u = User(phone=phone, password_hash="x", country_code="BJ", role=role, is_verified=True)
        db.add(u); db.commit(); db.refresh(u)
        return u.id, {"Authorization": f"Bearer {create_access_token(u.id)}"}
    finally:
        db.close()


def _emit(client, user_id, type, message, *, link=None, params=None):
    """Raise one notification the way every call site does, and commit it —
    notify() leaves the commit to its caller, so the test plays that part."""
    db = client.session_factory()
    try:
        notif_service.notify(db, user_id, type, message, link=link, params=params)
        db.commit()
    finally:
        db.close()


def test_link_and_params_survive_the_round_trip(client):
    """A migrated call site: the deep link and the localisation source come back
    out through the HTTP endpoint exactly as they went in, so the client has
    what it needs to open the record and render the body in French."""
    uid, headers = _user(client, "+22990000501")
    _emit(
        client,
        uid,
        "payment",
        "Escrow released, your payout is on the way",
        link="/contracts/abc-123",
        params={"key": "escrow_released_creator"},
    )

    row = client.get("/notifications/", headers=headers).json()[0]
    assert row["link"] == "/contracts/abc-123"
    assert row["params"] == {"key": "escrow_released_creator"}
    # The English prose is still carried: it is the email body and the client's
    # fallback, and this PR does not remove it.
    assert row["message"] == "Escrow released, your payout is on the way"


def test_params_carry_interpolation_values_not_just_the_key(client):
    """The body template has holes in it — an amount, a currency, a campaign
    title — and the values that fill them ride in params beside the key. A key
    with no values would render "{{payout}} {{currency}}" to a reader."""
    uid, headers = _user(client, "+22990000502")
    _emit(
        client,
        uid,
        "payment",
        "Your dispute was decided: 36000 XOF is on its way to you and 4000 XOF was refunded to the brand.",
        link="/disputes/d-9",
        params={
            "key": "dispute_resolved_creator",
            "payout": 36000,
            "refunded": 4000,
            "currency": "XOF",
        },
    )

    params = client.get("/notifications/", headers=headers).json()[0]["params"]
    assert params["key"] == "dispute_resolved_creator"
    assert params["payout"] == 36000
    assert params["currency"] == "XOF"


def test_a_row_with_no_target_is_valid_and_serialises_as_null(client):
    """An un-migrated type, or any row written before these columns existed,
    passes neither argument. It must still be a valid row — both fields null —
    because that is the state the client's fallback is built for: no link means
    routeForType(type), no params means show the stored English message."""
    uid, headers = _user(client, "+22990000503")
    _emit(client, uid, "security", "A new device signed in to your account")

    row = client.get("/notifications/", headers=headers).json()[0]
    assert row["link"] is None
    assert row["params"] is None
    # The sentence is untouched, so the fallback has something to show.
    assert row["message"] == "A new device signed in to your account"

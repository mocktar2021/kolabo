"""What the contract list says about whether a job is finished.

A contract's own status stops at `signed`. It never becomes "completed",
because completing is not something the document does — the MONEY finishes,
and the escrow is what reaches an ending. So the list row carries the escrow
status, and that is the field the web app's Active/Completed split reads
(web/src/lib/lifecycle.ts).

These cases pin the mapping the split depends on: unfunded is null and not an
ending, held and disputed are live, released and refunded are endings.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.contracts import models as contracts
from app.modules.contracts.router import router as contracts_router
from app.modules.payments import models as payments


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(contracts_router, prefix="/contracts")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _parties(client):
    db = client.session_factory()
    try:
        biz = User(phone="+22990001001", email="22990001001@kolabo.test", password_hash="x", country_code="BJ", role="business", is_verified=True)
        inf = User(phone="+22990001002", email="22990001002@kolabo.test", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add_all([biz, inf]); db.commit(); db.refresh(biz); db.refresh(inf)
        return biz.id, inf.id
    finally:
        db.close()


def _contract(client, biz_id, inf_id, suffix="1", status=None):
    db = client.session_factory()
    try:
        c = contracts.Contract(
            campaign_id=f"camp-{suffix}", proposal_id=f"prop-{suffix}",
            business_user_id=biz_id, influencer_user_id=inf_id, language="fr", body="body",
            rate_amount=10000, rate_currency="XOF", timeline_days=7,
            status=status or contracts.SIGNED,
        )
        db.add(c); db.commit(); db.refresh(c)
        return c.id
    finally:
        db.close()


def _escrow(client, contract_id, biz_id, inf_id, status):
    """An escrow in a given state, written directly.

    Straight to the table rather than through POST /payments/escrow/fund:
    this file mounts only the contracts router, and what it is testing is what
    the contract LIST reports, not how an escrow comes to exist.
    """
    db = client.session_factory()
    try:
        now = payments.utcnow()
        db.add(
            payments.Escrow(
                contract_id=contract_id, campaign_id="camp-1",
                business_user_id=biz_id, influencer_user_id=inf_id,
                amount=10000, currency="XOF", provider="mock", provider_fund_ref="ref",
                status=status, held_at=now, due_release_at=now,
            )
        )
        db.commit()
    finally:
        db.close()


def _rows(client, uid):
    return {r["id"]: r for r in client.get("/contracts/mine", headers=_headers(uid)).json()}


def test_an_unfunded_contract_reports_no_escrow_status(client):
    """Null is not an ending. Nobody has paid in yet, which is a live state —
    filing it as finished would hide a contract still waiting for money."""
    biz, inf = _parties(client)
    cid = _contract(client, biz, inf)
    assert _rows(client, biz)[cid]["escrow_status"] is None
    # And the creator reads the same fact from their side.
    assert _rows(client, inf)[cid]["escrow_status"] is None


@pytest.mark.parametrize("status", [payments.HELD, payments.DISPUTED])
def test_live_money_states_come_back_as_they_are(client, status):
    """Held is a job running; disputed is a job going wrong. Neither is done,
    and a dispute filed under Completed is the row somebody stops chasing."""
    biz, inf = _parties(client)
    cid = _contract(client, biz, inf)
    _escrow(client, cid, biz, inf, status)
    assert _rows(client, biz)[cid]["escrow_status"] == status


@pytest.mark.parametrize("status", [payments.RELEASED, payments.REFUNDED])
def test_settled_money_states_come_back_as_they_are(client, status):
    """The two endings: the creator was paid, or a dispute sent it back."""
    biz, inf = _parties(client)
    cid = _contract(client, biz, inf)
    _escrow(client, cid, biz, inf, status)
    assert _rows(client, biz)[cid]["escrow_status"] == status


def test_each_row_gets_its_own_escrow_status(client):
    """The statuses are resolved in one batched query keyed by contract, so a
    list with several contracts must not smear one escrow's state across the
    others."""
    biz, inf = _parties(client)
    unfunded = _contract(client, biz, inf, suffix="1")
    held = _contract(client, biz, inf, suffix="2")
    done = _contract(client, biz, inf, suffix="3")
    _escrow(client, held, biz, inf, payments.HELD)
    _escrow(client, done, biz, inf, payments.RELEASED)

    rows = _rows(client, biz)
    assert rows[unfunded]["escrow_status"] is None
    assert rows[held]["escrow_status"] == payments.HELD
    assert rows[done]["escrow_status"] == payments.RELEASED
    # The rest of the row is untouched by the addition.
    assert rows[done]["rate_amount"] == 10000


def test_a_cancelled_contract_is_still_listed(client):
    """It is an ending the CONTRACT reached rather than one the money did, and
    the list has to keep carrying it: the Completed shelf is built from both
    kinds, and a cancelled contract that vanished from the list would be a
    record the other party could no longer find."""
    biz, inf = _parties(client)
    cid = _contract(client, biz, inf, status=contracts.CANCELLED)
    row = _rows(client, biz)[cid]
    assert row["status"] == contracts.CANCELLED
    assert row["escrow_status"] is None

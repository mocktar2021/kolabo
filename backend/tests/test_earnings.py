"""Tests for GET /payments/earnings: the creator's side of the money.

The three things this screen must never get wrong, in order of how badly it
would hurt someone who believed it:

  1. Earned is NET of commission. Quoting the gross overstates every payout by
     the fee, and the creator finds out when the money lands short.
  2. Disputed money is not pending money. Pending is a promise with a date on
     it; frozen money has neither, and folding them together tells a creator
     to expect something they may have to argue for.
  3. Currencies are never summed. XOF plus GHS is not a number.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.campaigns import models as campaigns
from app.modules.contracts import models as contracts
from app.modules.payments import models as payments
from app.modules.payments.router import router as payments_router
from app.modules.profiles.models import BusinessProfile


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    from app.core.db import import_all_models
    import_all_models()
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(payments_router, prefix="/payments")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


@pytest.fixture()
def world(client):
    """A brand with a company name and a creator to pay."""
    db = client.session_factory()
    try:
        biz = User(phone="+22990050001", password_hash="x", country_code="BJ",
                   role="business", is_verified=True)
        inf = User(phone="+22990050002", password_hash="x", country_code="BJ",
                   role="influencer", is_verified=True)
        db.add_all([biz, inf]); db.commit(); db.refresh(biz); db.refresh(inf)
        db.add(BusinessProfile(user_id=biz.id, company_name="Maison Kola"))
        db.commit()
        return {"biz": biz.id, "inf": inf.id}
    finally:
        db.close()


def _escrow(client, world, amount, currency, status, title, tag, commission=None):
    """One campaign, one contract, one escrow in the state under test.

    Written straight to the database rather than driven through the funding
    endpoint: what is being tested is how the read model reports states, and
    reaching DISPUTED through the real path would need a signed contract, a
    provider call and a dispute row for every single case.
    """
    db = client.session_factory()
    try:
        camp = campaigns.Campaign(
            business_user_id=world["biz"], title=title, budget_amount=amount,
            budget_currency=currency, deliverables=[], status=campaigns.PUBLISHED,
        )
        db.add(camp); db.commit(); db.refresh(camp)
        contract = contracts.Contract(
            campaign_id=camp.id, proposal_id=f"proposal-{tag}", business_user_id=world["biz"],
            influencer_user_id=world["inf"], language="fr", body="placeholder",
            rate_amount=amount, rate_currency=currency, timeline_days=7,
            deliverables=[], status=contracts.SIGNED,
        )
        db.add(contract); db.commit(); db.refresh(contract)
        now = payments.utcnow()
        escrow = payments.Escrow(
            contract_id=contract.id, campaign_id=camp.id, business_user_id=world["biz"],
            influencer_user_id=world["inf"], amount=amount, currency=currency,
            commission_amount=commission, provider="mock", provider_fund_ref=f"ref-{tag}",
            status=status, held_at=now, due_release_at=now,
            resolved_at=now if status == payments.RELEASED else None,
        )
        db.add(escrow); db.commit(); db.refresh(escrow)
        return escrow.id
    finally:
        db.close()


def _fee(amount):
    """The one definition of the fee, read from settings rather than hardcoded:
    the commission rate is a launch value that will move per country."""
    return amount * settings.commission_bps // 10000


def _get(client, uid, **params):
    return client.get("/payments/earnings", params=params, headers=_headers(uid))


def test_earned_is_net_of_commission(client, world):
    """The gross never reaches the creator's wallet. Quoting it here would
    overstate the payout by the fee and turn every release into a small
    disappointment."""
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "Launch", "a",
            commission=_fee(100000))

    body = _get(client, world["inf"]).json()
    assert body["earned"] == {"XOF": 100000 - _fee(100000)}
    assert body["pending"] == {}
    assert body["disputed"] == {}

    # And the row shows our arithmetic rather than hiding it.
    row = body["payments"][0]
    assert row["gross"] == 100000
    assert row["commission"] == _fee(100000)
    assert row["net"] == 100000 - _fee(100000)
    assert row["gross"] == row["commission"] + row["net"]


def test_pending_and_disputed_are_separate(client, world):
    """Frozen money is not money on its way. A creator planning around
    "pending" must not be planning around a dispute they might lose."""
    _escrow(client, world, 100000, "XOF", payments.HELD, "On its way", "a")
    _escrow(client, world, 60000, "XOF", payments.DISPUTED, "Frozen", "b")

    body = _get(client, world["inf"]).json()
    assert body["pending"] == {"XOF": 100000 - _fee(100000)}
    assert body["disputed"] == {"XOF": 60000 - _fee(60000)}
    # Neither leaks into the other, and neither is counted as earned.
    assert body["earned"] == {}
    assert body["pending"]["XOF"] != body["pending"]["XOF"] + body["disputed"]["XOF"]


def test_two_currencies_stay_separate(client, world):
    """XOF plus GHS is not a number. One total across two markets would be
    meaningless on the screen a creator trusts most."""
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "Benin", "a",
            commission=_fee(100000))
    _escrow(client, world, 5000, "GHS", payments.RELEASED, "Ghana", "b",
            commission=_fee(5000))
    _escrow(client, world, 20000, "GHS", payments.HELD, "Ghana next", "c")

    body = _get(client, world["inf"]).json()
    assert body["earned"] == {
        "XOF": 100000 - _fee(100000),
        "GHS": 5000 - _fee(5000),
    }
    assert body["pending"] == {"GHS": 20000 - _fee(20000)}
    assert "XOF" not in body["pending"]


def test_refunded_money_is_not_earnings_of_any_kind(client, world):
    """It went back to the buyer and never reached the creator, so it is not
    earned, not pending and not frozen."""
    _escrow(client, world, 100000, "XOF", payments.REFUNDED, "Called off", "a")
    body = _get(client, world["inf"]).json()
    assert body["earned"] == body["pending"] == body["disputed"] == {}
    assert body["payments"] == []


def test_a_business_calling_it_sees_an_empty_result(client, world):
    """Creator side only, deliberately. What a buyer would want here is SPEND
    — the opposite sign, commission not deducted, refunds included — and
    answering both from one endpoint would make every field mean two things.
    Buyer-side spend is out of scope and wants its own endpoint."""
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "Launch", "a",
            commission=_fee(100000))

    body = _get(client, world["biz"]).json()
    assert body["earned"] == {}
    assert body["pending"] == {}
    assert body["disputed"] == {}
    assert body["payments"] == []


def test_the_list_carries_the_counterparty_name_and_the_campaign(client, world):
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "Launch push", "a",
            commission=_fee(100000))
    row = _get(client, world["inf"]).json()["payments"][0]
    assert row["counterparty_name"] == "Maison Kola"
    assert row["campaign_title"] == "Launch push"
    assert row["status"] == payments.RELEASED
    assert row["date"] is not None
    assert row["contract_id"]


def test_a_buyer_with_no_profile_leaves_the_name_null(client, world):
    """Null rather than a phone number. The users table has nothing else to
    offer, and a phone is never handed to the other side of a deal."""
    db = client.session_factory()
    try:
        db.query(BusinessProfile).filter(BusinessProfile.user_id == world["biz"]).delete()
        db.commit()
    finally:
        db.close()
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "Launch", "a",
            commission=_fee(100000))
    assert _get(client, world["inf"]).json()["payments"][0]["counterparty_name"] is None


def test_a_dispute_split_credits_only_what_actually_moved(client, world):
    """After a split the escrow is RELEASED but part of it went back to the
    buyer. Reading escrow.amount there would credit the creator with money
    that was refunded away from them — wrong, and wrong in their favour, so
    they would only find out when the payout landed short."""
    escrow_id = _escrow(client, world, 100000, "XOF", payments.RELEASED, "Half done", "a",
                        commission=_fee(60000))
    db = client.session_factory()
    try:
        now = payments.utcnow()
        db.add(payments.Dispute(
            escrow_id=escrow_id, opened_by_user_id=world["biz"], reason="late",
            statement="two of three landed", status=payments.DISPUTE_RESOLVED,
            respond_by=now, resolved_at=now, released_amount=60000, refunded_amount=40000,
        ))
        db.commit()
    finally:
        db.close()

    body = _get(client, world["inf"]).json()
    assert body["earned"] == {"XOF": 60000 - _fee(60000)}
    assert body["payments"][0]["gross"] == 60000


def test_the_year_filter_narrows_totals_and_list_together(client, world):
    """Somebody who filtered to a year wants that year's totals, not all-time
    totals sitting beside a filtered list."""
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "This year", "a",
            commission=_fee(100000))
    body = _get(client, world["inf"], year=1999).json()
    assert body["earned"] == {}
    assert body["payments"] == []

    this_year = payments.utcnow().year
    body = _get(client, world["inf"], year=this_year).json()
    assert body["earned"] == {"XOF": 100000 - _fee(100000)}
    assert len(body["payments"]) == 1


def test_nothing_earned_yet_is_an_honest_empty_answer(client, world):
    body = _get(client, world["inf"]).json()
    assert body == {"earned": {}, "pending": {}, "disputed": {}, "payments": []}


def test_earnings_requires_auth(client):
    assert client.get("/payments/earnings").status_code == 401

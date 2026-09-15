"""Tests for GET /payments/earnings: the creator's side of the money.

The three things this screen must never get wrong, in order of how badly it
would hurt someone who believed it:

  1. Earned is NET of commission. Quoting the gross overstates every payout by
     the fee, and the creator finds out when the money lands short.
  2. Disputed money is not pending money. Pending is a promise with a date on
     it; frozen money has neither, and folding them together tells a creator
     to expect something they may have to argue for.
  3. Currencies are never summed. XOF plus GHS is not a number.

And one rule that cuts across all three: A FILTER NARROWS THE TOTALS AND THE
LIST TOGETHER. A filtered statement sitting under an all-time total is how a
creator adds up the rows, gets a different number, and stops believing the
screen.
"""
from datetime import datetime

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
        biz = User(phone="+22990050001", email="22990050001@kolabo.test", password_hash="x", country_code="BJ",
                   role="business", is_verified=True)
        inf = User(phone="+22990050002", email="22990050002@kolabo.test", password_hash="x", country_code="BJ",
                   role="influencer", is_verified=True)
        db.add_all([biz, inf]); db.commit(); db.refresh(biz); db.refresh(inf)
        db.add(BusinessProfile(user_id=biz.id, company_name="Maison Kola"))
        db.commit()
        return {"biz": biz.id, "inf": inf.id}
    finally:
        db.close()


def _other_buyer(client, phone="+22990050003", company="Autre Marque"):
    """A second brand, so "filter by counterparty" has two to tell apart."""
    db = client.session_factory()
    try:
        biz = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x", country_code="BJ",
                   role="business", is_verified=True)
        db.add(biz); db.commit(); db.refresh(biz)
        db.add(BusinessProfile(user_id=biz.id, company_name=company))
        db.commit()
        return biz.id
    finally:
        db.close()


def _escrow(client, world, amount, currency, status, title, tag, commission=None,
            business_user_id=None, when=None):
    """One campaign, one contract, one escrow in the state under test.

    Written straight to the database rather than driven through the funding
    endpoint: what is being tested is how the read model reports states, and
    reaching DISPUTED through the real path would need a signed contract, a
    provider call and a dispute row for every single case.

    business_user_id and when default to the fixture's brand and to now, so
    every test written before the filters existed reads unchanged; the
    overrides exist for the filter tests, which need two buyers and dates that
    are not today.
    """
    buyer = business_user_id or world["biz"]
    db = client.session_factory()
    try:
        camp = campaigns.Campaign(
            business_user_id=buyer, title=title, budget_amount=amount,
            budget_currency=currency, deliverables=[], status=campaigns.PUBLISHED,
        )
        db.add(camp); db.commit(); db.refresh(camp)
        contract = contracts.Contract(
            campaign_id=camp.id, proposal_id=f"proposal-{tag}", business_user_id=buyer,
            influencer_user_id=world["inf"], language="fr", body="placeholder",
            rate_amount=amount, rate_currency=currency, timeline_days=7,
            deliverables=[], status=contracts.SIGNED,
        )
        db.add(contract); db.commit(); db.refresh(contract)
        moment = when or payments.utcnow()
        escrow = payments.Escrow(
            contract_id=contract.id, campaign_id=camp.id, business_user_id=buyer,
            influencer_user_id=world["inf"], amount=amount, currency=currency,
            commission_amount=commission, provider="mock", provider_fund_ref=f"ref-{tag}",
            status=status, held_at=moment, due_release_at=moment,
            resolved_at=moment if status == payments.RELEASED else None,
        )
        db.add(escrow); db.commit(); db.refresh(escrow)
        return escrow.id
    finally:
        db.close()


def _campaign_of(client, escrow_id):
    db = client.session_factory()
    try:
        return (
            db.query(payments.Escrow)
            .filter(payments.Escrow.id == escrow_id)
            .first()
            .campaign_id
        )
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
    """Creator side only, deliberately. What a buyer wants here is SPEND — the
    opposite sign, commission not deducted, refunds included — and answering
    both from one endpoint would make every field mean two things. Buyer-side
    spend has its own endpoint, GET /payments/spend."""
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


# --- filters ---------------------------------------------------------------
#
# Every one of these asserts the totals AND the list, on purpose. Narrowing
# one without the other is the specific bug these tests exist to catch: it
# does not throw, it does not log, it just quietly shows a creator a number
# that does not match the rows underneath it.


def _march(day=10):
    return datetime(2026, 3, day, 12, 0)


def test_a_date_range_narrows_totals_and_list_together(client, world):
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "March", "a",
            commission=_fee(100000), when=_march())
    _escrow(client, world, 50000, "XOF", payments.RELEASED, "July", "b",
            commission=_fee(50000), when=datetime(2026, 7, 1, 12, 0))

    body = _get(client, world["inf"],
                from_date="2026-03-01", to_date="2026-03-31").json()
    assert body["earned"] == {"XOF": 100000 - _fee(100000)}
    assert [r["campaign_title"] for r in body["payments"]] == ["March"]
    # The total is exactly the sum of the rows shown. That equality IS the
    # feature: a creator checking our arithmetic must be able to.
    assert body["earned"]["XOF"] == sum(r["net"] for r in body["payments"])


def test_both_ends_of_the_range_are_inclusive(client, world):
    """from_date and to_date name days a human picked off a calendar. A range
    whose last day is not in it is the off-by-one nobody reports and everybody
    works around."""
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "On the boundary", "a",
            commission=_fee(100000), when=_march(10))

    body = _get(client, world["inf"],
                from_date="2026-03-10", to_date="2026-03-10").json()
    assert len(body["payments"]) == 1
    assert body["earned"] == {"XOF": 100000 - _fee(100000)}


def test_an_open_ended_range_stays_open_at_that_end(client, world):
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "March", "a",
            commission=_fee(100000), when=_march())
    _escrow(client, world, 50000, "XOF", payments.RELEASED, "July", "b",
            commission=_fee(50000), when=datetime(2026, 7, 1, 12, 0))

    body = _get(client, world["inf"], from_date="2026-06-01").json()
    assert [r["campaign_title"] for r in body["payments"]] == ["July"]
    body = _get(client, world["inf"], to_date="2026-06-01").json()
    assert [r["campaign_title"] for r in body["payments"]] == ["March"]


def test_the_campaign_filter_narrows_totals_and_list_together(client, world):
    kept = _escrow(client, world, 100000, "XOF", payments.RELEASED, "Wanted", "a",
                   commission=_fee(100000))
    _escrow(client, world, 50000, "XOF", payments.RELEASED, "Other", "b",
            commission=_fee(50000))

    body = _get(client, world["inf"], campaign_id=_campaign_of(client, kept)).json()
    assert body["earned"] == {"XOF": 100000 - _fee(100000)}
    assert [r["campaign_title"] for r in body["payments"]] == ["Wanted"]


def test_the_counterparty_filter_narrows_totals_and_list_together(client, world):
    """The counterparty on a creator's row is the buyer. Filtering to one
    brand is how a creator answers "what has this client paid me"."""
    other = _other_buyer(client)
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "Maison Kola job", "a",
            commission=_fee(100000))
    _escrow(client, world, 50000, "XOF", payments.RELEASED, "Autre Marque job", "b",
            commission=_fee(50000), business_user_id=other)

    body = _get(client, world["inf"], counterparty_id=other).json()
    assert body["earned"] == {"XOF": 50000 - _fee(50000)}
    assert [r["counterparty_name"] for r in body["payments"]] == ["Autre Marque"]


def test_an_empty_range_returns_zeros_not_an_error(client, world):
    """A window with nothing in it is a question with the answer zero. An
    inverted one — "between the 5th and the 1st" — is the same: it matches
    nothing, and answering honestly beats a 400 nobody's client expects."""
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "March", "a",
            commission=_fee(100000), when=_march())

    r = _get(client, world["inf"], from_date="2025-01-01", to_date="2025-01-31")
    assert r.status_code == 200
    assert r.json() == {"earned": {}, "pending": {}, "disputed": {}, "payments": []}

    inverted = _get(client, world["inf"], from_date="2026-03-31", to_date="2026-03-01")
    assert inverted.status_code == 200
    assert inverted.json()["payments"] == []


def test_year_and_a_range_intersect_rather_than_one_winning(client, world):
    """A caller sending both means the overlap, and where the two genuinely
    contradict, zero rows is the visibly-empty answer that sends them to fix
    the request — picking a winner would show a confident wrong number."""
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "March 2026", "a",
            commission=_fee(100000), when=_march())

    body = _get(client, world["inf"], year=2026,
                from_date="2026-03-01", to_date="2026-03-31").json()
    assert len(body["payments"]) == 1

    contradiction = _get(client, world["inf"], year=2025,
                         from_date="2026-03-01", to_date="2026-03-31").json()
    assert contradiction["earned"] == {}
    assert contradiction["payments"] == []


def test_filters_combine_as_an_and(client, world):
    other = _other_buyer(client, phone="+22990050004", company="Troisième")
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "Right brand, right month", "a",
            commission=_fee(100000), when=_march(), business_user_id=other)
    _escrow(client, world, 50000, "XOF", payments.RELEASED, "Right brand, wrong month", "b",
            commission=_fee(50000), when=datetime(2026, 7, 1, 12, 0), business_user_id=other)

    body = _get(client, world["inf"], counterparty_id=other,
                from_date="2026-03-01", to_date="2026-03-31").json()
    assert [r["campaign_title"] for r in body["payments"]] == ["Right brand, right month"]
    assert body["earned"] == {"XOF": 100000 - _fee(100000)}


def test_an_unparseable_date_is_a_422(client, world):
    """A malformed date is a client bug rather than a rule the user broke, so
    FastAPI's field error is the right answer and needs no sentence of ours."""
    assert _get(client, world["inf"], from_date="last-tuesday").status_code == 422

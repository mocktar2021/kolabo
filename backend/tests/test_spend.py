"""Tests for GET /payments/spend: the buyer's side of the money.

The things this screen must never get wrong, in order of how badly it would
hurt the person reading it:

  1. Spent is the GROSS the buyer paid. The platform's cut comes out of the
     creator's release, not the brand's payment; quoting a net figure here
     would tell a brand it was charged less than its bank statement says.
  2. Refunded money is refunded, not spent. It came back, and a screen that
     counts it as spend overstates a budget that has already been restored.
  3. A dispute split is two figures, not one. resolution.py marks the escrow
     RELEASED the moment any money reaches the creator while escrow.amount
     still holds the full original sum — using it would overstate spend by
     the refund and lose the refund at the same time.
  4. Currencies are never summed. XOF plus GHS is not a number.
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
from app.modules.profiles.models import InfluencerProfile


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
    """A brand that buys and a creator with a name to show on the statement."""
    db = client.session_factory()
    try:
        biz = User(phone="+22990060001", password_hash="x", country_code="BJ",
                   role="business", is_verified=True)
        inf = User(phone="+22990060002", password_hash="x", country_code="BJ",
                   role="influencer", is_verified=True)
        db.add_all([biz, inf]); db.commit(); db.refresh(biz); db.refresh(inf)
        db.add(InfluencerProfile(user_id=inf.id, display_name="Ama K.", rate_card={}))
        db.commit()
        return {"biz": biz.id, "inf": inf.id}
    finally:
        db.close()


def _other_creator(client, phone="+22990060003", name="Kofi B."):
    """A second creator, so "filter by counterparty" has two to tell apart."""
    db = client.session_factory()
    try:
        inf = User(phone=phone, password_hash="x", country_code="BJ",
                   role="influencer", is_verified=True)
        db.add(inf); db.commit(); db.refresh(inf)
        db.add(InfluencerProfile(user_id=inf.id, display_name=name, rate_card={}))
        db.commit()
        return inf.id
    finally:
        db.close()


def _escrow(client, world, amount, currency, status, title, tag, commission=None,
            influencer_user_id=None, when=None):
    """One campaign, one contract, one escrow in the state under test.

    Written straight to the database rather than driven through the funding
    endpoint, exactly as test_earnings does it: what is under test is how the
    read model reports states, and reaching DISPUTED through the real path
    would need a signed contract, a provider call and a dispute row for every
    single case.
    """
    creator = influencer_user_id or world["inf"]
    db = client.session_factory()
    try:
        camp = campaigns.Campaign(
            business_user_id=world["biz"], title=title, budget_amount=amount,
            budget_currency=currency, deliverables=[], status=campaigns.PUBLISHED,
        )
        db.add(camp); db.commit(); db.refresh(camp)
        contract = contracts.Contract(
            campaign_id=camp.id, proposal_id=f"proposal-{tag}", business_user_id=world["biz"],
            influencer_user_id=creator, language="fr", body="placeholder",
            rate_amount=amount, rate_currency=currency, timeline_days=7,
            deliverables=[], status=contracts.SIGNED,
        )
        db.add(contract); db.commit(); db.refresh(contract)
        moment = when or payments.utcnow()
        escrow = payments.Escrow(
            contract_id=contract.id, campaign_id=camp.id, business_user_id=world["biz"],
            influencer_user_id=creator, amount=amount, currency=currency,
            commission_amount=commission, provider="mock", provider_fund_ref=f"ref-{tag}",
            status=status, held_at=moment, due_release_at=moment,
            resolved_at=moment if status in (payments.RELEASED, payments.REFUNDED) else None,
        )
        db.add(escrow); db.commit(); db.refresh(escrow)
        return escrow.id
    finally:
        db.close()


def _split(client, world, escrow_id, released, refunded):
    """The dispute row that records where a split actually sent the money."""
    db = client.session_factory()
    try:
        now = payments.utcnow()
        db.add(payments.Dispute(
            escrow_id=escrow_id, opened_by_user_id=world["biz"], reason="late",
            statement="two of three landed", status=payments.DISPUTE_RESOLVED,
            respond_by=now, resolved_at=now,
            released_amount=released, refunded_amount=refunded,
        ))
        db.commit()
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
    """The commission, read from settings. Present only so a test can assert
    that spend is NOT reduced by it."""
    return amount * settings.commission_bps // 10000


def _get(client, uid, **params):
    return client.get("/payments/spend", params=params, headers=_headers(uid))


def test_spent_is_the_gross_the_buyer_paid_not_net_of_commission(client, world):
    """The platform's cut comes off the creator's release, not the brand's
    payment. A brand that funded 100000 paid 100000, whatever the creator
    received, and its accounting has to agree with its bank statement."""
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "Launch", "a",
            commission=_fee(100000))

    body = _get(client, world["biz"]).json()
    assert body["spent"] == {"XOF": 100000}
    assert body["spent"] != {"XOF": 100000 - _fee(100000)}
    assert body["pending"] == body["disputed"] == body["refunded"] == {}

    row = body["payments"][0]
    assert row["amount"] == 100000
    assert row["refunded_amount"] == 0
    # No commission or net columns at all: a buyer was not charged a fee, and
    # a column implying one would invite a support ticket.
    assert "commission" not in row
    assert "net" not in row


def test_refunded_money_is_refunded_and_not_spent(client, world):
    """It came back. Counting it as spend would overstate a budget that has
    already been restored."""
    _escrow(client, world, 100000, "XOF", payments.REFUNDED, "Called off", "a")

    body = _get(client, world["biz"]).json()
    assert body["refunded"] == {"XOF": 100000}
    assert body["spent"] == {}
    # And unlike the creator's screen, it is a visible line rather than a row
    # that never existed: the buyer paid it and got it back, and both facts
    # have to be on the statement or the arithmetic does not close.
    assert body["payments"][0]["status"] == payments.REFUNDED
    assert body["payments"][0]["amount"] == 100000


def test_a_split_counts_the_released_part_as_spent_and_the_rest_as_refunded(client, world):
    """resolution.py marks the escrow RELEASED the moment any money reaches
    the creator, while escrow.amount still holds the full original sum.
    Reading escrow.amount here would overstate spend by the refund AND lose
    the refund entirely — one mistake misreporting both figures."""
    escrow_id = _escrow(client, world, 100000, "XOF", payments.RELEASED, "Half done", "a",
                        commission=_fee(60000))
    _split(client, world, escrow_id, released=60000, refunded=40000)

    body = _get(client, world["biz"]).json()
    assert body["spent"] == {"XOF": 60000}
    assert body["refunded"] == {"XOF": 40000}
    # The two halves add back up to what the buyer actually funded.
    assert body["spent"]["XOF"] + body["refunded"]["XOF"] == 100000

    # And the line traces it, so the statement and the totals agree.
    row = body["payments"][0]
    assert row["amount"] == 60000
    assert row["refunded_amount"] == 40000


def test_a_fully_released_escrow_is_not_read_as_a_split(client, world):
    """The ordinary case has no dispute row, and must not lose anything to the
    lookup that exists for the split one."""
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "Clean", "a",
            commission=_fee(100000))
    body = _get(client, world["biz"]).json()
    assert body["spent"] == {"XOF": 100000}
    assert body["refunded"] == {}


def test_pending_and_disputed_are_separate(client, world):
    """Pending is money the buyer expects to lose; disputed is money they may
    get back. A budget built on the two added together is a budget built on a
    number that means neither."""
    _escrow(client, world, 100000, "XOF", payments.HELD, "Committed", "a")
    _escrow(client, world, 60000, "XOF", payments.DISPUTED, "Frozen", "b")

    body = _get(client, world["biz"]).json()
    assert body["pending"] == {"XOF": 100000}
    assert body["disputed"] == {"XOF": 60000}
    assert body["spent"] == {}


def test_currencies_stay_separate(client, world):
    """XOF plus GHS is not a number. A brand running in two markets has two
    budgets, not one meaningless total."""
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "Benin", "a",
            commission=_fee(100000))
    _escrow(client, world, 5000, "GHS", payments.RELEASED, "Ghana", "b",
            commission=_fee(5000))
    _escrow(client, world, 20000, "GHS", payments.HELD, "Ghana next", "c")
    _escrow(client, world, 7000, "GHS", payments.REFUNDED, "Ghana off", "d")

    body = _get(client, world["biz"]).json()
    assert body["spent"] == {"XOF": 100000, "GHS": 5000}
    assert body["pending"] == {"GHS": 20000}
    assert body["refunded"] == {"GHS": 7000}
    assert "XOF" not in body["pending"]
    assert "XOF" not in body["refunded"]


def test_a_creator_calling_it_sees_empty_figures(client, world):
    """Buyer side only, the mirror of a business getting empty earnings. A
    creator is on no escrow as the buyer, and there is no version of "what
    have I spent" that means anything to somebody who has never bought."""
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "Launch", "a",
            commission=_fee(100000))

    body = _get(client, world["inf"]).json()
    assert body == {"spent": {}, "pending": {}, "disputed": {}, "refunded": {}, "payments": []}


def test_the_list_names_the_creator_and_the_campaign(client, world):
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "Launch push", "a",
            commission=_fee(100000))
    row = _get(client, world["biz"]).json()["payments"][0]
    assert row["counterparty_name"] == "Ama K."
    assert row["campaign_title"] == "Launch push"
    assert row["currency"] == "XOF"
    assert row["status"] == payments.RELEASED
    assert row["date"] is not None
    assert row["contract_id"]
    # Never the creator's phone number, here or anywhere else.
    assert "+22990060002" not in str(row)


def test_a_creator_with_no_profile_leaves_the_name_null(client, world):
    """Null rather than a phone number: the users table has nothing else to
    offer, and a phone is never handed to the other side of a deal."""
    db = client.session_factory()
    try:
        db.query(InfluencerProfile).filter(
            InfluencerProfile.user_id == world["inf"]
        ).delete()
        db.commit()
    finally:
        db.close()
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "Launch", "a",
            commission=_fee(100000))
    assert _get(client, world["biz"]).json()["payments"][0]["counterparty_name"] is None


def test_nothing_spent_yet_is_an_honest_empty_answer(client, world):
    body = _get(client, world["biz"]).json()
    assert body == {"spent": {}, "pending": {}, "disputed": {}, "refunded": {}, "payments": []}


def test_spend_requires_auth(client):
    assert client.get("/payments/spend").status_code == 401


# --- filters ---------------------------------------------------------------
#
# The same StatementFilter the creator's screen uses, so these tests are
# about the WIRING: that spend passes the filter through, and that its
# counterparty is the creator rather than the buyer. The semantics of the
# filter itself are pinned down in test_earnings.


def test_a_date_range_narrows_spend_totals_and_list_together(client, world):
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "March", "a",
            commission=_fee(100000), when=datetime(2026, 3, 10, 12, 0))
    _escrow(client, world, 50000, "XOF", payments.RELEASED, "July", "b",
            commission=_fee(50000), when=datetime(2026, 7, 1, 12, 0))

    body = _get(client, world["biz"],
                from_date="2026-03-01", to_date="2026-03-31").json()
    assert body["spent"] == {"XOF": 100000}
    assert [r["campaign_title"] for r in body["payments"]] == ["March"]
    assert body["spent"]["XOF"] == sum(r["amount"] for r in body["payments"])


def test_the_campaign_filter_narrows_spend(client, world):
    kept = _escrow(client, world, 100000, "XOF", payments.RELEASED, "Wanted", "a",
                   commission=_fee(100000))
    _escrow(client, world, 50000, "XOF", payments.RELEASED, "Other", "b",
            commission=_fee(50000))

    body = _get(client, world["biz"], campaign_id=_campaign_of(client, kept)).json()
    assert body["spent"] == {"XOF": 100000}
    assert [r["campaign_title"] for r in body["payments"]] == ["Wanted"]


def test_the_counterparty_on_this_side_is_the_creator(client, world):
    """counterparty_id means "the other party", which is the creator here and
    the buyer on the earnings screen. Filtering to one creator is how a brand
    answers "what have I paid this person"."""
    other = _other_creator(client)
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "Ama's job", "a",
            commission=_fee(100000))
    _escrow(client, world, 50000, "XOF", payments.RELEASED, "Kofi's job", "b",
            commission=_fee(50000), influencer_user_id=other)

    body = _get(client, world["biz"], counterparty_id=other).json()
    assert body["spent"] == {"XOF": 50000}
    assert [r["counterparty_name"] for r in body["payments"]] == ["Kofi B."]


def test_an_empty_range_returns_zeros_not_an_error(client, world):
    _escrow(client, world, 100000, "XOF", payments.RELEASED, "March", "a",
            commission=_fee(100000), when=datetime(2026, 3, 10, 12, 0))
    r = _get(client, world["biz"], from_date="2025-01-01", to_date="2025-01-31")
    assert r.status_code == 200
    assert r.json() == {"spent": {}, "pending": {}, "disputed": {}, "refunded": {}, "payments": []}

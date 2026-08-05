"""Tests for Epic G (KOL-7): escrow funding, release, and the referral hook.

Disputes have their own two files — test_disputes.py for raising and answering
one, test_dispute_resolution.py for the admin's split and the queue. What is
left here is the ordinary money path plus the one dispute fact that belongs to
it: a frozen escrow cannot be released by the business.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.rewards import REFERRAL_CREDIT
from app.core.security import create_access_token
from app.modules.auth.models import ReferralCredit, User
from app.modules.contracts import models as contracts
from app.modules.deliverables import models as deliverables
from app.modules.payments import provider as provider_module
from app.modules.payments import service as pay_service
from app.modules.payments import models as pay_models
from app.modules.payments.router import router as payments_router


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    # Fresh mock provider per test so we can inspect collections and payouts.
    pay_service.payment_provider = provider_module.MockProvider()

    app = FastAPI()
    app.include_router(payments_router, prefix="/payments")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


ADMIN = {"X-Admin-Id": "admin-1"}

# Raising a dispute now costs a reason and a statement. The cases below only
# need A dispute, not a particular one; what the payload is FOR is tested in
# test_disputes.py.
DISPUTE_BODY = {
    "reason": "not_delivered",
    "statement": "The deliverable never arrived and the agreed date has passed.",
}


def _dispute(client, escrow_id, user_id):
    return client.post(
        f"/payments/escrow/{escrow_id}/dispute", json=DISPUTE_BODY, headers=_headers(user_id)
    )


def _signed_contract(client, signed=True, amount=10000):
    db = client.session_factory()
    try:
        biz = User(phone="+22990000001", password_hash="x", country_code="BJ", role="business", is_verified=True)
        inf = User(phone="+22990000002", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add_all([biz, inf]); db.commit(); db.refresh(biz); db.refresh(inf)
        c = contracts.Contract(
            campaign_id="camp-1", proposal_id="prop-1", business_user_id=biz.id, influencer_user_id=inf.id,
            language="fr", body="body", rate_amount=amount, rate_currency="XOF", timeline_days=7,
            status=contracts.SIGNED if signed else contracts.PENDING,
        )
        db.add(c); db.commit(); db.refresh(c)
        return biz.id, inf.id, c.id
    finally:
        db.close()


def _another_signed_contract(client, business_user_id, influencer_user_id, amount=10000):
    """A second signed contract between the same two parties."""
    db = client.session_factory()
    try:
        c = contracts.Contract(
            campaign_id="camp-2", proposal_id="prop-2", business_user_id=business_user_id,
            influencer_user_id=influencer_user_id, language="fr", body="body",
            rate_amount=amount, rate_currency="XOF", timeline_days=7, status=contracts.SIGNED,
        )
        db.add(c); db.commit(); db.refresh(c)
        return c.id
    finally:
        db.close()


def _referred_by(client, user_id, country="BJ", phone="+22990000009"):
    """Give an existing user a referrer, as a signup with a code would have."""
    db = client.session_factory()
    try:
        referrer = User(phone=phone, password_hash="x", country_code=country, role="influencer", is_verified=True)
        db.add(referrer); db.commit(); db.refresh(referrer)
        user = db.query(User).filter(User.id == user_id).first()
        user.referred_by_user_id = referrer.id
        db.commit()
        return referrer.id
    finally:
        db.close()


def _credits(client):
    db = client.session_factory()
    try:
        return db.query(ReferralCredit).all()
    finally:
        db.close()


def _fund(client, biz, contract_id):
    return client.post("/payments/escrow/fund", json={"contract_id": contract_id}, headers=_headers(biz)).json()


def _submitted(client, contract_id, creator_id):
    """Work handed in and still awaiting the brand's answer.

    THE SWEEP NEEDS ONE TO EXIST. Auto-release used to be a pure function of
    the funding date, so an escrow nobody had delivered against paid itself
    out once the deadline passed. It now only takes escrows with an OPEN
    submission — see payments.service.run_due_auto_releases — which means the
    timeout path in these tests has to have something submitted against it,
    exactly as a real one would.

    Written straight to the table rather than through POST /deliverables: this
    file mounts only the payments router, and what it is testing is the sweep
    and the referral hook, not the submission API. test_deliverables.py owns
    that end.
    """
    db = client.session_factory()
    try:
        db.add(
            deliverables.DeliverableSubmission(
                contract_id=contract_id,
                submitted_by_user_id=creator_id,
                link_url="https://instagram.com/p/abc123",
                status=deliverables.SUBMITTED,
            )
        )
        db.commit()
    finally:
        db.close()


def _age_release_deadline(client, escrow_id):
    db = client.session_factory()
    try:
        e = db.query(pay_models.Escrow).filter(pay_models.Escrow.id == escrow_id).first()
        e.due_release_at = pay_models.utcnow().replace(year=2020)
        db.commit()
    finally:
        db.close()


def test_fund_requires_signed_contract(client):
    biz, inf, cid = _signed_contract(client, signed=False)
    r = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz))
    assert r.status_code == 400


def test_fund_holds_money_and_calls_provider(client):
    biz, inf, cid = _signed_contract(client)
    r = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz))
    assert r.status_code == 201
    assert r.json()["status"] == "held"
    assert len(pay_service.payment_provider.collections) == 1
    assert pay_service.payment_provider.collections[0]["amount"] == 10000


def test_fund_requires_ownership_and_no_double_fund(client):
    biz, inf, cid = _signed_contract(client)
    assert client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(inf)).status_code == 403
    assert client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).status_code == 201
    assert client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).status_code == 409


def test_release_deducts_commission(client):
    biz, inf, cid = _signed_contract(client, amount=10000)
    escrow = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).json()
    r = client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "released"
    # 15 percent of 10000 is 1500 commission; payout is 8500.
    assert body["commission_amount"] == 1500
    assert pay_service.payment_provider.payouts[0]["amount"] == 8500


def test_only_business_can_release(client):
    biz, inf, cid = _signed_contract(client)
    escrow = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).json()
    assert client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(inf)).status_code == 403


def test_auto_release_after_timeout(client):
    """Delivered work the brand never got round to reviewing still pays.

    The creator did their part; a brand that clicks nothing must not be able
    to hold a payout indefinitely. That is what the timeout is FOR, and it is
    now the only thing it does — see the test below for the case it used to
    get wrong.
    """
    biz, inf, cid = _signed_contract(client)
    escrow = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).json()
    _submitted(client, cid, inf)
    _age_release_deadline(client, escrow["id"])
    r = client.post("/payments/escrow/auto-release", headers=ADMIN)
    assert r.json()["released"] == 1
    assert client.get(f"/payments/escrow/{escrow['id']}", headers=_headers(biz)).json()["status"] == "released"


def test_nothing_submitted_never_auto_releases(client):
    """The hole the deliverables work closed, guarded from the money side.

    due_release_at was stamped at FUNDING, and the sweep asked nothing about
    delivery — so a brand that funded a contract and then heard nothing from
    the creator had its money paid out to that creator seven days later. The
    escrow now waits, and the brand's recourse is the dispute path, which is
    where a claim on frozen money belongs.
    """
    biz, inf, cid = _signed_contract(client)
    escrow = _fund(client, biz, cid)
    _age_release_deadline(client, escrow["id"])
    assert client.post("/payments/escrow/auto-release", headers=ADMIN).json()["released"] == 0
    assert client.get(f"/payments/escrow/{escrow['id']}", headers=_headers(biz)).json()["status"] == "held"


def test_a_frozen_escrow_cannot_be_released_by_the_business(client):
    """Freezing it is what raising a dispute is for. The split that ends it is
    tested in test_dispute_resolution.py."""
    biz, inf, cid = _signed_contract(client, amount=20000)
    escrow = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).json()
    eid = escrow["id"]
    r = _dispute(client, eid, inf)
    # The response is now the DISPUTE, which starts in its response window;
    # the frozen escrow rides along on it.
    assert r.status_code == 201
    assert r.json()["status"] == "awaiting_response"
    assert r.json()["escrow"]["status"] == "disputed"
    assert client.post(f"/payments/escrow/{eid}/release", headers=_headers(biz)).status_code == 400
    # And no auto release can slip past the freeze either: the sweep only
    # looks at HELD escrows.
    #
    # The submission is here so that the freeze is the only thing left
    # stopping it. Without one the sweep would skip this escrow anyway, for
    # having nothing delivered against it, and the test would pass while
    # proving nothing about disputes at all.
    _submitted(client, cid, inf)
    _age_release_deadline(client, eid)
    assert client.post("/payments/escrow/auto-release", headers=ADMIN).json()["released"] == 0


def test_fund_requires_auth(client):
    biz, inf, cid = _signed_contract(client)
    assert client.post("/payments/escrow/fund", json={"contract_id": cid}).status_code == 401


def test_escrow_by_contract_lookup(client):
    biz, inf, cid = _signed_contract(client)
    escrow = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).json()
    found = client.get(f"/payments/escrow/by-contract/{cid}", headers=_headers(biz))
    assert found.status_code == 200
    assert found.json()["id"] == escrow["id"]
    # The influencer, a party, can also find it.
    assert client.get(f"/payments/escrow/by-contract/{cid}", headers=_headers(inf)).status_code == 200


def test_escrow_by_contract_404_when_unfunded(client):
    biz, inf, cid = _signed_contract(client)
    assert client.get(f"/payments/escrow/by-contract/{cid}", headers=_headers(biz)).status_code == 404


def test_release_credits_both_sides_of_a_referral(client):
    """The reward lands on the first COMPLETED ORDER, not at signup: a cleared
    escrow is the thing nobody can manufacture for free."""
    biz, inf, cid = _signed_contract(client)
    referrer_id = _referred_by(client, inf)
    escrow = _fund(client, biz, cid)
    assert client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz)).status_code == 200

    by_kind = {c.kind: c for c in _credits(client)}
    assert set(by_kind) == {"referee", "referrer"}
    # Both parties live in Benin, so both are credited the XOF launch value —
    # each in their own market's currency, not the order's.
    assert by_kind["referee"].user_id == inf
    assert by_kind["referee"].amount == REFERRAL_CREDIT["XOF"]
    assert by_kind["referee"].currency == "XOF"
    assert by_kind["referee"].source_user_id == referrer_id
    assert by_kind["referee"].contract_id == cid
    assert by_kind["referrer"].user_id == referrer_id
    assert by_kind["referrer"].amount == REFERRAL_CREDIT["XOF"]
    assert by_kind["referrer"].source_user_id == inf


def test_each_side_is_credited_in_its_own_market_currency(client):
    """A Ghanaian referrer spends the credit in GHS; telling them they earned
    XOF would be telling them nothing."""
    biz, inf, cid = _signed_contract(client)
    referrer_id = _referred_by(client, inf, country="GH")
    escrow = _fund(client, biz, cid)
    client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz))

    by_kind = {c.kind: c for c in _credits(client)}
    assert (by_kind["referee"].currency, by_kind["referee"].amount) == ("XOF", REFERRAL_CREDIT["XOF"])
    assert (by_kind["referrer"].currency, by_kind["referrer"].amount) == ("GHS", REFERRAL_CREDIT["GHS"])


def test_second_completed_order_credits_nobody_again(client):
    """The referee's existing credit row IS the first-order flag: a second
    cleared escrow finds it and pays nothing."""
    biz, inf, cid = _signed_contract(client)
    _referred_by(client, inf)
    first = _fund(client, biz, cid)
    client.post(f"/payments/escrow/{first['id']}/release", headers=_headers(biz))
    assert len(_credits(client)) == 2

    second_contract = _another_signed_contract(client, biz, inf)
    second = _fund(client, biz, second_contract)
    assert client.post(f"/payments/escrow/{second['id']}/release", headers=_headers(biz)).status_code == 200
    assert len(_credits(client)) == 2


def test_release_for_unreferred_users_credits_nobody(client):
    biz, inf, cid = _signed_contract(client)
    escrow = _fund(client, biz, cid)
    assert client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz)).status_code == 200
    assert _credits(client) == []


def test_auto_release_also_awards_the_referral(client):
    """Order completion is the trigger, not the button: the timeout path is a
    completed order too."""
    biz, inf, cid = _signed_contract(client)
    _referred_by(client, inf)
    escrow = _fund(client, biz, cid)
    _submitted(client, cid, inf)
    _age_release_deadline(client, escrow["id"])
    assert client.post("/payments/escrow/auto-release", headers=ADMIN).json()["released"] == 1
    assert {c.kind for c in _credits(client)} == {"referee", "referrer"}


def test_award_failure_never_breaks_the_release(client, monkeypatch):
    """The payout has already happened at the provider by the time the reward
    runs. A rewards bug must not turn a paid creator into a 500."""
    biz, inf, cid = _signed_contract(client)
    _referred_by(client, inf)
    escrow = _fund(client, biz, cid)

    def boom(*args, **kwargs):
        raise RuntimeError("referral rewards exploded")

    monkeypatch.setattr(pay_service, "award_for_completed_order", boom)
    r = client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz))
    assert r.status_code == 200
    assert r.json()["status"] == "released"
    assert r.json()["commission_amount"] == 1500
    # No credit was written, and that is the acceptable half of the trade.
    assert _credits(client) == []

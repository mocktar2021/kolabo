"""Resolving a dispute (KOL-37): the split, the fee, and the admin queue.

A separate file from test_disputes.py because it needs the admin router
mounted alongside the payments one, and because these are the money cases:
they are the ones somebody reads first when a figure looks wrong.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.modules.admin.models import AdminActionLog
from app.modules.admin.router import router as admin_router
from app.modules.auth.models import ReferralCredit, User
from app.modules.campaigns import models as campaigns
from app.modules.contracts import models as contracts
from app.modules.payments import models as pay_models
from app.modules.payments import provider as provider_module
from app.modules.payments import service as pay_service
from app.modules.payments.router import router as payments_router
from app.modules.profiles import models as profiles


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

    pay_service.payment_provider = provider_module.MockProvider()

    app = FastAPI()
    app.include_router(payments_router, prefix="/payments")
    app.include_router(admin_router, prefix="/admin")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


STATEMENT = "Only two of the three posts went up before the campaign ended."


def _disputed(client, amount=10000, suffix="1"):
    """A frozen escrow with an open dispute raised by the creator."""
    db = client.session_factory()
    try:
        biz = User(phone=f"+2299001{suffix}01", email=f"2299001{suffix}01@kolabo.test", password_hash="x", country_code="BJ", role="business", is_verified=True)
        inf = User(phone=f"+2299001{suffix}02", email=f"2299001{suffix}02@kolabo.test", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add_all([biz, inf])
        db.commit()
        db.refresh(biz)
        db.refresh(inf)
        c = contracts.Contract(
            campaign_id=f"camp-{suffix}", proposal_id=f"prop-{suffix}", business_user_id=biz.id,
            influencer_user_id=inf.id, language="fr", body="body", rate_amount=amount,
            rate_currency="XOF", timeline_days=7, status=contracts.SIGNED,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        ids = (biz.id, inf.id, c.id)
    finally:
        db.close()
    biz_id, inf_id, contract_id = ids
    escrow = client.post(
        "/payments/escrow/fund", json={"contract_id": contract_id}, headers=_headers(biz_id)
    ).json()
    dispute = client.post(
        f"/payments/escrow/{escrow['id']}/dispute",
        json={"reason": "late", "statement": STATEMENT},
        headers=_headers(inf_id),
    ).json()
    return biz_id, inf_id, escrow, dispute


def _resolve(client, admin_headers, escrow_id, released, refunded, note="Two of three delivered."):
    return client.post(
        f"/payments/escrow/{escrow_id}/resolve",
        json={"released_amount": released, "refunded_amount": refunded, "note": note},
        headers=admin_headers,
    )


def _payouts(client):
    return pay_service.payment_provider.payouts


def _referred_by(client, user_id, phone="+22990019999"):
    db = client.session_factory()
    try:
        referrer = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add(referrer)
        db.commit()
        db.refresh(referrer)
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


# --- The split ----------------------------------------------------------


def test_a_split_releases_part_and_refunds_the_rest(client, admin_headers, admin_user_id):
    """Real disputes are partial. A binary outcome forces a wrong answer on
    one of the two people."""
    biz, inf, escrow, dispute = _disputed(client, amount=10000)
    r = _resolve(client, admin_headers, escrow["id"], released=6000, refunded=4000)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "resolved"
    assert (body["released_amount"], body["refunded_amount"]) == (6000, 4000)
    # The account that decided, not a string somebody typed into a header.
    assert body["resolved_by"] == admin_user_id
    # 15 percent of the released 6000 is 900, so the creator receives 5100 and
    # the brand gets its 4000 back untouched.
    amounts = [p["amount"] for p in _payouts(client)]
    assert amounts == [5100, 4000]
    assert body["escrow"]["commission_amount"] == 900


def test_commission_is_charged_only_on_the_released_part(client, admin_headers):
    """Refunded money never earned a fee."""
    biz, inf, escrow, dispute = _disputed(client, amount=20000)
    body = _resolve(client, admin_headers, escrow["id"], released=5000, refunded=15000).json()
    # 15 percent of 5000, not of 20000: 750 rather than 3000.
    assert body["escrow"]["commission_amount"] == 750
    assert _payouts(client)[0]["amount"] == 4250


def test_amounts_that_do_not_add_up_are_refused(client, admin_headers):
    """A rounding gap here is a real loss that only surfaces at
    reconciliation, so it is refused at the door."""
    biz, inf, escrow, dispute = _disputed(client, amount=10000)
    short = _resolve(client, admin_headers, escrow["id"], released=6000, refunded=3000)
    assert short.status_code == 400
    assert "10000" in short.json()["detail"] and "9000" in short.json()["detail"]
    assert _resolve(client, admin_headers, escrow["id"], released=6000, refunded=5000).status_code == 400
    # Nothing moved and the escrow is still frozen for a real decision.
    assert _payouts(client) == []
    assert client.get(f"/payments/escrow/{escrow['id']}", headers=_headers(biz)).json()["status"] == "disputed"


def test_a_full_refund_leaves_the_escrow_refunded(client, admin_headers):
    biz, inf, escrow, dispute = _disputed(client, amount=10000)
    body = _resolve(client, admin_headers, escrow["id"], released=0, refunded=10000).json()
    assert body["escrow"]["status"] == "refunded"
    assert body["escrow"]["commission_amount"] == 0
    assert [p["amount"] for p in _payouts(client)] == [10000]


def test_a_full_release_leaves_the_escrow_released(client, admin_headers):
    biz, inf, escrow, dispute = _disputed(client, amount=10000)
    body = _resolve(client, admin_headers, escrow["id"], released=10000, refunded=0).json()
    assert body["escrow"]["status"] == "released"
    assert body["escrow"]["commission_amount"] == 1500
    assert [p["amount"] for p in _payouts(client)] == [8500]


def test_any_money_reaching_the_creator_means_released(client, admin_headers):
    """\"Refunded\" has to mean the buyer got their money back, and a buyer who
    got 90 percent of it did not."""
    biz, inf, escrow, dispute = _disputed(client, amount=10000)
    assert _resolve(client, admin_headers, escrow["id"], released=1000, refunded=9000).json()["escrow"]["status"] == "released"


def _brief(client, business_user_id, campaign_id="camp-1"):
    """The campaign the contracts here only ever named by id. Written for the
    case below and nowhere else: everywhere in this file its absence is the
    normal state, and the completion hook is silent about a brief that is not
    there rather than turning a settled dispute into a 500."""
    db = client.session_factory()
    try:
        db.add(campaigns.Campaign(
            id=campaign_id, business_user_id=business_user_id, title="Launch push",
            budget_amount=500000, budget_currency="XOF",
            deliverables=[{"platform": "instagram", "type": "post", "quantity": 1}],
            status=campaigns.PUBLISHED,
        ))
        db.commit()
    finally:
        db.close()


def _campaign_status(client, campaign_id="camp-1"):
    db = client.session_factory()
    try:
        return db.query(campaigns.Campaign).filter(
            campaigns.Campaign.id == campaign_id
        ).first().status
    finally:
        db.close()


@pytest.mark.parametrize("released,refunded", [(6000, 4000), (0, 10000)])
def test_settling_the_last_dispute_finishes_the_campaign(client, admin_headers, released, refunded):
    """Either way the split falls the escrow reaches an ending — RELEASED when
    anything reached the creator, REFUNDED when nothing did — and both are the
    money ending the completion rule asks for. A brief must not be left looking
    live because its last deal ended in an argument."""
    biz, inf, escrow, dispute = _disputed(client, amount=10000)
    _brief(client, biz)
    assert _campaign_status(client) == campaigns.PUBLISHED

    assert _resolve(client, admin_headers, escrow["id"], released=released, refunded=refunded).status_code == 200
    assert _campaign_status(client) == campaigns.COMPLETED


def test_resolving_is_logged_and_closed_to_everyone_but_an_admin(client, admin_headers):
    biz, inf, escrow, dispute = _disputed(client, amount=10000)
    # An admin is a flag on an account now, so a party's own bearer token — a
    # perfectly valid login — still buys nothing here.
    as_a_party = client.post(
        f"/payments/escrow/{escrow['id']}/resolve",
        json={"released_amount": 10000, "refunded_amount": 0},
        headers=_headers(biz),
    )
    assert as_a_party.status_code in (401, 403)
    _resolve(client, admin_headers, escrow["id"], released=6000, refunded=4000, note="Two of three.")
    db = client.session_factory()
    log = db.query(AdminActionLog).filter(AdminActionLog.target_id == escrow["id"]).first()
    db.close()
    assert log is not None
    assert log.action == "dispute_resolved"
    assert log.reason == "Two of three."


def test_a_resolved_dispute_cannot_be_resolved_again(client, admin_headers):
    biz, inf, escrow, dispute = _disputed(client, amount=10000)
    assert _resolve(client, admin_headers, escrow["id"], released=10000, refunded=0).status_code == 200
    assert _resolve(client, admin_headers, escrow["id"], released=0, refunded=10000).status_code == 400


# --- The referral hook --------------------------------------------------


def test_a_split_that_paid_the_creator_counts_as_a_completed_order(client, admin_headers):
    """The reward pays for transactions that cleared escrow, and a partial
    payment is still a job somebody did and got paid for."""
    biz, inf, escrow, dispute = _disputed(client, amount=10000)
    _referred_by(client, inf)
    _resolve(client, admin_headers, escrow["id"], released=6000, refunded=4000)
    assert {c.kind for c in _credits(client)} == {"referee", "referrer"}


def test_a_fully_refunded_dispute_credits_nobody(client, admin_headers):
    """A full refund is the transaction being unwound. Crediting it would make
    \"dispute, then refund\" a free way to mint credit."""
    biz, inf, escrow, dispute = _disputed(client, amount=10000)
    _referred_by(client, inf)
    _resolve(client, admin_headers, escrow["id"], released=0, refunded=10000)
    assert _credits(client) == []


# --- The queue ----------------------------------------------------------


def test_the_queue_puts_waiting_cases_first_then_oldest_first(client, admin_headers):
    biz1, inf1, escrow1, first = _disputed(client, suffix="1")
    biz2, inf2, escrow2, second = _disputed(client, suffix="2")
    _, _, _, fresh = _disputed(client, suffix="3")

    # Close the window on the first two, oldest of them raised first.
    db = client.session_factory()
    for did in (first["id"], second["id"]):
        d = db.query(pay_models.Dispute).filter(pay_models.Dispute.id == did).first()
        d.respond_by = pay_models.utcnow().replace(year=2020)
    db.commit()
    db.close()
    assert client.post("/payments/disputes/escalate", headers=admin_headers).json()["escalated"] == 2

    queue = client.get("/admin/disputes", headers=admin_headers).json()
    assert [row["id"] for row in queue] == [first["id"], second["id"], fresh["id"]]
    assert [row["status"] for row in queue][:2] == ["awaiting_admin", "awaiting_admin"]


def test_the_queue_carries_what_it_takes_to_triage(client, admin_headers):
    biz, inf, escrow, dispute = _disputed(client, amount=25000)
    db = client.session_factory()
    db.add(profiles.BusinessProfile(user_id=biz, company_name="Sika Foods"))
    db.add(profiles.InfluencerProfile(user_id=inf, display_name="Ama K."))
    db.commit()
    db.close()
    client.post(
        f"/payments/disputes/{dispute['id']}/messages",
        json={"body": "Both posts are live, here are the links."},
        headers=_headers(biz),
    )

    row = client.get("/admin/disputes", headers=admin_headers).json()[0]
    assert (row["amount"], row["currency"]) == (25000, "XOF")
    assert row["reason"] == "late"
    assert row["business_name"] == "Sika Foods"
    assert row["creator_name"] == "Ama K."
    assert row["message_count"] == 1


def test_a_resolved_dispute_leaves_the_queue(client, admin_headers):
    biz, inf, escrow, dispute = _disputed(client)
    assert len(client.get("/admin/disputes", headers=admin_headers).json()) == 1
    _resolve(client, admin_headers, escrow["id"], released=10000, refunded=0)
    assert client.get("/admin/disputes", headers=admin_headers).json() == []


def test_the_queue_needs_an_admin(client):
    assert client.get("/admin/disputes").status_code == 401

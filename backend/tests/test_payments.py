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
from app.modules.campaigns import models as campaigns
from app.modules.contracts import models as contracts
from app.modules.deliverables import models as deliverables
from app.modules.payments import gateway_models
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


def _signed_contract(client, signed=True, amount=10000, biz_email="brand@example.com",
                     biz_phone=None, inf_phone=None):
    """A brand, a creator and a contract between them.

    NEITHER PARTY HAS A PHONE NUMBER BY DEFAULT, which is what an account
    created since registration stopped asking for one looks like. The two
    fields are here so the pair of tests below can seed a pre-flip account and
    show that both shapes still move money.
    """
    db = client.session_factory()
    try:
        biz = User(email=biz_email, phone=biz_phone, password_hash="x", country_code="BJ", role="business", is_verified=True)
        inf = User(email="creator@example.com", phone=inf_phone, password_hash="x", country_code="BJ", role="influencer", is_verified=True)
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


def _referred_by(client, user_id, country="BJ", email="referrer@example.com"):
    """Give an existing user a referrer, as a signup with a code would have."""
    db = client.session_factory()
    try:
        referrer = User(email=email, password_hash="x", country_code=country, role="influencer", is_verified=True)
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


def test_funding_names_the_payer_by_address_and_never_by_None(client):
    """The mock path's half of the phone-is-nullable problem.

    fund_escrow passed business.phone into MobileMoneyProvider.collect, which
    is typed `target: str`. That column is None for every account created since
    registration stopped asking, so the mock would have filed None as the payer
    — harmless in a list, and exactly the shape of mistake that is not harmless
    in the gateway path beside it. The address is what an account IS now, so it
    is what identifies the payer.
    """
    biz, _inf, cid = _signed_contract(client)
    assert client.post(
        "/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)
    ).status_code == 201
    assert pay_service.payment_provider.collections[0]["target"] == "brand@example.com"


def test_a_pre_flip_brand_with_no_address_still_names_its_number(client):
    """An account that registered before the flip has a number and no address,
    and must not become a blank payer on the way through."""
    biz, _inf, cid = _signed_contract(client, biz_email=None, biz_phone="+22990000001")
    assert client.post(
        "/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)
    ).status_code == 201
    assert pay_service.payment_provider.collections[0]["target"] == "+22990000001"


def test_fund_requires_ownership_and_no_double_fund(client):
    biz, inf, cid = _signed_contract(client)
    assert client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(inf)).status_code == 403
    assert client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).status_code == 201
    assert client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).status_code == 409


def _submission_row(client, contract_id):
    """The submission on a contract, read straight from the table."""
    db = client.session_factory()
    try:
        return (
            db.query(deliverables.DeliverableSubmission)
            .filter(deliverables.DeliverableSubmission.contract_id == contract_id)
            .first()
        )
    finally:
        db.close()


def test_release_deducts_commission(client):
    biz, inf, cid = _signed_contract(client, amount=10000)
    escrow = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).json()
    # Confirming delivery now approves an open hand-in, so there has to be one.
    _submitted(client, cid, inf)
    r = client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "released"
    # 15 percent of 10000 is 1500 commission; payout is 8500.
    assert body["commission_amount"] == 1500
    assert pay_service.payment_provider.payouts[0]["amount"] == 8500


def _payout_method(client, user_id, phone="+22996000000"):
    """The wallet a creator actually nominated, which is where a payout goes.

    Written straight to the table rather than through PUT /payments/payout-method:
    this file mounts only the escrow router, and what is under test is where the
    money is addressed, not the form that collects it.
    """
    db = client.session_factory()
    try:
        db.add(
            gateway_models.PayoutMethod(
                user_id=user_id, country="BJ", mode="mtn_open", phone=phone
            )
        )
        db.commit()
    finally:
        db.close()


def test_a_legacy_payout_goes_to_the_nominated_wallet_and_never_to_None(client):
    """The third place the account phone was read, and the one that was already
    slightly wrong before the flip made it dangerous.

    payouts.disburse's legacy branch sent `user.phone if user else ""`, which
    guarded against a missing USER and not against a missing NUMBER. Since
    registration stopped collecting one that column is None for every creator
    who signed up after, and MobileMoneyProvider.payout is typed `target: str`.

    The correction is not only the None: method.phone is the mobile money
    wallet the creator nominated, and users.phone was only ever the number they
    happened to log in with. The real gateway path has always used the wallet;
    this leg simply never caught up.
    """
    biz, inf, cid = _signed_contract(client)
    _payout_method(client, inf)
    escrow = _fund(client, biz, cid)
    _submitted(client, cid, inf)
    assert client.post(
        f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz)
    ).status_code == 200
    assert pay_service.payment_provider.payouts[0]["target"] == "+22996000000"


def test_a_creator_with_no_wallet_and_no_number_is_a_blank_target_not_a_None(client):
    """Nothing real reads this value — the branch only runs where no gateway is
    configured — but a None here is the same bug as a None in the gateway path
    beside it, and the type says str."""
    biz, inf, cid = _signed_contract(client)
    escrow = _fund(client, biz, cid)
    _submitted(client, cid, inf)
    assert client.post(
        f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz)
    ).status_code == 200
    assert pay_service.payment_provider.payouts[0]["target"] == ""


def _brief(client, business_user_id, campaign_id="camp-1"):
    """The campaign the contracts in this file only ever named by id.

    Every other case here leaves it absent, which is a real state — a contract
    row carries a campaign_id and nothing enforces a brief behind it — and the
    completion hook is silent about it on purpose. This one writes the row so
    the hook has something to finish.
    """
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


def test_releasing_the_last_escrow_finishes_the_campaign(client):
    """The commonest way a brief ends, through the real endpoint: the brand
    confirms the only delivery, the money leaves escrow, and the campaign
    reaches its terminal state without the router knowing anything about it —
    the hook is at the service layer for exactly that reason.

    The rule itself (which contract and escrow states count as an ending) is
    pinned in test_cancellations.py; what this asserts is that the release path
    calls it at all, and after the release has been committed."""
    biz, inf, cid = _signed_contract(client)
    _brief(client, biz)
    escrow = _fund(client, biz, cid)
    assert _campaign_status(client) == campaigns.PUBLISHED
    _submitted(client, cid, inf)

    r = client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz))
    assert r.status_code == 200
    assert r.json()["status"] == "released"
    assert _campaign_status(client) == campaigns.COMPLETED


def test_a_release_on_a_contract_with_no_campaign_row_still_pays_out(client):
    """The hook must never cost somebody their money. A contract naming a brief
    that was never written is the state every other case in this file is in,
    and the release has to behave exactly as it always did."""
    biz, inf, cid = _signed_contract(client)
    escrow = _fund(client, biz, cid)
    _submitted(client, cid, inf)

    r = client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz))
    assert r.status_code == 200
    assert r.json()["status"] == "released"
    assert pay_service.payment_provider.payouts[0]["amount"] == 8500


def test_release_needs_an_open_submission(client):
    """Deliverables D2: confirming delivery approves what the creator handed in,
    so with nothing submitted there is nothing to confirm and the money waits.
    A business does not pay out of the deliverable flow."""
    biz, inf, cid = _signed_contract(client)
    escrow = _fund(client, biz, cid)
    r = client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz))
    # A 400 on a freshly funded, undisputed escrow can only be the D2 gate.
    # (The coded refusal escrow_release_needs_submission and its two languages
    # are guarded by test_error_codes.py and errorMessages.test.ts; this throwaway
    # app does not register the AppError handler, so it asserts on behaviour.)
    assert r.status_code == 400
    # The money did not move.
    assert client.get(f"/payments/escrow/{escrow['id']}", headers=_headers(biz)).json()["status"] == "held"


def test_release_approves_the_open_submission(client):
    """The divergence this closes: releasing from the escrow side now closes the
    open hand-in as approved in the same act, so deliverable state and escrow
    state can no longer tell two different stories."""
    biz, inf, cid = _signed_contract(client)
    escrow = _fund(client, biz, cid)
    _submitted(client, cid, inf)
    r = client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz))
    assert r.status_code == 200
    assert r.json()["status"] == "released"
    sub = _submission_row(client, cid)
    assert sub.status == deliverables.APPROVED
    assert sub.reviewed_by_user_id == biz
    assert sub.reviewed_at is not None


def test_only_business_can_release(client):
    biz, inf, cid = _signed_contract(client)
    escrow = client.post("/payments/escrow/fund", json={"contract_id": cid}, headers=_headers(biz)).json()
    assert client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(inf)).status_code == 403


def test_auto_release_after_timeout(client, admin_headers):
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
    r = client.post("/payments/escrow/auto-release", headers=admin_headers)
    assert r.json()["released"] == 1
    assert client.get(f"/payments/escrow/{escrow['id']}", headers=_headers(biz)).json()["status"] == "released"


def test_the_auto_release_sweep_finishes_the_campaign_too(client, admin_headers):
    """The sweep pays out in a batch and commits once, so it closes the briefs
    it touched in a pass of its own afterwards rather than one at a time. A
    creator paid by the clock ends the brief exactly as a creator paid by the
    button does."""
    biz, inf, cid = _signed_contract(client)
    _brief(client, biz)
    escrow = _fund(client, biz, cid)
    _submitted(client, cid, inf)
    _age_release_deadline(client, escrow["id"])

    assert client.post("/payments/escrow/auto-release", headers=admin_headers).json()["released"] == 1
    assert _campaign_status(client) == campaigns.COMPLETED


def test_nothing_submitted_never_auto_releases(client, admin_headers):
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
    assert client.post("/payments/escrow/auto-release", headers=admin_headers).json()["released"] == 0
    assert client.get(f"/payments/escrow/{escrow['id']}", headers=_headers(biz)).json()["status"] == "held"


def test_a_frozen_escrow_cannot_be_released_by_the_business(client, admin_headers):
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
    assert client.post("/payments/escrow/auto-release", headers=admin_headers).json()["released"] == 0


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
    _submitted(client, cid, inf)
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
    _submitted(client, cid, inf)
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
    _submitted(client, cid, inf)
    client.post(f"/payments/escrow/{first['id']}/release", headers=_headers(biz))
    assert len(_credits(client)) == 2

    second_contract = _another_signed_contract(client, biz, inf)
    second = _fund(client, biz, second_contract)
    _submitted(client, second_contract, inf)
    assert client.post(f"/payments/escrow/{second['id']}/release", headers=_headers(biz)).status_code == 200
    assert len(_credits(client)) == 2


def test_release_for_unreferred_users_credits_nobody(client):
    biz, inf, cid = _signed_contract(client)
    escrow = _fund(client, biz, cid)
    _submitted(client, cid, inf)
    assert client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz)).status_code == 200
    assert _credits(client) == []


def test_auto_release_also_awards_the_referral(client, admin_headers):
    """Order completion is the trigger, not the button: the timeout path is a
    completed order too."""
    biz, inf, cid = _signed_contract(client)
    _referred_by(client, inf)
    escrow = _fund(client, biz, cid)
    _submitted(client, cid, inf)
    _age_release_deadline(client, escrow["id"])
    assert client.post("/payments/escrow/auto-release", headers=admin_headers).json()["released"] == 1
    assert {c.kind for c in _credits(client)} == {"referee", "referrer"}


def test_award_failure_never_breaks_the_release(client, monkeypatch):
    """The payout has already happened at the provider by the time the reward
    runs. A rewards bug must not turn a paid creator into a 500."""
    biz, inf, cid = _signed_contract(client)
    _referred_by(client, inf)
    escrow = _fund(client, biz, cid)
    _submitted(client, cid, inf)

    def boom(*args, **kwargs):
        raise RuntimeError("referral rewards exploded")

    monkeypatch.setattr(pay_service, "award_for_completed_order", boom)
    r = client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz))
    assert r.status_code == 200
    assert r.json()["status"] == "released"
    assert r.json()["commission_amount"] == 1500
    # No credit was written, and that is the acceptable half of the trade.
    assert _credits(client) == []

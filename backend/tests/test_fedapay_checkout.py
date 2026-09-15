"""Hosted checkout, payouts and the webhook, end to end against a fake gateway.

WHY A FAKE GATEWAY AND NOT A MOCKED FedaPayGateway. What these tests are about
is our state machine — when an escrow appears, when it does not, what happens
to a release whose payout fails — and that machine talks to the PaymentGateway
protocol, not to FedaPay. A fake that implements the protocol lets each test
say "the gateway says this happened" in one line and keeps the FedaPay wire
format where it belongs, in test_fedapay_gateway.py, which drives the real
client against recorded response bodies.

The registry is reset around every test. Without that, a gateway installed here
would leak into test_payments.py, where the direct funding path deliberately
REFUSES as soon as a live gateway is configured — and the failure would look
like a bug in escrow funding rather than a dirty fixture.
"""
import json
import time

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
from app.modules.deliverables import models as deliverables
from app.modules.payments import gateway_models as gmodels
from app.modules.payments import models as pay_models
from app.modules.payments import provider as provider_module
from app.modules.payments import service as pay_service
from app.modules.payments.gateway_router import router as gateway_router
from app.modules.payments.gateways import base as gwbase
from app.modules.payments.gateways import registry, signature
from app.modules.payments.gateways.base import (
    CollectionStart,
    CollectionState,
    GatewayError,
    PayoutState,
)
from app.modules.payments.router import router as payments_router
from app.modules.payments.webhooks import router as webhooks_router

WEBHOOK_SECRET = "wh_test_secret"


class FakeGateway:
    """A PaymentGateway that does whatever the test tells it to."""

    name = "fedapay"

    def __init__(self):
        self.webhook_secret = WEBHOOK_SECRET
        self.collection_status = gwbase.SUCCEEDED
        self.collection_amount = None  # None -> echo whatever was asked for
        self.collection_currency = "XOF"
        self.collection_fee = None  # None -> the gateway reported no fee
        self.payout_status = gwbase.PAYOUT_SENT
        self.payout_fee = None  # ditto, and NOT the same claim as a fee of 0
        self.payout_raises = False
        self.payouts_sent = []
        self.started = []

    def supports(self, country, currency):
        return country in ("BJ", "TG", "CI") and currency == "XOF"

    def start_collection(self, *, amount, currency, **kw):
        self.started.append({"amount": amount, "currency": currency, **kw})
        self._last_amount = amount
        return CollectionStart(reference="tx_1", checkout_url="https://pay.test/tx_1")

    def read_collection(self, reference):
        return CollectionState(
            reference=reference,
            status=self.collection_status,
            amount=self.collection_amount
            if self.collection_amount is not None
            else getattr(self, "_last_amount", 0),
            currency=self.collection_currency,
            raw_status="approved",
            fee=self.collection_fee,
        )

    def send_payout(self, *, amount, currency, description, target, merchant_reference=None):
        if self.payout_raises:
            raise GatewayError("network down", retryable=True)
        self.payouts_sent.append({"amount": amount, "target": target})
        return PayoutState(
            reference=f"po_{len(self.payouts_sent)}",
            status=self.payout_status,
            amount=amount,
            currency=currency,
            raw_status="sent",
            fee=self.payout_fee,
        )

    def read_payout(self, reference):
        return PayoutState(
            reference=reference,
            status=self.payout_status,
            amount=0,
            currency="XOF",
            fee=self.payout_fee,
        )

    def verify_webhook(self, raw_body, headers):
        header = next(
            (v for k, v in headers.items() if k.lower() == signature.SIGNATURE_HEADER), None
        )
        signature.verify_signature(raw_body, header, self.webhook_secret)
        return json.loads(raw_body)


@pytest.fixture(autouse=True)
def clean_registry():
    registry.reset_registry()
    yield
    registry.reset_registry()


@pytest.fixture()
def gateway():
    fake = FakeGateway()
    for country in ("BJ", "TG", "CI"):
        registry.set_gateway(country, fake)
    return fake


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

    pay_service.payment_provider = provider_module.MockProvider()

    app = FastAPI()
    app.include_router(payments_router, prefix="/payments")
    app.include_router(gateway_router, prefix="/payments")
    app.include_router(webhooks_router, prefix="/webhooks")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _seed(
    client,
    *,
    country="BJ",
    amount=50000,
    currency="XOF",
    signed=True,
    brand_phone="+22990000001",
):
    """A brand, a creator and a fully signed contract between them.

    brand_phone defaults to a number because plenty of these tests predate the
    identity flip and a pre-flip brand is a perfectly real fixture. A brand who
    registered AFTER it has None there, which is what
    test_a_brand_with_no_phone_can_still_start_a_checkout passes.
    """
    db = client.session_factory()
    try:
        brand = User(
            phone=brand_phone,
            email="brand@example.com",
            password_hash="x",
            country_code=country,
            role="business",
            is_verified=True,
        )
        creator = User(
            phone="+22990000002",
            password_hash="x",
            country_code=country,
            role="influencer",
            is_verified=True,
        )
        db.add_all([brand, creator])
        db.flush()
        contract = contracts.Contract(
            campaign_id="camp-1",
            proposal_id="prop-1",
            business_user_id=brand.id,
            influencer_user_id=creator.id,
            language="fr",
            body="terms",
            rate_amount=amount,
            rate_currency=currency,
            timeline_days=7,
            deliverables=[],
            status=contracts.SIGNED if signed else contracts.PENDING,
        )
        db.add(contract)
        db.commit()
        return brand.id, creator.id, contract.id
    finally:
        db.close()


def _escrow_count(client, contract_id):
    db = client.session_factory()
    try:
        return (
            db.query(pay_models.Escrow)
            .filter(pay_models.Escrow.contract_id == contract_id)
            .count()
        )
    finally:
        db.close()


# ------------------------------------------------------------------ checkout


def test_start_checkout_returns_a_url_and_does_not_fund_yet(client, gateway):
    """A 201 here means "we asked", NOT "they paid".

    The escrow must not exist until the gateway confirms the money arrived.
    Creating it optimistically at start would hold funds against a payer who
    never typed their PIN, and every downstream sweep would treat that as real
    money.
    """
    brand, _creator, contract = _seed(client)
    res = client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    )
    assert res.status_code == 201
    body = res.json()
    assert body["checkout_url"] == "https://pay.test/tx_1"
    assert body["status"] == "pending"
    assert body["escrow_id"] is None
    assert _escrow_count(client, contract) == 0
    # The amount asked for is the contract's, unscaled.
    assert gateway.started[0]["amount"] == 50000


def test_a_brand_with_no_phone_can_still_start_a_checkout(client, gateway):
    """THE REGRESSION THIS GUARDS IS THE WORST ONE IN THE IDENTITY FLIP.

    Registration stopped collecting a phone number, so users.phone is None for
    every brand that signed up since, and start_checkout read it straight into
    payer_phone on a parameter that was typed `str`. Funding is the one path
    where a None that merely "works" in Python is a brand who cannot pay us.

    What reaches the gateway is the address instead, and an absent number. The
    FedaPay client omits the customer's phone_number rather than sending a null
    inside it — see test_fedapay_gateway.py, which asserts that on the wire.

    Note what is NOT lost: the payer still chooses their network and types the
    paying number on the hosted checkout page this url leads to. The customer
    phone was never the wallet being debited.
    """
    brand, _creator, contract = _seed(client, brand_phone=None)
    res = client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    )
    assert res.status_code == 201
    assert res.json()["checkout_url"] == "https://pay.test/tx_1"

    started = gateway.started[0]
    assert started["payer_phone"] is None
    assert started["payer_email"] == "brand@example.com"


def test_a_brand_who_has_added_a_phone_still_sends_it(client, gateway):
    """The settings screen is the only place a number arrives from now, and a
    brand who used it must see that number on their payment record."""
    brand, _creator, contract = _seed(client, brand_phone="+22997000000")
    client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    )
    assert gateway.started[0]["payer_phone"] == "+22997000000"


def test_reading_a_paid_intent_creates_the_escrow(client, gateway):
    brand, _creator, contract = _seed(client)
    intent = client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    ).json()

    res = client.get(f"/payments/checkout/{intent['id']}", headers=_headers(brand))
    assert res.status_code == 200
    assert res.json()["status"] == "succeeded"
    assert res.json()["escrow_id"] is not None
    assert _escrow_count(client, contract) == 1

    db = client.session_factory()
    try:
        escrow = db.query(pay_models.Escrow).filter(
            pay_models.Escrow.contract_id == contract
        ).one()
        assert escrow.status == pay_models.HELD
        assert escrow.amount == 50000
        assert escrow.provider == "fedapay"
    finally:
        db.close()


def test_settling_twice_creates_one_escrow(client, gateway):
    """The webhook and the return page race, and both call settle.

    Whichever loses must find the work done rather than doing it again. One
    escrow per contract is also enforced by a unique index, but reaching that
    index would mean an IntegrityError inside a webhook — a 500 that makes the
    gateway retry forever.
    """
    brand, _creator, contract = _seed(client)
    intent = client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    ).json()
    first = client.get(f"/payments/checkout/{intent['id']}", headers=_headers(brand)).json()
    second = client.get(f"/payments/checkout/{intent['id']}", headers=_headers(brand)).json()
    assert first["escrow_id"] == second["escrow_id"]
    assert _escrow_count(client, contract) == 1


def test_underpayment_is_refused_and_funds_nothing(client, gateway):
    """Pay 500 against a 50,000 contract and see whether the platform notices.

    It is the cheapest attack on a marketplace checkout and the one that is
    invisible if you only read the happy path. The intent fails, no escrow is
    created, and the money sits at the gateway for a human to reconcile.
    """
    brand, _creator, contract = _seed(client, amount=50000)
    intent = client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    ).json()
    gateway.collection_amount = 500

    body = client.get(f"/payments/checkout/{intent['id']}", headers=_headers(brand)).json()
    assert body["status"] == "failed"
    assert body["failure_reason"] == "amount_mismatch"
    assert _escrow_count(client, contract) == 0


def test_declined_payment_funds_nothing(client, gateway):
    brand, _creator, contract = _seed(client)
    intent = client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    ).json()
    gateway.collection_status = gwbase.FAILED

    assert (
        client.get(f"/payments/checkout/{intent['id']}", headers=_headers(brand)).json()["status"]
        == "failed"
    )
    assert _escrow_count(client, contract) == 0


def test_double_click_reuses_the_pending_intent(client, gateway):
    """Two open transactions against one contract is how somebody pays twice."""
    brand, _creator, contract = _seed(client)
    first = client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    ).json()
    second = client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    ).json()
    assert first["id"] == second["id"]
    assert len(gateway.started) == 1


def test_unsigned_contract_cannot_be_paid(client, gateway):
    brand, _creator, contract = _seed(client, signed=False)
    res = client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    )
    assert res.status_code == 400


def test_only_the_buyer_can_start_or_read_a_payment(client, gateway):
    brand, creator, contract = _seed(client)
    assert (
        client.post(
            "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(creator)
        ).status_code
        == 403
    )
    intent = client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    ).json()
    assert (
        client.get(f"/payments/checkout/{intent['id']}", headers=_headers(creator)).status_code
        == 403
    )


def test_a_country_with_no_gateway_is_refused_not_mocked(client, gateway):
    """Ghana has no FedaPay coverage, and the brand is told so.

    The alternative was falling back to the mock provider, which would show a
    Ghanaian brand a receipt for money nobody collected and leave a creator
    waiting on a payout that can never arrive. Failing loudly is the whole
    point of gateways/registry.py.
    """
    brand, _creator, contract = _seed(client, country="GH", currency="GHS")
    res = client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    )
    assert res.status_code == 400


def test_direct_funding_is_disabled_once_a_gateway_is_live(client, gateway):
    """The old one-step endpoint must not hold an escrow against uncollected money.

    A synchronous collect() cannot be honest against a real network: the payer
    has not seen a PIN prompt yet. So the endpoint refuses and names the path
    that works.
    """
    brand, _creator, contract = _seed(client)
    res = client.post(
        "/payments/escrow/fund", json={"contract_id": contract}, headers=_headers(brand)
    )
    assert res.status_code == 400
    assert _escrow_count(client, contract) == 0


def test_direct_funding_still_works_with_no_gateway(client):
    """And the mock path is untouched, which is what keeps the rest of the suite green."""
    brand, _creator, contract = _seed(client)
    res = client.post(
        "/payments/escrow/fund", json={"contract_id": contract}, headers=_headers(brand)
    )
    assert res.status_code == 201
    assert _escrow_count(client, contract) == 1


# ------------------------------------------------------------------- webhook


def _signed_headers(body: bytes) -> dict:
    import hashlib
    import hmac

    ts = int(time.time())
    mac = hmac.new(
        WEBHOOK_SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256
    ).hexdigest()
    return {"X-FEDAPAY-SIGNATURE": f"t={ts},s={mac}", "Content-Type": "application/json"}


def test_webhook_funds_the_escrow(client, gateway):
    brand, _creator, contract = _seed(client)
    client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    )

    body = json.dumps(
        {"id": "ev_1", "name": "transaction.approved", "entity": {"id": "tx_1"}}
    ).encode()
    res = client.post("/webhooks/fedapay", content=body, headers=_signed_headers(body))
    assert res.status_code == 200
    assert _escrow_count(client, contract) == 1


def test_unsigned_webhook_is_rejected_and_funds_nothing(client, gateway):
    """No bearer token protects this route, so the signature is the whole gate."""
    brand, _creator, contract = _seed(client)
    client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    )

    body = json.dumps({"id": "ev_2", "name": "transaction.approved", "entity": {"id": "tx_1"}}).encode()
    res = client.post("/webhooks/fedapay", content=body, headers={"Content-Type": "application/json"})
    assert res.status_code == 400
    assert _escrow_count(client, contract) == 0


def test_replayed_webhook_is_a_no_op(client, gateway):
    """At-least-once delivery is normal. Funding twice is not.

    The event id is inserted under a unique constraint BEFORE the work, so the
    duplicate loses the insert and returns 200 having done nothing.
    """
    brand, _creator, contract = _seed(client)
    client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    )
    body = json.dumps({"id": "ev_3", "name": "transaction.approved", "entity": {"id": "tx_1"}}).encode()

    assert client.post("/webhooks/fedapay", content=body, headers=_signed_headers(body)).status_code == 200
    assert client.post("/webhooks/fedapay", content=body, headers=_signed_headers(body)).status_code == 200
    assert _escrow_count(client, contract) == 1

    db = client.session_factory()
    try:
        assert db.query(gmodels.GatewayEvent).count() == 1
    finally:
        db.close()


def test_webhook_for_an_unknown_transaction_is_acknowledged(client, gateway):
    """200, not 500. Retrying will never make somebody else's transaction ours."""
    body = json.dumps({"id": "ev_4", "name": "transaction.approved", "entity": {"id": "nope"}}).encode()
    assert client.post("/webhooks/fedapay", content=body, headers=_signed_headers(body)).status_code == 200


def test_a_settled_collection_records_what_the_gateway_charged_us(client, gateway):
    """The first of the two costs between the gross and what Kolabo keeps.

    Commission is 15 percent of the gross, and the gateway takes its own cut of
    the same money on the way in. Until this was stored, that cut lived only in
    the raw webhook body on gateway_events and no query against our own tables
    could reach it, so "how much did we net" was a monthly reconciliation
    against the FedaPay dashboard rather than a SELECT.
    """
    brand, _creator, contract = _seed(client)
    gateway.collection_fee = 600

    intent = client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    ).json()
    client.get(f"/payments/checkout/{intent['id']}", headers=_headers(brand))

    db = client.session_factory()
    try:
        row = db.query(gmodels.PaymentIntent).filter(
            gmodels.PaymentIntent.id == intent["id"]
        ).one()
        assert row.status == gmodels.INTENT_SUCCEEDED
        assert row.gateway_fee == 600
    finally:
        db.close()


def test_a_collection_the_gateway_charged_nothing_for_stays_unknown(client, gateway):
    """No fee reported means no fee KNOWN, and the column says so with null.

    Defaulting this to zero would let a gateway that simply did not answer look
    like a gateway that worked for free, in the one report where that error
    always flatters us.
    """
    brand, _creator, contract = _seed(client)

    intent = client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    ).json()
    client.get(f"/payments/checkout/{intent['id']}", headers=_headers(brand))

    db = client.session_factory()
    try:
        row = db.query(gmodels.PaymentIntent).filter(
            gmodels.PaymentIntent.id == intent["id"]
        ).one()
        assert row.gateway_fee is None
    finally:
        db.close()


# ------------------------------------------------------------------- payouts


def _fund_and_deliver(client, gateway, brand, creator, contract):
    intent = client.post(
        "/payments/checkout/start", json={"contract_id": contract}, headers=_headers(brand)
    ).json()
    client.get(f"/payments/checkout/{intent['id']}", headers=_headers(brand))
    db = client.session_factory()
    try:
        escrow = db.query(pay_models.Escrow).filter(
            pay_models.Escrow.contract_id == contract
        ).one()
        db.add(
            deliverables.DeliverableSubmission(
                contract_id=contract,
                submitted_by_user_id=creator,
                link_url="https://example.com/post",
                status=deliverables.SUBMITTED,
            )
        )
        db.commit()
        return escrow.id
    finally:
        db.close()


def _set_method(client, user_id):
    return client.put(
        "/payments/payout-method",
        json={"country": "BJ", "mode": "mtn_open", "phone": "97000000", "account_name": "Ada Lovelace"},
        headers=_headers(user_id),
    )


def test_release_pays_the_creator_net_of_commission(client, gateway):
    brand, creator, contract = _seed(client)
    escrow_id = _fund_and_deliver(client, gateway, brand, creator, contract)
    _set_method(client, creator)

    res = client.post(f"/payments/escrow/{escrow_id}/release", headers=_headers(brand))
    assert res.status_code == 200
    # 15 percent commission on 50000 is 7500, so 42500 reaches the wallet.
    assert gateway.payouts_sent[0]["amount"] == 42500
    assert gateway.payouts_sent[0]["target"].mode == "mtn_open"

    db = client.session_factory()
    try:
        payout = db.query(gmodels.Payout).filter(gmodels.Payout.escrow_id == escrow_id).one()
        assert payout.status == gmodels.PAYOUT_SENT
    finally:
        db.close()


def test_a_failed_payout_does_not_undo_the_release(client, gateway):
    """THE most important test in this file.

    The brand confirmed delivery, so the creator is owed the money — and a
    mobile money network timing out thirty seconds later does not make that
    untrue. If the gateway failure propagated it would roll the release back
    and leave an escrow HELD on work that was accepted; if it were swallowed
    silently the escrow would say RELEASED with nobody paid and nothing
    tracking it. Instead: the escrow releases, and a FAILED Payout row carries
    the real state for the retry sweep.
    """
    brand, creator, contract = _seed(client)
    escrow_id = _fund_and_deliver(client, gateway, brand, creator, contract)
    _set_method(client, creator)
    gateway.payout_raises = True

    res = client.post(f"/payments/escrow/{escrow_id}/release", headers=_headers(brand))
    assert res.status_code == 200
    assert res.json()["status"] == pay_models.RELEASED

    db = client.session_factory()
    try:
        escrow = db.query(pay_models.Escrow).filter(pay_models.Escrow.id == escrow_id).one()
        assert escrow.status == pay_models.RELEASED
        assert escrow.commission_amount == 7500
        payout = db.query(gmodels.Payout).filter(gmodels.Payout.escrow_id == escrow_id).one()
        assert payout.status == gmodels.PAYOUT_FAILED
        assert payout.amount == 42500
        assert payout.attempts == 1
    finally:
        db.close()


def test_a_creator_with_no_wallet_on_file_is_still_owed_the_money(client, gateway):
    """Not a failure, and not retryable: no amount of retrying invents a wallet.

    The escrow releases, the payout waits in awaiting_method, and the creator
    is asked for their details. The sweep picks it up when they answer.
    """
    brand, creator, contract = _seed(client)
    escrow_id = _fund_and_deliver(client, gateway, brand, creator, contract)

    assert client.post(f"/payments/escrow/{escrow_id}/release", headers=_headers(brand)).status_code == 200
    db = client.session_factory()
    try:
        escrow = db.query(pay_models.Escrow).filter(pay_models.Escrow.id == escrow_id).one()
        assert escrow.status == pay_models.RELEASED
        payout = db.query(gmodels.Payout).filter(gmodels.Payout.escrow_id == escrow_id).one()
        assert payout.status == gmodels.PAYOUT_NO_METHOD
        assert payout.attempts == 0
    finally:
        db.close()
    assert gateway.payouts_sent == []


def test_the_sweep_pays_a_creator_who_adds_their_wallet_later(client, gateway):
    brand, creator, contract = _seed(client)
    escrow_id = _fund_and_deliver(client, gateway, brand, creator, contract)
    client.post(f"/payments/escrow/{escrow_id}/release", headers=_headers(brand))

    _set_method(client, creator)
    db = client.session_factory()
    try:
        from app.modules.payments import payouts as payouts_module

        result = payouts_module.run_pending_payouts(db)
        assert result["retried"] == 1
        payout = db.query(gmodels.Payout).filter(gmodels.Payout.escrow_id == escrow_id).one()
        assert payout.status == gmodels.PAYOUT_SENT
    finally:
        db.close()


def test_a_sent_payout_records_what_the_gateway_charged_us(client, gateway):
    """The second cost, and the reason one leg alone cannot state the margin.

    Kolabo's commission on 50000 is 7500, and both gateway fees come out of
    THAT rather than out of the creator's 42500, because commission is computed
    on the gross before either movement happens.
    """
    brand, creator, contract = _seed(client)
    escrow_id = _fund_and_deliver(client, gateway, brand, creator, contract)
    _set_method(client, creator)
    gateway.payout_fee = 425

    assert client.post(
        f"/payments/escrow/{escrow_id}/release", headers=_headers(brand)
    ).status_code == 200

    db = client.session_factory()
    try:
        payout = db.query(gmodels.Payout).filter(gmodels.Payout.escrow_id == escrow_id).one()
        assert payout.status == gmodels.PAYOUT_SENT
        assert payout.gateway_fee == 425
    finally:
        db.close()


def test_a_later_read_that_reports_no_fee_does_not_erase_the_one_we_have(client, gateway):
    """A payout is read more than once, and silence is not a correction.

    The send records the fee. The sweep then reads the same payout again, and
    if that read carries no fee it means the gateway did not mention one — not
    that the movement turned out to be free. Overwriting here would quietly
    delete a real cost every time a re-read happened to be quieter than the
    first one, which on a retried payout is most of them.
    """
    brand, creator, contract = _seed(client)
    escrow_id = _fund_and_deliver(client, gateway, brand, creator, contract)
    _set_method(client, creator)
    # Still in flight after the send, so the sweep will re-read it.
    gateway.payout_status = gwbase.PAYOUT_PENDING
    gateway.payout_fee = 425
    client.post(f"/payments/escrow/{escrow_id}/release", headers=_headers(brand))

    db = client.session_factory()
    try:
        from app.modules.payments import payouts as payouts_module

        payout = db.query(gmodels.Payout).filter(gmodels.Payout.escrow_id == escrow_id).one()
        assert payout.gateway_fee == 425

        gateway.payout_fee = None
        gateway.payout_status = gwbase.PAYOUT_SENT
        payouts_module.run_pending_payouts(db)

        db.refresh(payout)
        assert payout.status == gmodels.PAYOUT_SENT
        assert payout.gateway_fee == 425
    finally:
        db.close()


def test_payout_method_rejects_a_network_the_gateway_does_not_know(client, gateway):
    """Validated at the form, not at the payout.

    A rule enforced at the last possible moment fails in front of the wrong
    person — three weeks later, when a release cannot go out.
    """
    _brand, creator, _contract = _seed(client)
    res = client.put(
        "/payments/payout-method",
        json={"country": "BJ", "mode": "orange_ci", "phone": "97000000"},
        headers=_headers(creator),
    )
    assert res.status_code == 400


def test_payout_method_never_returns_the_full_number(client, gateway):
    _brand, creator, _contract = _seed(client)
    _set_method(client, creator)
    body = client.get("/payments/payout-method", headers=_headers(creator)).json()
    assert body["phone_masked"] == "*** 0000"
    assert "97000000" not in json.dumps(body)


def test_payment_config_reports_the_live_countries(client, gateway):
    body = client.get("/payments/config").json()
    assert body["enabled"] is True
    assert body["countries"] == ["BJ", "CI", "TG"]


def test_payment_config_is_honest_when_nothing_is_configured(client):
    body = client.get("/payments/config").json()
    assert body["enabled"] is False
    assert body["countries"] == []

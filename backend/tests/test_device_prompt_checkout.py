"""Funding a contract when there is no page to open.

WHY THIS FILE EXISTS. Every part of the funding flow was built on one
assumption: starting a collection returns a URL and the brand's browser goes
there. That assumption does not survive the market Kolabo launches in.
FeexPay's only hosted checkout takes CARDS, measured on 27 October by opening
it and reading it, and mobile money is how brands in Benin, Togo, Cote
d'Ivoire and Senegal actually pay. Its mobile money endpoint pushes a prompt
to a handset and returns nothing to open.

A FAKE GATEWAY, NOT FeexPayGateway, for the reason test_fedapay_checkout.py
gives about its own fake: what is under test here is Kolabo's state machine,
not a wire format. The FeexPay request and response bytes are pinned in
test_feexpay.py, which drives the real client against a MockTransport.

THE ONE THAT WOULD HAVE SHIPPED. checkout.py's duplicate-funding guard used
to read `checkout_url IS NOT NULL`, which is the same thing as "the gateway
accepted this" only for as long as every gateway returns a URL. A device
prompt never does, so under the old guard every reload of the funding page
would have started ANOTHER collection and the payer would have received a
second prompt, and a third, for one contract.
test_a_reload_does_not_send_a_second_prompt is that test, and it fails
against the old condition.
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
from app.modules.payments import gateway_models as gmodels
from app.modules.payments import provider as provider_module
from app.modules.payments import service as pay_service
from app.modules.payments.gateway_router import router as gateway_router
from app.modules.payments.gateways import base as gwbase
from app.modules.payments.gateways import registry
from app.modules.payments.gateways.base import (
    CollectionStart,
    CollectionState,
    GatewayError,
)
from app.modules.payments.router import router as payments_router

NETWORKS = {
    "BJ": ("MTN", "MOOV", "CELTIIS BJ"),
    "TG": ("MOOV TG", "TOGOCOM TG"),
}


class PromptGateway:
    """A gateway that pushes a prompt to a handset and returns no URL."""

    name = "feexpay"

    def __init__(self):
        self.started = []
        self.collection_status = gwbase.PENDING
        self.start_raises = False
        self.reference = "hthwUo946aQE"

    def supports(self, country, currency):
        return country in NETWORKS and currency == "XOF"

    def collection_networks(self, country):
        return NETWORKS.get(country, ())

    def start_collection(self, *, amount, currency, **kw):
        if self.start_raises:
            raise GatewayError("network down", retryable=True)
        # REFUSES WITHOUT A NETWORK, exactly as the real adapter does, and
        # the fake has to or the end-to-end translation of that refusal into
        # payments_gateway_unavailable is never exercised. The wording lives
        # in feexpay.py and is pinned in test_feexpay.py; what is under test
        # here is that a brand gets a 502 and a readable code rather than a
        # 500 or a pending intent for a prompt nobody was sent.
        if not kw.get("payer_network"):
            raise GatewayError("a network is required", retryable=False)
        self.started.append({"amount": amount, "currency": currency, **kw})
        return CollectionStart(
            reference=self.reference,
            checkout_url=None,
            payer_action=gwbase.PAYER_ACTION_DEVICE_PROMPT,
        )

    def read_collection(self, reference):
        return CollectionState(
            reference=reference,
            status=self.collection_status,
            amount=self.started[-1]["amount"] if self.started else 0,
            currency="XOF",
            raw_status=self.collection_status.upper(),
        )

    def send_payout(self, **kw):
        raise AssertionError("not part of this file")

    def read_payout(self, reference):
        raise AssertionError("not part of this file")

    def verify_webhook(self, raw_body, headers):
        raise GatewayError("no scheme observed")


class RedirectGateway:
    """The other shape, to prove the two stay apart.

    NO collection_networks METHOD AT ALL, which is the whole point of this
    class: a gateway whose payer picks an operator on its own hosted page has
    nothing to offer there and is not edited into compliance with an
    interface it has no use for. checkout.collection_networks finds that
    absence with getattr and answers [].

    DELIBERATELY NOT A SUBCLASS OF PromptGateway. It was one, with the method
    deleted off the subclass, and that proved nothing at all: deleting an
    override leaves the parent's, getattr found it, and the test asserting
    this gateway offers no networks got three. A fake whose defining feature
    is an absence should not inherit from something that has it.
    """

    name = "fedapay"

    def __init__(self):
        self.started = []
        self.collection_status = gwbase.SUCCEEDED

    def supports(self, country, currency):
        return country in NETWORKS and currency == "XOF"

    def start_collection(self, *, amount, currency, **kw):
        self.started.append({"amount": amount, "currency": currency, **kw})
        return CollectionStart(reference="tx_1", checkout_url="https://pay.test/tx_1")

    def read_collection(self, reference):
        return CollectionState(
            reference=reference,
            status=self.collection_status,
            amount=self.started[-1]["amount"] if self.started else 0,
            currency="XOF",
            raw_status="approved",
        )

    def send_payout(self, **kw):
        raise AssertionError("not part of this file")

    def read_payout(self, reference):
        raise AssertionError("not part of this file")

    def verify_webhook(self, raw_body, headers):
        raise GatewayError("not part of this file")


@pytest.fixture(autouse=True)
def clean_registry():
    registry.reset_registry()
    yield
    registry.reset_registry()


@pytest.fixture()
def gateway():
    fake = PromptGateway()
    for country in NETWORKS:
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
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _seed(client, *, country="BJ", amount=50000, brand_phone="+22990000001"):
    db = client.session_factory()
    try:
        brand = User(
            phone=brand_phone, email="brand@example.com", password_hash="x",
            country_code=country, role="business", is_verified=True,
        )
        creator = User(
            phone="+22990000002", email="22990000002@kolabo.test", password_hash="x",
            country_code=country, role="influencer", is_verified=True,
        )
        db.add_all([brand, creator])
        db.flush()
        contract = contracts.Contract(
            campaign_id="camp-1", proposal_id="prop-1",
            business_user_id=brand.id, influencer_user_id=creator.id,
            language="fr", body="terms", rate_amount=amount, rate_currency="XOF",
            timeline_days=7, deliverables=[], status=contracts.SIGNED,
        )
        db.add(contract)
        db.commit()
        return brand.id, contract.id
    finally:
        db.close()


def _start(client, brand, contract, **body):
    return client.post(
        "/payments/checkout/start",
        json={"contract_id": contract, **body},
        headers=_headers(brand),
    )


# ----------------------------------------------------- the prompt has no url


def test_a_prompt_collection_returns_no_url_and_says_what_to_do_instead(client, gateway):
    """The field a client renders from. A null checkout_url is not the signal:
    it also goes null once a redirect payment is terminal."""
    brand, contract = _seed(client)
    body = _start(client, brand, contract, payer_network="MTN", payer_phone="22966000000").json()
    assert body["checkout_url"] is None
    assert body["payer_action"] == "device_prompt"
    assert body["payer_network"] == "MTN"
    assert body["status"] == "pending"


def test_the_network_and_the_typed_number_reach_the_gateway(client, gateway):
    brand, contract = _seed(client)
    _start(client, brand, contract, payer_network="MTN", payer_phone="22966000000")
    sent = gateway.started[-1]
    assert sent["payer_network"] == "MTN"
    assert sent["payer_phone"] == "22966000000"


def test_the_typed_number_beats_the_one_on_the_account(client, gateway):
    """On a prompt flow these are different questions. The account number is
    who the brand is; this one is the wallet being debited, and a brand may
    well pay from a wallet they did not register with."""
    brand, contract = _seed(client, brand_phone="+22990000001")
    _start(client, brand, contract, payer_network="MOOV", payer_phone="22997000000")
    assert gateway.started[-1]["payer_phone"] == "22997000000"


def test_with_no_typed_number_the_account_number_is_still_offered(client, gateway):
    brand, contract = _seed(client, brand_phone="+22990000001")
    _start(client, brand, contract, payer_network="MTN")
    assert gateway.started[-1]["payer_phone"] == "+22990000001"


# ------------------------------------------------- the guard that would break


def test_a_reload_does_not_send_a_second_prompt(client, gateway):
    """THE REGRESSION THIS WHOLE CHANGE RISKED.

    The duplicate-funding guard used to require `checkout_url IS NOT NULL`,
    which a device prompt never has. Under that condition this test starts two
    collections and the payer's phone lights up twice for one contract. It now
    keys on provider_ref, which is what the guard always meant: the gateway
    accepted this attempt."""
    brand, contract = _seed(client)
    first = _start(client, brand, contract, payer_network="MTN", payer_phone="22966000000").json()
    second = _start(client, brand, contract, payer_network="MTN", payer_phone="22966000000").json()
    assert first["id"] == second["id"]
    assert len(gateway.started) == 1, "the payer was sent a second prompt"


def test_an_attempt_the_gateway_never_accepted_is_not_reused(client, gateway):
    """The row written just before a failed outbound call carries no
    transaction at the gateway at all. Handing it back to a brand as a live
    attempt would show them a payment that does not exist anywhere."""
    brand, contract = _seed(client)
    gateway.start_raises = True
    assert _start(client, brand, contract, payer_network="MTN", payer_phone="229660").status_code == 502

    gateway.start_raises = False
    second = _start(client, brand, contract, payer_network="MTN", payer_phone="22966000000")
    assert second.status_code == 201
    assert len(gateway.started) == 1

    db = client.session_factory()
    try:
        rows = (
            db.query(gmodels.PaymentIntent)
            .filter(gmodels.PaymentIntent.contract_id == contract)
            .all()
        )
        assert len(rows) == 2, "the failed attempt should still be on record"
        assert second.json()["id"] != [r for r in rows if r.provider_ref is None][0].id
    finally:
        db.close()


# ----------------------------------------------------------- KOL-130, old clients


def test_a_request_with_no_network_or_phone_is_still_accepted_by_the_api(client):
    """KOL-130. The last build approved by Apple and Google posts this body.
    A required field at the edge would answer it with a 422 naming something
    it has never heard of, and the only fix would be a store review.

    Routed to a REDIRECT gateway, which is what those builds have always
    reached. The point is that the API shape did not narrow."""
    redirect = RedirectGateway()
    registry.set_gateway("BJ", redirect)
    brand, contract = _seed(client)
    res = _start(client, brand, contract)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["checkout_url"] == "https://pay.test/tx_1"
    assert body["payer_action"] == "redirect"
    assert body["payer_network"] is None


def test_a_gateway_that_needs_a_network_refuses_readably_without_one(client, gateway):
    """The edge stays permissive and the gateway refuses what it cannot use.
    A brand reads a sentence about a network, not a schema error."""
    brand, contract = _seed(client)
    res = _start(client, brand, contract)
    assert res.status_code == 502
    # The sentence, not the code. This app fixture does not register
    # app_error_handler, so the body carries `detail` alone, exactly as
    # test_fedapay_checkout.py's does. What matters here is that the refusal
    # travels as a 502 the client already knows how to show, rather than
    # as a 500 or as a pending intent for a prompt nobody was sent.
    assert "Nothing has been charged" in res.json()["detail"]


def test_an_intent_written_before_the_migration_reads_as_a_redirect(client, gateway):
    """The additive migration left payer_action null on every existing row.
    The default is applied at the edge rather than by a backfill, which is
    what keeps the previous image able to run against this schema."""
    brand, contract = _seed(client)
    started = _start(client, brand, contract, payer_network="MTN", payer_phone="22966000000").json()
    db = client.session_factory()
    try:
        row = db.query(gmodels.PaymentIntent).filter(
            gmodels.PaymentIntent.id == started["id"]
        ).first()
        row.payer_action = None
        row.checkout_url = "https://pay.test/legacy"
        db.commit()
    finally:
        db.close()
    read = client.get(f"/payments/checkout/{started['id']}", headers=_headers(brand)).json()
    assert read["payer_action"] == "redirect"


# ------------------------------------------------------------------- polling


def test_polling_settles_the_prompt_once_the_payer_answers(client, gateway):
    """There is no return page to land on, so the client polls the same
    endpoint the return page already used. get_intent settles on read, which
    is why no new endpoint is needed for this."""
    brand, contract = _seed(client)
    started = _start(client, brand, contract, payer_network="MTN", payer_phone="22966000000").json()

    still = client.get(f"/payments/checkout/{started['id']}", headers=_headers(brand)).json()
    assert still["status"] == "pending"
    assert still["escrow_id"] is None

    gateway.collection_status = gwbase.SUCCEEDED
    done = client.get(f"/payments/checkout/{started['id']}", headers=_headers(brand)).json()
    assert done["status"] == "succeeded"
    assert done["escrow_id"], "the escrow is what the brand is actually waiting for"


def test_a_prompt_the_payer_refuses_fails_without_funding_anything(client, gateway):
    brand, contract = _seed(client)
    started = _start(client, brand, contract, payer_network="MTN", payer_phone="22966000000").json()
    gateway.collection_status = gwbase.FAILED
    done = client.get(f"/payments/checkout/{started['id']}", headers=_headers(brand)).json()
    assert done["status"] == "failed"
    assert done["escrow_id"] is None


# -------------------------------------------------------- the networks endpoint


def test_the_networks_endpoint_answers_from_the_routed_gateway(client, gateway):
    res = client.get("/payments/collection-networks/BJ")
    assert res.status_code == 200
    assert res.json() == ["MTN", "MOOV", "CELTIIS BJ"]


def test_it_is_case_insensitive_on_the_country(client, gateway):
    assert client.get("/payments/collection-networks/bj").json() == ["MTN", "MOOV", "CELTIIS BJ"]


def test_a_redirect_gateway_offers_no_networks_rather_than_raising(client):
    """Empty means "do not show a picker", not "something went wrong". The
    payer chooses their operator on the hosted page instead."""
    registry.set_gateway("BJ", RedirectGateway())
    assert client.get("/payments/collection-networks/BJ").json() == []


def test_an_unrouted_country_answers_empty_not_an_error(client, gateway):
    """A screen asking what to offer should get an empty list. A 500 on a
    dropdown is worse than no dropdown."""
    res = client.get("/payments/collection-networks/CI")
    assert res.status_code == 200
    assert res.json() == []


def test_a_country_that_does_not_exist_answers_empty_too(client, gateway):
    res = client.get("/payments/collection-networks/ZZ")
    assert res.status_code == 200
    assert res.json() == []

"""Tests for Epic E (KOL-5): contract generation and e-signature."""
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.errors import AppError, app_error_handler
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.campaigns import models as campaigns
from app.modules.contracts.router import router as contracts_router


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    # The REAL AppError handler, registered from app.core.errors the way
    # app/main.py does it, so a refusal reaches the client carrying its `code`.
    # Without it FastAPI's default HTTPException handler answers with `detail`
    # alone and a test cannot assert WHICH rule refused — which is the thing
    # both clients key their translated sentence off. Same reasoning, and the
    # same handler, as test_error_codes.py's fixture.
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(contracts_router, prefix="/contracts")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = testing_session
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _setup(client, proposal_status=campaigns.SUBMITTED, country="BJ"):
    """Create a business, an influencer, a published campaign, and a proposal."""
    db = client.session_factory()
    try:
        biz = User(phone="+22990000001", password_hash="x", country_code=country, role="business", is_verified=True)
        inf = User(phone="+22990000002", password_hash="x", country_code=country, role="influencer", is_verified=True)
        db.add_all([biz, inf]); db.commit(); db.refresh(biz); db.refresh(inf)
        camp = campaigns.Campaign(
            business_user_id=biz.id, title="Launch push", budget_amount=50000, budget_currency="XOF",
            deliverables=[{"platform": "instagram", "type": "post", "quantity": 2}],
            deadline=None, status=campaigns.PUBLISHED,
        )
        db.add(camp); db.commit(); db.refresh(camp)
        prop = campaigns.Proposal(
            campaign_id=camp.id, influencer_user_id=inf.id, version=1,
            rate_amount=10000, rate_currency="XOF", timeline_days=7, status=proposal_status,
        )
        db.add(prop); db.commit(); db.refresh(prop)
        return biz.id, inf.id, camp.id, prop.id
    finally:
        db.close()


def test_generate_contract_from_submitted_proposal(client):
    biz, inf, camp, prop = _setup(client)
    r = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending_signatures"
    assert body["rate_amount"] == 10000
    assert body["fully_signed"] is False
    # Proposal is now accepted.
    db = client.session_factory()
    p = db.query(campaigns.Proposal).filter(campaigns.Proposal.id == prop).first()
    db.close()
    assert p.status == "accepted"


def test_generated_body_is_french_placeholder_for_bj(client):
    biz, inf, camp, prop = _setup(client, country="BJ")
    contract = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()
    detail = client.get(f"/contracts/{contract['id']}", headers=_headers(biz)).json()
    assert detail["language"] == "fr"
    assert "MODELE PROVISOIRE" in detail["body"]


def test_generate_requires_ownership(client):
    biz, inf, camp, prop = _setup(client)
    r = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(inf))
    assert r.status_code == 403


def test_cannot_generate_twice_for_same_proposal(client):
    biz, inf, camp, prop = _setup(client)
    assert client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).status_code == 201
    assert client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).status_code == 409


def test_both_signatures_required_then_immutable(client):
    biz, inf, camp, prop = _setup(client)
    contract = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()
    cid = contract["id"]
    r = client.post(f"/contracts/{cid}/sign", json={"signature": "Business Rep"}, headers=_headers(biz))
    assert r.json()["business_signed"] is True
    assert r.json()["fully_signed"] is False
    r = client.post(f"/contracts/{cid}/sign", json={"signature": "The Creator"}, headers=_headers(inf))
    assert r.json()["fully_signed"] is True
    assert r.json()["status"] == "signed"
    # Immutable once fully signed.
    r = client.post(f"/contracts/{cid}/sign", json={"signature": "again"}, headers=_headers(biz))
    assert r.status_code == 400


def test_non_party_cannot_sign(client):
    biz, inf, camp, prop = _setup(client)
    contract = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()
    other = "outsider-user-id"
    r = client.post(f"/contracts/{contract['id']}/sign", json={"signature": "x"}, headers=_headers(other))
    assert r.status_code == 403


def test_double_sign_by_same_party_rejected(client):
    biz, inf, camp, prop = _setup(client)
    contract = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()
    cid = contract["id"]
    client.post(f"/contracts/{cid}/sign", json={"signature": "Business Rep"}, headers=_headers(biz))
    r = client.post(f"/contracts/{cid}/sign", json={"signature": "Business Rep again"}, headers=_headers(biz))
    assert r.status_code == 400


def test_signing_a_cancelled_contract_is_refused_and_writes_nothing(client):
    """A cancelled contract is not signable, and the refusal leaves no trace.

    Its own code rather than contract_signed_immutable: this contract is not
    signed, it is over, and the two refusals point somewhere different. The
    second half matters more than the first — a refusal that still stamped the
    signature would be the worse bug, because the stamps are exactly what
    sign_contract reads to decide the contract is fully signed.
    """
    from app.modules.contracts import models as contracts

    biz, inf, camp, prop = _setup(client)
    cid = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()["id"]
    assert client.post(f"/contracts/{cid}/cancel", headers=_headers(biz)).status_code == 200

    db = client.session_factory()
    before = db.query(contracts.ContractEvent).filter(contracts.ContractEvent.contract_id == cid).count()
    db.close()

    r = client.post(f"/contracts/{cid}/sign", json={"signature": "Business Rep"}, headers=_headers(biz))
    assert r.status_code == 400
    assert r.json()["code"] == "contract_sign_cancelled"

    db = client.session_factory()
    contract = db.query(contracts.Contract).filter(contracts.Contract.id == cid).first()
    after = db.query(contracts.ContractEvent).filter(contracts.ContractEvent.contract_id == cid).count()
    db.close()
    assert contract.status == contracts.CANCELLED
    assert contract.business_signature is None
    assert contract.business_signed_at is None
    # No signed_business row was added on the way out of the refusal.
    assert after == before


def test_a_cancelled_contract_cannot_be_signed_back_to_life_by_the_other_party(client):
    """The actual exploit, end to end: sign, cancel, then sign anyway.

    The business signs, the creator calls the deal off — allowed, because it
    is not fully signed and no escrow exists against it — and then the creator
    signs after all. Without the guard that second signature completes the
    pair, the pair sets the status to signed, and payments.assert_fundable
    asks nothing except whether the status is signed: an ended deal becomes
    fundable, and the money is real.
    """
    from app.modules.contracts import models as contracts

    biz, inf, camp, prop = _setup(client)
    cid = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()["id"]
    assert client.post(f"/contracts/{cid}/sign", json={"signature": "Business Rep"},
                       headers=_headers(biz)).status_code == 200
    assert client.post(f"/contracts/{cid}/cancel", headers=_headers(inf)).status_code == 200

    r = client.post(f"/contracts/{cid}/sign", json={"signature": "The Creator"}, headers=_headers(inf))
    assert r.status_code == 400
    assert r.json()["code"] == "contract_sign_cancelled"

    db = client.session_factory()
    contract = db.query(contracts.Contract).filter(contracts.Contract.id == cid).first()
    events = [
        e.event
        for e in db.query(contracts.ContractEvent).filter(contracts.ContractEvent.contract_id == cid).all()
    ]
    db.close()
    # Still cancelled. The first signature stands as a record; the contract
    # does not become signed because of it.
    assert contract.status == contracts.CANCELLED
    assert contract.influencer_signature is None
    assert contract.influencer_signed_at is None
    assert "signed_influencer" not in events
    assert "fully_signed" not in events


def test_endpoints_require_auth(client):
    biz, inf, camp, prop = _setup(client)
    assert client.post(f"/contracts/from-proposal/{prop}").status_code == 401


def test_audit_trail_recorded(client):
    biz, inf, camp, prop = _setup(client)
    contract = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()
    cid = contract["id"]
    client.post(f"/contracts/{cid}/sign", json={"signature": "Business Rep"}, headers=_headers(biz))
    client.post(f"/contracts/{cid}/sign", json={"signature": "The Creator"}, headers=_headers(inf))
    from app.modules.contracts.models import ContractEvent
    db = client.session_factory()
    events = [e.event for e in db.query(ContractEvent).filter(ContractEvent.contract_id == cid).all()]
    db.close()
    assert "generated" in events
    assert "signed_business" in events
    assert "signed_influencer" in events
    assert "fully_signed" in events


def test_contract_by_proposal_lookup(client):
    biz, inf, camp, prop = _setup(client)
    created = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()
    found = client.get(f"/contracts/by-proposal/{prop}", headers=_headers(biz))
    assert found.status_code == 200
    assert found.json()["id"] == created["id"]
    # The influencer, a party, can also find it.
    assert client.get(f"/contracts/by-proposal/{prop}", headers=_headers(inf)).status_code == 200
    # A non-party cannot.
    assert client.get(f"/contracts/by-proposal/{prop}", headers=_headers("stranger")).status_code == 403


def test_contract_by_proposal_404_when_none(client):
    biz, inf, camp, prop = _setup(client)
    assert client.get(f"/contracts/by-proposal/{prop}", headers=_headers(biz)).status_code == 404


def test_list_my_contracts_for_both_parties(client):
    biz, inf, camp, prop = _setup(client)
    created = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz)).json()
    biz_list = client.get("/contracts/mine", headers=_headers(biz)).json()
    inf_list = client.get("/contracts/mine", headers=_headers(inf)).json()
    assert [c["id"] for c in biz_list] == [created["id"]]
    assert [c["id"] for c in inf_list] == [created["id"]]
    # A non-party sees none.
    assert client.get("/contracts/mine", headers=_headers("stranger")).json() == []


def test_list_my_contracts_carries_campaign_and_counterparty(client):
    """The card reads without opening the contract: the campaign it is for, and
    the OTHER party. No profiles exist in this setup, so the counterparty has
    no name yet — the row still carries the keys, as null, rather than dropping
    them or falling back to a user id or a phone number."""
    biz, inf, camp, prop = _setup(client)
    client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))

    biz_row = client.get("/contracts/mine", headers=_headers(biz)).json()[0]
    assert biz_row["campaign_title"] == "Launch push"
    assert biz_row["counterparty_name"] is None
    assert biz_row["counterparty_avatar_url"] is None
    assert biz_row["created_at"]

    # The creator's own view names the business as the counterparty (null here,
    # no profile) and never carries an avatar for it — a business has a company
    # name and no photo in this system.
    inf_row = client.get("/contracts/mine", headers=_headers(inf)).json()[0]
    assert inf_row["campaign_title"] == "Launch push"
    assert inf_row["counterparty_name"] is None
    assert inf_row["counterparty_avatar_url"] is None


# --------------------------------------------------------------------------
# W2: what may be turned into a contract at all
#
# generate_from_proposal used to ask two questions — is the live version
# `submitted`, and does a contract already exist — and three it did not, all
# of them upstream of money: whose offer is on the table, whether the campaign
# is still open, and whether the offer has lapsed.
#
# Every case below asserts the refusal AND that nothing was written. That
# second half is the one that matters: generation marks the chain `accepted`
# before it writes the contract, and an `accepted` chain is exactly what makes
# the creator's decline fail with order_not_open — so a refusal that still
# wrote would take the creator's way out with it.
# --------------------------------------------------------------------------


def _counter_from_business(client, camp, inf, rate_amount=8000):
    """Add a business-authored version to the chain, superseding the one below.

    What a buyer's counter-offer looks like on a brief, and the shape a direct
    order carries from the moment it is placed.
    """
    db = client.session_factory()
    try:
        previous = (
            db.query(campaigns.Proposal)
            .filter(campaigns.Proposal.campaign_id == camp)
            .order_by(campaigns.Proposal.version.desc())
            .first()
        )
        previous.status = campaigns.SUPERSEDED
        counter = campaigns.Proposal(
            campaign_id=camp,
            influencer_user_id=inf,
            version=previous.version + 1,
            rate_amount=rate_amount,
            rate_currency="XOF",
            timeline_days=7,
            author_role=campaigns.AUTHOR_BUSINESS,
            status=campaigns.SUBMITTED,
            # Carried forward, the way reply_to_proposal carries it.
            expires_at=previous.expires_at,
        )
        db.add(counter)
        db.commit()
        db.refresh(counter)
        return counter.id
    finally:
        db.close()


def _contracts_for(client, camp):
    from app.modules.contracts import models as contracts

    db = client.session_factory()
    try:
        return db.query(contracts.Contract).filter(contracts.Contract.campaign_id == camp).all()
    finally:
        db.close()


def _proposal_status(client, proposal_id):
    db = client.session_factory()
    try:
        return (
            db.query(campaigns.Proposal)
            .filter(campaigns.Proposal.id == proposal_id)
            .first()
            .status
        )
    finally:
        db.close()


def test_business_cannot_generate_a_contract_from_its_own_counter(client):
    """The buyer accepting its own offer, which is not an acceptance at all.

    Once the business counters, the live version is the business's own. Taking
    it through the contracts endpoint marked the chain accepted and wrote a
    contract on terms the creator never said yes to — and with the chain then
    `accepted`, the creator's decline came back order_not_open, so they could
    not turn the offer down through the order flow either.
    """
    biz, inf, camp, prop = _setup(client)
    counter = _counter_from_business(client, camp, inf)

    r = client.post(f"/contracts/from-proposal/{counter}", headers=_headers(biz))
    assert r.status_code == 400
    assert r.json()["code"] == "contract_own_offer"

    # The same refusal through the stale id the buyer's page may still hold:
    # generation resolves the chain to its latest version either way.
    stale = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))
    assert stale.status_code == 400
    assert stale.json()["code"] == "contract_own_offer"

    assert _contracts_for(client, camp) == []
    # Still an open offer, still waiting on the creator to answer it.
    assert _proposal_status(client, counter) == campaigns.SUBMITTED


def test_the_order_accept_path_still_generates_a_contract(client):
    """The one caller that may accept a business-authored offer.

    A direct order IS business-authored — the buyer named the terms — and the
    creator is the one saying yes. accept_direct_order passes the BUYER as the
    actor, because contract generation is written from the buyer's side, so
    the exemption has to be an explicit argument: who is calling cannot be
    read off the actor. This is the regression case proving the guard above
    did not close the real flow.
    """
    from app.modules.campaigns import orders
    from app.modules.contracts import models as contracts

    biz, inf, camp, prop = _setup(client)
    db = client.session_factory()
    try:
        campaign = db.query(campaigns.Campaign).filter(campaigns.Campaign.id == camp).first()
        campaign.is_direct = True
        db.add(
            campaigns.CampaignInvitation(
                campaign_id=camp, influencer_user_id=inf, status=campaigns.INVITED
            )
        )
        offer = db.query(campaigns.Proposal).filter(campaigns.Proposal.id == prop).first()
        offer.author_role = campaigns.AUTHOR_BUSINESS
        offer.expires_at = campaigns.utcnow() + timedelta(hours=48)
        db.commit()
    finally:
        db.close()

    db = client.session_factory()
    try:
        contract = orders.accept_direct_order(db, inf, prop)
    finally:
        db.close()

    assert contract["campaign_id"] == camp
    assert contract["status"] == contracts.PENDING
    assert [c.proposal_id for c in _contracts_for(client, camp)] == [prop]
    assert _proposal_status(client, prop) == campaigns.PROPOSAL_ACCEPTED


def test_a_cancelled_campaign_cannot_be_turned_into_a_contract(client):
    """The brief is off, and its proposals are still sitting there `submitted`.

    campaigns/editing.py cancel_campaign changes the campaign's status and
    leaves the proposals alone — it refuses only when a contract already
    exists. So without this guard a buyer could cancel a brief, let every
    invited creator be told it was cancelled, and then accept one of their
    proposals anyway. payments.assert_fundable never looks at the campaign, so
    the contract would sign and fund like any other.
    """
    biz, inf, camp, prop = _setup(client)
    db = client.session_factory()
    try:
        campaign = db.query(campaigns.Campaign).filter(campaigns.Campaign.id == camp).first()
        campaign.status = campaigns.CANCELLED
        db.commit()
    finally:
        db.close()

    r = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))
    assert r.status_code == 400
    assert r.json()["code"] == "contract_campaign_not_open"

    assert _contracts_for(client, camp) == []
    assert _proposal_status(client, prop) == campaigns.SUBMITTED


def test_an_expired_offer_cannot_be_turned_into_a_contract(client):
    """A lapsed direct order the sweep has not reached yet.

    expires_at bounds a direct order's accept window, and every counter in the
    chain inherits it rather than restarting the clock, so a negotiated order
    can lapse while still sitting at `submitted` — expire_stale_orders runs
    only when an admin triggers it.

    order_expired, not a contract-prefixed code of its own: it is the same
    rule on the same column as campaigns/orders.py, and it can only ever fire
    on a direct order, because a brief's proposals carry NULL there.
    """
    biz, inf, camp, prop = _setup(client)
    db = client.session_factory()
    try:
        offer = db.query(campaigns.Proposal).filter(campaigns.Proposal.id == prop).first()
        offer.expires_at = campaigns.utcnow() - timedelta(hours=1)
        db.commit()
    finally:
        db.close()

    r = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))
    assert r.status_code == 400
    assert r.json()["code"] == "order_expired"

    assert _contracts_for(client, camp) == []
    assert _proposal_status(client, prop) == campaigns.SUBMITTED


def test_the_ordinary_brief_acceptance_is_untouched(client):
    """Creator-authored, campaign published, no expiry: still a contract.

    All three guards have to stay false at once for the normal path, so this
    pins that they do — including that a brief's NULL expires_at is read as
    "never expires" rather than as a date already past.
    """
    biz, inf, camp, prop = _setup(client)
    db = client.session_factory()
    try:
        offer = db.query(campaigns.Proposal).filter(campaigns.Proposal.id == prop).first()
        assert offer.author_role == campaigns.AUTHOR_INFLUENCER
        assert offer.expires_at is None
    finally:
        db.close()

    r = client.post(f"/contracts/from-proposal/{prop}", headers=_headers(biz))
    assert r.status_code == 201
    assert [c.proposal_id for c in _contracts_for(client, camp)] == [prop]
    assert _proposal_status(client, prop) == campaigns.PROPOSAL_ACCEPTED

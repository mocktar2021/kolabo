"""Taking things back, and the exact point at which you no longer can.

One rule, three places: you may withdraw what you offered until the other side
has spent something on it — an evening pricing a brief, a signature, money.
Each refusal below is the moment that line is crossed.
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
from app.modules.campaigns import models as campaigns
from app.modules.campaigns.router import router as campaigns_router
from app.modules.contracts import models as contracts
from app.modules.contracts.router import router as contracts_router
from app.modules.payments import models as payments


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
    app.include_router(campaigns_router, prefix="/campaigns")
    app.include_router(contracts_router, prefix="/contracts")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


@pytest.fixture()
def world(client):
    """A brand, a creator, a published brief, and an open invitation."""
    db = client.session_factory()
    try:
        biz = User(phone="+22990060001", password_hash="x", country_code="BJ",
                   role="business", is_verified=True)
        inf = User(phone="+22990060002", password_hash="x", country_code="BJ",
                   role="influencer", is_verified=True)
        other = User(phone="+22990060003", password_hash="x", country_code="BJ",
                     role="influencer", is_verified=True)
        db.add_all([biz, inf, other]); db.commit()
        db.refresh(biz); db.refresh(inf); db.refresh(other)
        camp = campaigns.Campaign(
            business_user_id=biz.id, title="Launch push", budget_amount=500000,
            budget_currency="XOF",
            deliverables=[{"platform": "instagram", "type": "post", "quantity": 1}],
            status=campaigns.PUBLISHED,
        )
        db.add(camp); db.commit(); db.refresh(camp)
        inv = campaigns.CampaignInvitation(
            campaign_id=camp.id, influencer_user_id=inf.id, status=campaigns.INVITED
        )
        db.add(inv); db.commit(); db.refresh(inv)
        return {
            "biz": biz.id, "inf": inf.id, "other": other.id,
            "campaign": camp.id, "invitation": inv.id,
        }
    finally:
        db.close()


def _proposal(client, world, status=campaigns.SUBMITTED, author=campaigns.AUTHOR_INFLUENCER,
              version=1, creator=None):
    db = client.session_factory()
    try:
        p = campaigns.Proposal(
            campaign_id=world["campaign"], influencer_user_id=creator or world["inf"],
            version=version, rate_amount=40000, rate_currency="XOF", timeline_days=7,
            author_role=author, status=status,
        )
        db.add(p); db.commit(); db.refresh(p)
        return p.id
    finally:
        db.close()


def _contract(client, world, proposal_id, status=contracts.PENDING):
    db = client.session_factory()
    try:
        c = contracts.Contract(
            campaign_id=world["campaign"], proposal_id=proposal_id,
            business_user_id=world["biz"], influencer_user_id=world["inf"],
            language="fr", body="placeholder", rate_amount=40000, rate_currency="XOF",
            timeline_days=7, deliverables=[], status=status,
        )
        db.add(c); db.commit(); db.refresh(c)
        return c.id
    finally:
        db.close()


def _direct_order(client, world):
    """A hidden single-creator campaign with the buyer's offer on it, as
    campaigns.service._place_order builds one."""
    db = client.session_factory()
    try:
        camp = campaigns.Campaign(
            business_user_id=world["biz"], title="1 IG Post", budget_amount=30000,
            budget_currency="XOF", deliverables=[], status=campaigns.PUBLISHED,
            is_direct=True,
        )
        db.add(camp); db.commit(); db.refresh(camp)
        inv = campaigns.CampaignInvitation(
            campaign_id=camp.id, influencer_user_id=world["inf"], status=campaigns.INVITED
        )
        db.add(inv)
        p = campaigns.Proposal(
            campaign_id=camp.id, influencer_user_id=world["inf"], version=1,
            rate_amount=30000, rate_currency="XOF", timeline_days=7,
            author_role=campaigns.AUTHOR_BUSINESS, status=campaigns.SUBMITTED,
        )
        db.add(p); db.commit(); db.refresh(p); db.refresh(inv)
        return {"campaign": camp.id, "proposal": p.id, "invitation": inv.id}
    finally:
        db.close()


def _invitation_status(client, invitation_id):
    db = client.session_factory()
    try:
        return db.query(campaigns.CampaignInvitation).filter(
            campaigns.CampaignInvitation.id == invitation_id
        ).first().status
    finally:
        db.close()


# --------------------------------------------------------------------------
# Withdrawing an invitation
# --------------------------------------------------------------------------


def test_the_owner_can_withdraw_an_unanswered_invitation(client, world):
    r = client.delete(
        f"/campaigns/{world['campaign']}/invitations/{world['invitation']}",
        headers=_headers(world["biz"]),
    )
    assert r.status_code == 200
    assert r.json()["status"] == campaigns.WITHDRAWN
    # The row is kept, not deleted: the creator's half of the record stays.
    assert _invitation_status(client, world["invitation"]) == campaigns.WITHDRAWN


def test_withdrawn_is_not_declined(client, world):
    """Declined says the creator said no. Nobody said no here, and a refusal
    they never made must not land on their record."""
    client.delete(
        f"/campaigns/{world['campaign']}/invitations/{world['invitation']}",
        headers=_headers(world["biz"]),
    )
    assert _invitation_status(client, world["invitation"]) != campaigns.DECLINED


def test_withdrawing_after_the_creator_proposed_is_400(client, world):
    """They priced the brief. What is on the table is now an offer that
    deserves an answer, not an invitation to retract."""
    _proposal(client, world)
    r = client.delete(
        f"/campaigns/{world['campaign']}/invitations/{world['invitation']}",
        headers=_headers(world["biz"]),
    )
    assert r.status_code == 400
    assert "proposal" in r.json()["detail"].lower()
    assert _invitation_status(client, world["invitation"]) == campaigns.INVITED


def test_a_superseded_proposal_still_blocks_the_withdrawal(client, world):
    """The question is whether they did the work, not whether the version is
    live. Four rounds of negotiation is four evenings."""
    _proposal(client, world, status=campaigns.SUPERSEDED)
    r = client.delete(
        f"/campaigns/{world['campaign']}/invitations/{world['invitation']}",
        headers=_headers(world["biz"]),
    )
    assert r.status_code == 400


def test_withdrawing_twice_is_400(client, world):
    path = f"/campaigns/{world['campaign']}/invitations/{world['invitation']}"
    assert client.delete(path, headers=_headers(world["biz"])).status_code == 200
    # Refused rather than a no-op: a second "this is off" for something
    # already off is a notification nobody should get.
    assert client.delete(path, headers=_headers(world["biz"])).status_code == 400


def test_only_the_campaign_owner_can_withdraw_an_invitation(client, world):
    r = client.delete(
        f"/campaigns/{world['campaign']}/invitations/{world['invitation']}",
        headers=_headers(world["inf"]),
    )
    assert r.status_code == 403


def test_an_unknown_invitation_is_404(client, world):
    r = client.delete(
        f"/campaigns/{world['campaign']}/invitations/nope",
        headers=_headers(world["biz"]),
    )
    assert r.status_code == 404


def test_a_direct_orders_invitation_cannot_be_withdrawn(client, world):
    """An order always carries the buyer's own proposal, so the priced-it
    guard catches it. Correct: an order is closed by the creator's decline,
    not by the buyer deleting the invitation out from under it."""
    order = _direct_order(client, world)
    r = client.delete(
        f"/campaigns/{order['campaign']}/invitations/{order['invitation']}",
        headers=_headers(world["biz"]),
    )
    assert r.status_code == 400


# --------------------------------------------------------------------------
# Withdrawing a proposal
# --------------------------------------------------------------------------


def test_the_creator_can_withdraw_their_live_proposal(client, world):
    pid = _proposal(client, world)
    r = client.post(f"/campaigns/proposals/{pid}/withdraw", headers=_headers(world["inf"]))
    assert r.status_code == 200
    assert r.json()["status"] == campaigns.WITHDRAWN


def test_withdrawing_someone_elses_proposal_is_403(client, world):
    pid = _proposal(client, world)
    r = client.post(f"/campaigns/proposals/{pid}/withdraw", headers=_headers(world["other"]))
    assert r.status_code == 403


def test_withdrawing_a_superseded_proposal_is_400(client, world):
    """It is not the offer on the table any more, so there is nothing left on
    it to take back."""
    pid = _proposal(client, world, status=campaigns.SUPERSEDED)
    r = client.post(f"/campaigns/proposals/{pid}/withdraw", headers=_headers(world["inf"]))
    assert r.status_code == 400


def test_withdrawing_once_a_contract_exists_is_400(client, world):
    """The terms have left the negotiation and become an agreement. Unwinding
    that is the contract cancel path, which knows about escrow."""
    pid = _proposal(client, world)
    _contract(client, world, pid)
    r = client.post(f"/campaigns/proposals/{pid}/withdraw", headers=_headers(world["inf"]))
    assert r.status_code == 400
    assert "contract" in r.json()["detail"].lower()


def test_a_direct_order_is_refused_and_sent_to_decline(client, world):
    """Not a back door around decline. decline_direct_order also cancels the
    hidden campaign, moves the invitation and tells the buyer they were not
    charged; a withdraw that skipped all that would leave the order looking
    live in the buyer's list with nothing behind it."""
    order = _direct_order(client, world)
    r = client.post(
        f"/campaigns/proposals/{order['proposal']}/withdraw", headers=_headers(world["inf"])
    )
    assert r.status_code == 400
    assert "decline" in r.json()["detail"].lower()

    # And the order is untouched: still open, still answerable.
    db = client.session_factory()
    try:
        p = db.query(campaigns.Proposal).filter(
            campaigns.Proposal.id == order["proposal"]
        ).first()
        assert p.status == campaigns.SUBMITTED
    finally:
        db.close()


def test_withdrawing_an_unknown_proposal_is_404(client, world):
    assert client.post(
        "/campaigns/proposals/nope/withdraw", headers=_headers(world["inf"])
    ).status_code == 404


# --------------------------------------------------------------------------
# Cancelling a contract
# --------------------------------------------------------------------------


def test_either_party_can_cancel_an_unsigned_contract(client, world):
    """Nothing is owed in either direction yet, and a creator who cannot
    deliver should be able to say so rather than going quiet."""
    for actor, tag in (("biz", "a"), ("inf", "b")):
        pid = _proposal(client, world, version=1 if tag == "a" else 2)
        cid = _contract(client, world, pid)
        r = client.post(f"/contracts/{cid}/cancel", headers=_headers(world[actor]))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == contracts.CANCELLED
        assert r.json()["fully_signed"] is False


def test_cancelling_writes_the_contract_event(client, world):
    """This is the one module that keeps an audit trail, and a contract that
    ends with no row saying who ended it cannot settle an argument later."""
    pid = _proposal(client, world)
    cid = _contract(client, world, pid)
    client.post(f"/contracts/{cid}/cancel", headers=_headers(world["biz"]))

    db = client.session_factory()
    try:
        events = db.query(contracts.ContractEvent).filter(
            contracts.ContractEvent.contract_id == cid
        ).all()
        assert [e.event for e in events] == ["cancelled"]
        assert events[0].actor_user_id == world["biz"]
    finally:
        db.close()


def test_cancelling_a_fully_signed_contract_is_400(client, world):
    """Both parties put their name to these terms. A button that walks out of
    that is the thing a contract exists to prevent."""
    pid = _proposal(client, world)
    cid = _contract(client, world, pid, status=contracts.SIGNED)
    r = client.post(f"/contracts/{cid}/cancel", headers=_headers(world["biz"]))
    assert r.status_code == 400


def test_cancelling_a_funded_contract_is_409(client, world):
    """Money at the provider makes this a question about who is owed what,
    which is the dispute path's business and has rules — a split, commission
    on the released part only, an admin, an audit log."""
    pid = _proposal(client, world)
    cid = _contract(client, world, pid)
    db = client.session_factory()
    try:
        now = payments.utcnow()
        db.add(payments.Escrow(
            contract_id=cid, campaign_id=world["campaign"], business_user_id=world["biz"],
            influencer_user_id=world["inf"], amount=40000, currency="XOF", provider="mock",
            provider_fund_ref="ref-1", status=payments.HELD, held_at=now, due_release_at=now,
        ))
        db.commit()
    finally:
        db.close()

    r = client.post(f"/contracts/{cid}/cancel", headers=_headers(world["biz"]))
    assert r.status_code == 409
    assert "dispute" in r.json()["detail"].lower()


def test_cancelling_twice_is_400(client, world):
    pid = _proposal(client, world)
    cid = _contract(client, world, pid)
    assert client.post(f"/contracts/{cid}/cancel", headers=_headers(world["biz"])).status_code == 200
    assert client.post(f"/contracts/{cid}/cancel", headers=_headers(world["biz"])).status_code == 400


def test_a_stranger_cannot_cancel_a_contract(client, world):
    pid = _proposal(client, world)
    cid = _contract(client, world, pid)
    r = client.post(f"/contracts/{cid}/cancel", headers=_headers(world["other"]))
    assert r.status_code == 403


def test_cancelling_an_unknown_contract_is_404(client, world):
    assert client.post(
        "/contracts/nope/cancel", headers=_headers(world["biz"])
    ).status_code == 404


def test_all_three_need_auth(client, world):
    assert client.delete(
        f"/campaigns/{world['campaign']}/invitations/{world['invitation']}"
    ).status_code == 401
    assert client.post("/campaigns/proposals/x/withdraw").status_code == 401
    assert client.post("/contracts/x/cancel").status_code == 401

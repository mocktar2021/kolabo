"""Taking things back, and the exact point at which you no longer can.

One rule, three places: you may withdraw what you offered until the other side
has spent something on it — an evening pricing a brief, a signature, money.
Each refusal below is the moment that line is crossed.

The last section is the fourth ending and the only one nobody chooses: a brief
that FINISHED. It closes what is still open for the same reason the three
above refuse — an offer nobody can answer any more should not sit on either
party's screen looking live.
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
from app.modules.campaigns import completion
from app.modules.campaigns import models as campaigns
from app.modules.campaigns.router import router as campaigns_router
from app.modules.contracts import models as contracts
from app.modules.contracts.router import router as contracts_router
from app.modules.notifications.models import Notification
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
        biz = User(phone="+22990060001", email="22990060001@kolabo.test", password_hash="x", country_code="BJ",
                   role="business", is_verified=True)
        inf = User(phone="+22990060002", email="22990060002@kolabo.test", password_hash="x", country_code="BJ",
                   role="influencer", is_verified=True)
        other = User(phone="+22990060003", email="22990060003@kolabo.test", password_hash="x", country_code="BJ",
                     role="influencer", is_verified=True)
        db.add_all([biz, inf, other]); db.commit()
        db.refresh(biz); db.refresh(inf); db.refresh(other)
        camp = campaigns.Campaign(
            business_user_id=biz.id, title="Launch push", budget_amount=500000,
            budget_currency="XOF",
            deliverables=[{"platform": "instagram", "type": "post", "quantity": 1}],
            status=campaigns.PUBLISHED,
            is_open=True,
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


def _escrow(client, world, contract_id, status=payments.RELEASED):
    """An escrow on a contract, in a given state, written directly.

    Straight to the table rather than through the funding endpoint: this file
    mounts no payments router, and what the completion rule reads is the
    escrow's STATUS and nothing else about how it got there. test_payments.py
    owns the real release path, and pins the same completion from that end.
    """
    db = client.session_factory()
    try:
        now = payments.utcnow()
        db.add(payments.Escrow(
            contract_id=contract_id, campaign_id=world["campaign"],
            business_user_id=world["biz"], influencer_user_id=world["inf"],
            amount=40000, currency="XOF", provider="mock", provider_fund_ref="ref",
            status=status, held_at=now, due_release_at=now,
        ))
        db.commit()
    finally:
        db.close()


def _complete(client, world):
    """Run the hook the way every call site runs it, and say whether it moved."""
    db = client.session_factory()
    try:
        return completion.maybe_complete_campaign(db, world["campaign"])
    finally:
        db.close()


def _campaign_status(client, campaign_id):
    db = client.session_factory()
    try:
        return db.query(campaigns.Campaign).filter(
            campaigns.Campaign.id == campaign_id
        ).first().status
    finally:
        db.close()


def _proposal_status(client, proposal_id):
    db = client.session_factory()
    try:
        return db.query(campaigns.Proposal).filter(
            campaigns.Proposal.id == proposal_id
        ).first().status
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


def _rows_of(client, model, campaign_id):
    """Every row of one model hanging off one campaign — the "and nothing was
    written" half of a refusal."""
    db = client.session_factory()
    try:
        return db.query(model).filter(model.campaign_id == campaign_id).all()
    finally:
        db.close()


def _notifications(client, user_id, key=None):
    db = client.session_factory()
    try:
        rows = db.query(Notification).filter(Notification.user_id == user_id).all()
        if key is None:
            return rows
        return [n for n in rows if (n.params or {}).get("key") == key]
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


# --------------------------------------------------------------------------
# A campaign that finished
# --------------------------------------------------------------------------


def test_a_brief_whose_only_deal_was_paid_out_is_completed(client, world):
    """The rule, in its simplest shape: every contract ended, and the ending
    was the money. Same predicate the web client files rows under Completed
    with (web/src/lib/lifecycle.ts), now decided on the server."""
    pid = _proposal(client, world)
    cid = _contract(client, world, pid, status=contracts.SIGNED)
    _escrow(client, world, cid, status=payments.RELEASED)

    assert _complete(client, world) is True
    assert _campaign_status(client, world["campaign"]) == campaigns.COMPLETED


def test_a_refunded_escrow_finishes_the_brief_too(client, world):
    """Refunded is an ending the money reached, exactly as released is. The
    brand got its money back; there is nothing left running underneath."""
    pid = _proposal(client, world)
    cid = _contract(client, world, pid, status=contracts.SIGNED)
    _escrow(client, world, cid, status=payments.REFUNDED)

    assert _complete(client, world) is True
    assert _campaign_status(client, world["campaign"]) == campaigns.COMPLETED


@pytest.mark.parametrize("escrow_status", [payments.HELD, payments.DISPUTED])
def test_an_unfinished_contract_keeps_the_brief_published(client, world, escrow_status):
    """Held money is a job still running and disputed money is a job actively
    going wrong. Neither is an ending, and one creator still delivering keeps
    the whole brief live."""
    pid = _proposal(client, world)
    cid = _contract(client, world, pid, status=contracts.SIGNED)
    _escrow(client, world, cid, status=escrow_status)

    assert _complete(client, world) is False
    assert _campaign_status(client, world["campaign"]) == campaigns.PUBLISHED


def test_a_second_live_contract_holds_the_whole_brief_open(client, world):
    """EVERY contract has to have ended. One paid out and one still held is a
    brief with work outstanding, however finished the other half looks."""
    done = _contract(client, world, _proposal(client, world), status=contracts.SIGNED)
    _escrow(client, world, done, status=payments.RELEASED)
    still_running = _contract(
        client, world, _proposal(client, world, version=2, creator=world["other"]),
        status=contracts.SIGNED,
    )
    db = client.session_factory()
    try:
        now = payments.utcnow()
        db.add(payments.Escrow(
            contract_id=still_running, campaign_id=world["campaign"],
            business_user_id=world["biz"], influencer_user_id=world["other"],
            amount=40000, currency="XOF", provider="mock", provider_fund_ref="ref-2",
            status=payments.HELD, held_at=now, due_release_at=now,
        ))
        db.commit()
    finally:
        db.close()

    assert _complete(client, world) is False
    assert _campaign_status(client, world["campaign"]) == campaigns.PUBLISHED


def test_a_deal_that_fell_through_before_any_money_is_not_a_finished_brief(client, world):
    """THE HALF OF THE RULE THAT IS EASY TO DROP. Every contract has ended —
    the one contract was cancelled — but nothing was ever paid, so nothing was
    completed here: something was abandoned, and the brand can still work the
    brief."""
    pid = _proposal(client, world)
    _contract(client, world, pid, status=contracts.CANCELLED)

    assert _complete(client, world) is False
    assert _campaign_status(client, world["campaign"]) == campaigns.PUBLISHED


def test_a_brief_nobody_contracted_on_is_never_finished(client, world):
    """No contracts at all is not an ending, it is a brief still waiting for
    somebody. The brand has something left to do either way."""
    _proposal(client, world)
    assert _complete(client, world) is False
    assert _campaign_status(client, world["campaign"]) == campaigns.PUBLISHED


def test_completing_twice_changes_nothing_the_second_time(client, world):
    """The hook is called from every path a contract can end on, and several
    of those can fire against one brief. The second call has to be a no-op —
    not a second round of notifications for creators who already heard."""
    pid = _proposal(client, world, creator=world["other"])
    cid = _contract(client, world, _proposal(client, world), status=contracts.SIGNED)
    _escrow(client, world, cid, status=payments.RELEASED)

    assert _complete(client, world) is True
    before = len(_notifications(client, world["other"]))

    assert _complete(client, world) is False
    assert _campaign_status(client, world["campaign"]) == campaigns.COMPLETED
    assert _proposal_status(client, pid) == campaigns.PROPOSAL_REJECTED
    assert len(_notifications(client, world["other"])) == before


def test_finishing_closes_the_open_bids_and_tells_those_creators(client, world):
    """The cascade. A brief that filled leaves other creators holding offers
    nobody will ever answer; closing them silently is how a creator ends up
    chasing a decision that was made without them."""
    losing_bid = _proposal(client, world, creator=world["other"])
    cid = _contract(client, world, _proposal(client, world), status=contracts.SIGNED)
    _escrow(client, world, cid, status=payments.RELEASED)

    assert _complete(client, world) is True

    # Rejected, not withdrawn: the creator took nothing back, the buyer walked
    # away from the bid. It is also one of the three terminal resolutions
    # submit_proposal refuses to reopen.
    assert _proposal_status(client, losing_bid) == campaigns.PROPOSAL_REJECTED
    filled = _notifications(client, world["other"], key="brief_filled")
    assert len(filled) == 1
    assert filled[0].type == "proposal_closed"
    assert filled[0].link == "/invitations"


def test_finishing_withdraws_the_invitations_nobody_answered(client, world):
    """An open invitation on a filled brief is a request for work that no
    longer exists. Withdrawn rather than declined: nobody said no."""
    cid = _contract(client, world, _proposal(client, world), status=contracts.SIGNED)
    _escrow(client, world, cid, status=payments.RELEASED)

    assert _complete(client, world) is True
    assert _invitation_status(client, world["invitation"]) == campaigns.WITHDRAWN
    assert _invitation_status(client, world["invitation"]) != campaigns.DECLINED


def test_an_accepted_chain_is_not_reopened_or_rewritten(client, world):
    """Only the chains still on the table are closed. The bid that WON is
    accepted and stays accepted — the contract was written from it."""
    winner = _proposal(client, world, status=campaigns.PROPOSAL_ACCEPTED)
    cid = _contract(client, world, winner, status=contracts.SIGNED)
    _escrow(client, world, cid, status=payments.RELEASED)

    assert _complete(client, world) is True
    assert _proposal_status(client, winner) == campaigns.PROPOSAL_ACCEPTED


def test_cancelling_the_last_open_contract_finishes_the_brief(client, world):
    """END TO END, through a real endpoint: the hook is wired into the service
    layer, so cancelling the second contract on a brief whose first one paid
    out finishes the campaign without the router knowing anything about it."""
    paid = _contract(client, world, _proposal(client, world), status=contracts.SIGNED)
    _escrow(client, world, paid, status=payments.RELEASED)
    unfunded = _contract(client, world, _proposal(client, world, version=2, creator=world["other"]))

    r = client.post(f"/contracts/{unfunded}/cancel", headers=_headers(world["biz"]))
    assert r.status_code == 200, r.text
    assert _campaign_status(client, world["campaign"]) == campaigns.COMPLETED


def test_a_cancelled_brief_is_never_rewritten_as_completed(client, world):
    """Cancelled and completed are different facts about the same row and the
    difference is the record: one brief finished, the other was called off.
    The client files both under its Completed shelf, which is a statement about
    tabs and not one this may act on."""
    db = client.session_factory()
    try:
        camp = db.query(campaigns.Campaign).filter(
            campaigns.Campaign.id == world["campaign"]
        ).first()
        camp.status = campaigns.CANCELLED
        db.commit()
    finally:
        db.close()
    cid = _contract(client, world, _proposal(client, world), status=contracts.SIGNED)
    _escrow(client, world, cid, status=payments.RELEASED)

    assert _complete(client, world) is False
    assert _campaign_status(client, world["campaign"]) == campaigns.CANCELLED


def test_a_draft_is_never_completed(client, world):
    """Nobody has seen it. Whatever rows a fixture or a backfill hung off it,
    a draft is not a brief that finished."""
    db = client.session_factory()
    try:
        camp = db.query(campaigns.Campaign).filter(
            campaigns.Campaign.id == world["campaign"]
        ).first()
        camp.status = campaigns.DRAFT
        db.commit()
    finally:
        db.close()
    cid = _contract(client, world, _proposal(client, world), status=contracts.SIGNED)
    _escrow(client, world, cid, status=payments.RELEASED)

    assert _complete(client, world) is False
    assert _campaign_status(client, world["campaign"]) == campaigns.DRAFT


def test_a_missing_campaign_is_silent(client, world):
    """Contracts carry a campaign_id and nothing enforces a row behind it. A
    hook deep in the payment path must not turn a successful release into a
    500 over a brief that was never written."""
    db = client.session_factory()
    try:
        assert completion.maybe_complete_campaign(db, "no-such-campaign") is False
    finally:
        db.close()


# --------------------------------------------------------------------------
# What a finished brief refuses
# --------------------------------------------------------------------------


def _finish(client, world):
    """A brief taken all the way to completed, through the rule."""
    cid = _contract(client, world, _proposal(client, world), status=contracts.SIGNED)
    _escrow(client, world, cid, status=payments.RELEASED)
    assert _complete(client, world) is True


def test_a_finished_brief_takes_no_new_proposal(client, world):
    """Closed BY CONSTRUCTION: submit_proposal has always required PUBLISHED,
    so the new status refuses a bid on a filled brief without a guard of its
    own. Asserted rather than assumed — it is the whole reason the campaign
    needed a terminal status."""
    _finish(client, world)
    before = len(_rows_of(client, campaigns.Proposal, world["campaign"]))

    r = client.post(
        f"/campaigns/{world['campaign']}/proposals",
        json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7},
        headers=_headers(world["other"]),
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Campaign is not open for proposals"
    # The other half: nothing was written.
    assert len(_rows_of(client, campaigns.Proposal, world["campaign"])) == before


def test_a_finished_brief_takes_no_new_invitation(client, world):
    """The same construction on the buyer's side: invite_influencer requires
    PUBLISHED, so a filled brief cannot go out to anybody new."""
    _finish(client, world)
    before = len(_rows_of(client, campaigns.CampaignInvitation, world["campaign"]))

    r = client.post(
        f"/campaigns/{world['campaign']}/invitations",
        json={"influencer_id": world["other"]},
        headers=_headers(world["biz"]),
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Publish the campaign before inviting"
    assert len(_rows_of(client, campaigns.CampaignInvitation, world["campaign"])) == before


def test_a_live_brief_still_takes_both(client, world):
    """The happy path is untouched. A published brief with a contract on it
    that has NOT finished still behaves exactly as it did."""
    r = client.post(
        f"/campaigns/{world['campaign']}/proposals",
        json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7},
        headers=_headers(world["other"]),
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == campaigns.SUBMITTED

    invited = client.post(
        f"/campaigns/{world['campaign']}/invitations",
        json={"influencer_id": world["other"]},
        headers=_headers(world["biz"]),
    )
    assert invited.status_code == 201, invited.text
    assert invited.json()["status"] == campaigns.INVITED


def test_all_three_need_auth(client, world):
    assert client.delete(
        f"/campaigns/{world['campaign']}/invitations/{world['invitation']}"
    ).status_code == 401
    assert client.post("/campaigns/proposals/x/withdraw").status_code == 401
    assert client.post("/contracts/x/cancel").status_code == 401

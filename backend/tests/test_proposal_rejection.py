"""The brand saying no, which is the answer it did not have.

`rejected` has been a proposal status since the table was written and nothing
wrote it until the completion cascade started closing filled briefs — a status
reachable only as a side effect of somebody else's deal being paid. Meanwhile
the invitation refusal was telling buyers to "reply to it or reject it" and the
submit guard was refusing to reopen a rejected chain, so two parts of the
system already assumed a decision that could not be made.

Every refusal below asserts BOTH halves: the refusal, and that nothing moved —
the proposal still says what it said and the creator was told nothing. A
rejection that half-happens is worse than one that does not happen, because the
creator's screen and the brand's stop agreeing about whether the offer is live.

Kept out of test_cancellations.py, which is about taking things back. Rejecting
is not taking anything back: nobody is withdrawing their own offer here, the
brand is answering somebody else's, and models.py keeps the three endings apart
for exactly that reason.
"""
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
from app.modules.campaigns.router import router as campaigns_router
from app.modules.contracts import models as contracts
from app.modules.notifications.models import Notification


@pytest.fixture()
def client():
    """A throwaway app with the REAL error handler on it.

    Registered from app.core.errors, not re-declared here, for the reason
    test_error_codes.py gives: a handler that merely resembles the production
    one is a test that stays green while the wiring is wrong. Without it
    `code` never reaches the response and every assertion below would have to
    be made against an English sentence instead — which is the thing a code
    exists so that nobody has to do.
    """
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
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(campaigns_router, prefix="/campaigns")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


@pytest.fixture()
def world(client):
    """A brand, two creators, a rival brand, and a published open brief."""
    db = client.session_factory()
    try:
        biz = User(phone="+22990070001", email="22990070001@kolabo.test", password_hash="x", country_code="BJ",
                   role="business", is_verified=True)
        rival = User(phone="+22990070002", email="22990070002@kolabo.test", password_hash="x", country_code="BJ",
                     role="business", is_verified=True)
        inf = User(phone="+22990070003", email="22990070003@kolabo.test", password_hash="x", country_code="BJ",
                   role="influencer", is_verified=True)
        other = User(phone="+22990070004", email="22990070004@kolabo.test", password_hash="x", country_code="BJ",
                     role="influencer", is_verified=True)
        db.add_all([biz, rival, inf, other]); db.commit()
        for u in (biz, rival, inf, other):
            db.refresh(u)
        camp = campaigns.Campaign(
            business_user_id=biz.id, title="Launch push", budget_amount=500000,
            budget_currency="XOF",
            deliverables=[{"platform": "instagram", "type": "post", "quantity": 1}],
            status=campaigns.PUBLISHED,
            is_open=True,
        )
        db.add(camp); db.commit(); db.refresh(camp)
        return {
            "biz": biz.id, "rival": rival.id, "inf": inf.id, "other": other.id,
            "campaign": camp.id,
        }
    finally:
        db.close()


def _proposal(client, world, status=campaigns.SUBMITTED, author=campaigns.AUTHOR_INFLUENCER,
              version=1, creator=None, campaign=None):
    db = client.session_factory()
    try:
        p = campaigns.Proposal(
            campaign_id=campaign or world["campaign"],
            influencer_user_id=creator or world["inf"],
            version=version, rate_amount=40000, rate_currency="XOF", timeline_days=7,
            author_role=author, status=status,
        )
        db.add(p); db.commit(); db.refresh(p)
        return p.id
    finally:
        db.close()


def _contract(client, world, proposal_id, creator=None, status=contracts.PENDING):
    """A contract on the brief, written straight to the table.

    This file mounts no contracts router: what the guard reads is whether a
    row EXISTS for this chain, not how it got there, and test_contracts.py owns
    the real generation path.
    """
    db = client.session_factory()
    try:
        c = contracts.Contract(
            campaign_id=world["campaign"], proposal_id=proposal_id,
            business_user_id=world["biz"], influencer_user_id=creator or world["inf"],
            language="fr", body="placeholder", rate_amount=40000, rate_currency="XOF",
            timeline_days=7, deliverables=[], status=status,
        )
        db.add(c); db.commit(); db.refresh(c)
        return c.id
    finally:
        db.close()


def _direct_order(client, world):
    """A hidden single-creator campaign carrying the buyer's own offer, plus
    the creator's counter on top of it — the shape a brand would be looking at
    when it wanted to say no to an order."""
    db = client.session_factory()
    try:
        camp = campaigns.Campaign(
            business_user_id=world["biz"], title="1 IG Post", budget_amount=30000,
            budget_currency="XOF", deliverables=[], status=campaigns.PUBLISHED,
            is_direct=True,
        )
        db.add(camp); db.commit(); db.refresh(camp)
        db.add(campaigns.CampaignInvitation(
            campaign_id=camp.id, influencer_user_id=world["inf"], status=campaigns.INVITED
        ))
        offer = campaigns.Proposal(
            campaign_id=camp.id, influencer_user_id=world["inf"], version=1,
            rate_amount=30000, rate_currency="XOF", timeline_days=7,
            author_role=campaigns.AUTHOR_BUSINESS, status=campaigns.SUPERSEDED,
        )
        counter = campaigns.Proposal(
            campaign_id=camp.id, influencer_user_id=world["inf"], version=2,
            rate_amount=45000, rate_currency="XOF", timeline_days=7,
            author_role=campaigns.AUTHOR_INFLUENCER, status=campaigns.SUBMITTED,
        )
        db.add_all([offer, counter]); db.commit(); db.refresh(counter)
        return {"campaign": camp.id, "proposal": counter.id}
    finally:
        db.close()


def _set_campaign_status(client, campaign_id, new_status):
    db = client.session_factory()
    try:
        db.query(campaigns.Campaign).filter(
            campaigns.Campaign.id == campaign_id
        ).first().status = new_status
        db.commit()
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


def _notifications(client, user_id, key=None):
    db = client.session_factory()
    try:
        rows = db.query(Notification).filter(Notification.user_id == user_id).all()
        if key is None:
            return rows
        return [n for n in rows if (n.params or {}).get("key") == key]
    finally:
        db.close()


def _reject(client, world, proposal_id, actor="biz", campaign=None):
    return client.post(
        f"/campaigns/{campaign or world['campaign']}/proposals/{proposal_id}/reject",
        headers=_headers(world[actor]),
    )


def _untouched(client, world, proposal_id, was=campaigns.SUBMITTED, creator=None):
    """The other half of every refusal: the row still says what it said, and
    the creator was told nothing."""
    assert _proposal_status(client, proposal_id) == was
    assert _notifications(client, creator or world["inf"]) == []


# --------------------------------------------------------------------------
# The decision itself
# --------------------------------------------------------------------------


def test_the_owner_can_reject_the_live_proposal(client, world):
    pid = _proposal(client, world)
    r = _reject(client, world, pid)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == campaigns.PROPOSAL_REJECTED
    assert _proposal_status(client, pid) == campaigns.PROPOSAL_REJECTED


def test_rejected_is_not_withdrawn_and_not_declined(client, world):
    """Three endings, three records. Withdrawn says the author took their own
    offer back and declined says a creator turned down a purchase; neither
    happened here, and putting either on somebody's record would describe an
    act they never performed."""
    pid = _proposal(client, world)
    assert _reject(client, world, pid).status_code == 200
    status = _proposal_status(client, pid)
    assert status not in (campaigns.WITHDRAWN, campaigns.PROPOSAL_DECLINED)
    assert status == campaigns.PROPOSAL_REJECTED


def test_the_creator_is_told(client, world):
    """A creator who is never told reads silence as a decision still pending,
    and chases it. The row routes to their own invitations, because
    /campaigns/{id} is the brand's screen and a 403 for them."""
    pid = _proposal(client, world)
    assert _reject(client, world, pid).status_code == 200

    told = _notifications(client, world["inf"], key="proposal_rejected")
    assert len(told) == 1
    assert told[0].type == "proposal_closed"
    assert told[0].link == "/invitations"
    # The stored English is also what goes out by email, where there is no
    # client to render the localised body.
    assert told[0].message == "Your proposal was not selected."


def test_the_brand_is_not_notified_of_its_own_decision(client, world):
    """The person who pressed the button knows. Same rule cancel_contract
    states when it notifies only the other party."""
    pid = _proposal(client, world)
    assert _reject(client, world, pid).status_code == 200
    assert _notifications(client, world["biz"]) == []


def test_rejecting_one_chain_leaves_the_others_alone(client, world):
    """A brief collects bids from several people and the brand answers them
    one at a time. Turning one down must not touch the rest, or a buyer
    clearing an obvious no would silently end the negotiation it was about to
    accept."""
    mine = _proposal(client, world)
    theirs = _proposal(client, world, creator=world["other"], version=1)

    assert _reject(client, world, mine).status_code == 200
    assert _proposal_status(client, theirs) == campaigns.SUBMITTED
    assert _notifications(client, world["other"]) == []


def test_only_the_live_version_moves(client, world):
    """Every version above the live one was already closed by whoever wrote
    the row underneath it. Rewriting those would erase who ended what."""
    old = _proposal(client, world, status=campaigns.SUPERSEDED, version=1)
    live = _proposal(client, world, version=2)

    assert _reject(client, world, live).status_code == 200
    assert _proposal_status(client, old) == campaigns.SUPERSEDED
    assert _proposal_status(client, live) == campaigns.PROPOSAL_REJECTED


def test_a_business_authored_counter_can_be_rejected(client, world):
    """The brand walking away from its own last counter. Unusual, and allowed
    on purpose for the reason decline_direct_order allows the mirror image:
    closing a negotiation you no longer want beats leaving the other side
    waiting on a number nobody intends to honour."""
    pid = _proposal(client, world, author=campaigns.AUTHOR_BUSINESS)
    assert _reject(client, world, pid).status_code == 200
    assert _proposal_status(client, pid) == campaigns.PROPOSAL_REJECTED


# --------------------------------------------------------------------------
# Who may make it
# --------------------------------------------------------------------------


def test_another_business_cannot_reject(client, world):
    """A campaign id is not a credential. Somebody else's brief is not theirs
    to close."""
    pid = _proposal(client, world)
    r = _reject(client, world, pid, actor="rival")
    assert r.status_code == 403
    assert r.json()["code"] == "campaign_not_yours"
    _untouched(client, world, pid)


def test_the_creator_cannot_reject_their_own_proposal(client, world):
    """Not because a creator may not end a negotiation — they may, by
    withdrawing — but because rejecting puts a REFUSAL on the record, and a
    creator refusing their own bid is not a fact about anything. The
    ownership check answers before the question is reached."""
    pid = _proposal(client, world)
    r = _reject(client, world, pid, actor="inf")
    assert r.status_code == 403
    assert r.json()["code"] == "campaign_not_yours"
    _untouched(client, world, pid)


def test_a_stranger_creator_cannot_reject_somebody_elses_bid(client, world):
    pid = _proposal(client, world)
    r = _reject(client, world, pid, actor="other")
    assert r.status_code == 403
    assert r.json()["code"] == "campaign_not_yours"
    _untouched(client, world, pid)


def test_rejecting_needs_auth(client, world):
    pid = _proposal(client, world)
    r = client.post(f"/campaigns/{world['campaign']}/proposals/{pid}/reject")
    assert r.status_code == 401
    _untouched(client, world, pid)


# --------------------------------------------------------------------------
# What it refuses
# --------------------------------------------------------------------------


def test_a_superseded_version_is_refused(client, world):
    """Not the offer on the table any more, so there is nothing on it to
    answer. Only one row in a chain is ever `submitted` and it is always the
    highest version, which is why the status test is the whole of "the latest
    version, and live"."""
    old = _proposal(client, world, status=campaigns.SUPERSEDED, version=1)
    _proposal(client, world, version=2)

    r = _reject(client, world, old)
    assert r.status_code == 400
    assert r.json()["code"] == "proposal_closed"
    _untouched(client, world, old, was=campaigns.SUPERSEDED)


def test_an_accepted_chain_is_refused(client, world):
    """The deal was done. Rejecting it now would say no to terms a contract
    was written from."""
    pid = _proposal(client, world, status=campaigns.PROPOSAL_ACCEPTED)
    r = _reject(client, world, pid)
    assert r.status_code == 400
    assert r.json()["code"] == "proposal_closed"
    _untouched(client, world, pid, was=campaigns.PROPOSAL_ACCEPTED)


def test_a_withdrawn_chain_is_refused(client, world):
    """The creator already took it off the table. Recording a refusal on top
    of that would put a rejection on their record for an offer nobody was
    asked to answer."""
    pid = _proposal(client, world, status=campaigns.WITHDRAWN)
    r = _reject(client, world, pid)
    assert r.status_code == 400
    assert r.json()["code"] == "proposal_closed"
    _untouched(client, world, pid, was=campaigns.WITHDRAWN)


def test_rejecting_twice_is_refused_and_tells_nobody_twice(client, world):
    """Refused rather than treated as a no-op, the same call cancel_campaign
    and withdraw_invitation make: a second "you were not selected" for
    something already answered is a notification nobody should ever get."""
    pid = _proposal(client, world)
    assert _reject(client, world, pid).status_code == 200

    again = _reject(client, world, pid)
    assert again.status_code == 400
    assert again.json()["code"] == "proposal_closed"
    assert _proposal_status(client, pid) == campaigns.PROPOSAL_REJECTED
    assert len(_notifications(client, world["inf"], key="proposal_rejected")) == 1


def test_a_chain_with_a_contract_is_refused(client, world):
    """The terms have left the negotiation and become an agreement sitting in
    front of two people to sign. Unwinding that is the contract cancel path,
    which knows about escrow; this endpoint does not and must not guess."""
    pid = _proposal(client, world)
    _contract(client, world, pid)

    r = _reject(client, world, pid)
    assert r.status_code == 400
    assert r.json()["code"] == "proposal_has_contract"
    _untouched(client, world, pid)


def test_a_contract_with_somebody_else_does_not_block_the_rejection(client, world):
    """A brief can carry several deals. The guard is about THIS chain, so a
    contract signed with another creator must not lock the brand out of
    answering the bids still open beside it."""
    _contract(client, world, _proposal(client, world, creator=world["other"]),
              creator=world["other"])
    mine = _proposal(client, world, version=1)

    assert _reject(client, world, mine).status_code == 200
    assert _proposal_status(client, mine) == campaigns.PROPOSAL_REJECTED


@pytest.mark.parametrize("dead", [campaigns.CANCELLED, campaigns.COMPLETED])
def test_a_brief_that_ended_takes_no_rejection(client, world, dead):
    """Both terminal states, and the same rule submit_proposal and
    reply_to_proposal already refuse with. A campaign that ended has had its
    open chains closed by completion.close_open_offers, so there is nothing
    here left to reject and a second closing would notify the creator twice."""
    pid = _proposal(client, world)
    _set_campaign_status(client, world["campaign"], dead)

    r = _reject(client, world, pid)
    assert r.status_code == 400
    assert r.json()["code"] == "campaign_not_open"
    _untouched(client, world, pid)


def test_a_draft_takes_no_rejection(client, world):
    """Nobody has seen it. Whatever rows a fixture hung off it, a draft is not
    a brief anybody has bid on."""
    pid = _proposal(client, world)
    _set_campaign_status(client, world["campaign"], campaigns.DRAFT)

    r = _reject(client, world, pid)
    assert r.status_code == 400
    assert r.json()["code"] == "campaign_not_open"
    _untouched(client, world, pid)


def test_a_direct_order_is_refused(client, world):
    """An order is not a bid on a brief, and this endpoint would only
    half-close one: the campaign would stay published, the invitation would
    stay `invited`, and the expiry sweep only touches `submitted` rows — so an
    order nobody can answer would sit in the buyer's list looking live and
    never lapse. Declining is the one way an order closes."""
    order = _direct_order(client, world)
    r = _reject(client, world, order["proposal"], campaign=order["campaign"])
    assert r.status_code == 400
    assert r.json()["code"] == "proposal_is_direct_order"
    assert _proposal_status(client, order["proposal"]) == campaigns.SUBMITTED
    assert _notifications(client, world["inf"]) == []


def test_an_unknown_proposal_is_404(client, world):
    r = _reject(client, world, "no-such-proposal")
    assert r.status_code == 404
    assert r.json()["code"] == "proposal_not_found"


def test_a_proposal_on_another_brief_is_not_found_here(client, world):
    """Scoped to the campaign in the path. A proposal id lifted from another
    brief is not found rather than found and refused — the buyer owns both
    briefs in this test, so the only thing stopping a cross-brief rejection is
    the scoping."""
    db = client.session_factory()
    try:
        other_camp = campaigns.Campaign(
            business_user_id=world["biz"], title="Second brief", budget_amount=100000,
            budget_currency="XOF", deliverables=[], status=campaigns.PUBLISHED,
        )
        db.add(other_camp); db.commit(); db.refresh(other_camp)
        elsewhere = other_camp.id
    finally:
        db.close()
    pid = _proposal(client, world, campaign=elsewhere)

    r = _reject(client, world, pid)
    assert r.status_code == 404
    assert r.json()["code"] == "proposal_not_found"
    _untouched(client, world, pid)


# --------------------------------------------------------------------------
# What it closes
# --------------------------------------------------------------------------


def test_the_creator_cannot_bid_again_after_a_rejection(client, world):
    """THE POINT OF USING `rejected` RATHER THAN INVENTING A STATUS.
    submit_proposal already refuses to reopen a chain that reached one of the
    three terminal resolutions, so the guard this feature needs was written
    before it — a rejection a bidder could undo by bidding again would not be
    a decision. Asserted rather than assumed, because it is the whole reason
    the status was reused."""
    pid = _proposal(client, world)
    assert _reject(client, world, pid).status_code == 200

    again = client.post(
        f"/campaigns/{world['campaign']}/proposals",
        json={"rate_amount": 35000, "rate_currency": "XOF", "timeline_days": 5},
        headers=_headers(world["inf"]),
    )
    assert again.status_code == 400
    assert again.json()["code"] == "proposal_negotiation_closed"

    # And nothing was written: the chain still ends at the rejected version.
    db = client.session_factory()
    try:
        versions = sorted(
            p.version for p in db.query(campaigns.Proposal).filter(
                campaigns.Proposal.campaign_id == world["campaign"]
            ).all()
        )
    finally:
        db.close()
    assert versions == [1]


def test_a_rejection_does_not_close_the_brief(client, world):
    """The brand said no to one bid, not to the brief. It stays published and
    open, and the next creator can still apply — which is exactly the
    difference between this and the cancel button the buyer used to have to
    reach for."""
    pid = _proposal(client, world)
    assert _reject(client, world, pid).status_code == 200

    db = client.session_factory()
    try:
        campaign = db.query(campaigns.Campaign).filter(
            campaigns.Campaign.id == world["campaign"]
        ).first()
        assert campaign.status == campaigns.PUBLISHED
    finally:
        db.close()

    fresh = client.post(
        f"/campaigns/{world['campaign']}/proposals",
        json={"rate_amount": 30000, "rate_currency": "XOF", "timeline_days": 5},
        headers=_headers(world["other"]),
    )
    assert fresh.status_code == 201, fresh.text

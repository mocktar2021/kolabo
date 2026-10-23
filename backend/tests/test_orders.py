"""Direct orders: a brand buys a creator's package at the published price.

The order is a hidden, single-creator campaign carrying one invitation and one
business-authored proposal, so the rest of the platform (contracts, escrow,
reviews) needs no second code path. These tests pin that shape down, plus the
rules about who may place an order, who may answer one, and what happens when
nobody does.
"""
from datetime import date, datetime, timedelta

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
from app.modules.campaigns import service as campaigns_service
from app.modules.campaigns.router import router as campaigns_router
from app.modules.contracts import models as contracts
from app.modules.contracts.router import router as contracts_router
from app.modules.notifications.models import Notification
from app.modules.profiles.models import Package

# The party details both sides have to have stated, and the licence the brand
# has to have stated, before a contract can be generated from anything at all.
# Shared with the three other suites that reach contract generation;
# tests/party_fixtures.py carries the argument.
from tests.party_fixtures import LICENCE_TERMS, licence_terms, seed_both_parties


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    # The REAL handler, registered from app.core.errors rather than a
    # lookalike: without it FastAPI renders {"detail": ...} alone and the
    # `code` assertions below would be reading a key that is not there. The
    # sentence stays exactly where it was, so the tests that read `detail`
    # are unaffected. Same registration as test_campaign_write_guards.py.
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(campaigns_router, prefix="/campaigns")
    # Accepting an order goes through the existing contracts path, and the
    # tests that check what it produced read it back from there.
    app.include_router(contracts_router, prefix="/contracts")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _setup(client, price=25000, currency="XOF", active=True, quantity=2):
    """A brand, a creator, and one package on the creator's profile."""
    db = client.session_factory()
    try:
        biz = User(phone="+22990000001", email="22990000001@kolabo.test", password_hash="x", country_code="BJ", role="business", is_verified=True)
        creator = User(phone="+22990000002", email="22990000002@kolabo.test", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add_all([biz, creator]); db.commit(); db.refresh(biz); db.refresh(creator)
        # BOTH SIDES STATE WHO THEY ARE, because accepting an order writes a
        # contract and generation refuses without that
        # (contract_business_party_missing / contract_creator_party_missing).
        # It belongs in the fixture rather than in the four tests that accept:
        # this is the pair every one of them accepts as, and a helper that
        # only sometimes produces a complete market participant is a helper
        # whose failures have to be read twice.
        #
        # The second creator (_second_package) and the bystander (_outsider)
        # are deliberately left without one, because neither ever reaches
        # generation. The fresh order in the expiry sweep is never accepted,
        # and every refusal involving the bystander is raised by
        # orders._load_order, which runs before the party gate.
        #
        # The licence generation also refuses without is not a property of
        # either party: the brand states it on the order, so it is in _order
        # below.
        seed_both_parties(db, biz.id, creator.id)
        pkg = Package(
            user_id=creator.id,
            platform="instagram",
            deliverable_type="reel",
            title="Two reels, shot and edited",
            price_amount=price,
            currency=currency,
            quantity=quantity,
            is_active=active,
        )
        db.add(pkg); db.commit(); db.refresh(pkg)
        return biz.id, creator.id, pkg.id
    finally:
        db.close()


def _second_package(client, phone="+22990000004", price=15000):
    """Another creator with another package, so two orders can coexist."""
    db = client.session_factory()
    try:
        creator = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add(creator); db.commit(); db.refresh(creator)
        pkg = Package(
            user_id=creator.id,
            platform="tiktok",
            deliverable_type="video",
            title="One TikTok video",
            price_amount=price,
            currency="XOF",
            quantity=1,
            is_active=True,
        )
        db.add(pkg); db.commit(); db.refresh(pkg)
        return creator.id, pkg.id
    finally:
        db.close()


def _order(client, buyer, package_id, note=None):
    # The licence travels with the order even though every other term comes
    # off the package, and that is the rule rather than a convenience: a
    # package says what the creator will make and what it costs, while how the
    # brand may then use it is a statement about the brand's own plans. The
    # same package is sold to somebody who will post it once and to somebody
    # who will run it as an advertisement for a year.
    #
    # Stated here, in the one helper every order in this file goes through,
    # because that is where a real buyer states it: generation refuses without
    # a licence (contract_licence_terms_missing), so an order placed with none
    # is an order nobody can turn into a contract.
    body = {"package_id": package_id, "licence_terms": licence_terms()}
    if note is not None:
        body["note"] = note
    return client.post("/campaigns/orders", json=body, headers=_headers(buyer))


def _rows(client, model, **filters):
    db = client.session_factory()
    try:
        query = db.query(model)
        for field, value in filters.items():
            query = query.filter(getattr(model, field) == value)
        return query.all()
    finally:
        db.close()


def _age_out(client, proposal_id):
    """Push an order's window into the past, as 48 real hours would."""
    db = client.session_factory()
    try:
        p = db.query(campaigns.Proposal).filter(campaigns.Proposal.id == proposal_id).first()
        p.expires_at = campaigns.utcnow() - timedelta(hours=1)
        db.commit()
    finally:
        db.close()


def _outsider(client, phone="+22990000005"):
    """A verified creator with nothing at all to do with the order under test."""
    db = client.session_factory()
    try:
        user = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add(user); db.commit(); db.refresh(user)
        return user.id
    finally:
        db.close()


def _stranger_chain(client, campaign_id, stranger_id, author_role=None, rate=30000, days=7):
    """A proposal chain opened on somebody else's direct order, seeded directly.

    THIS ROW CAN NO LONGER BE CREATED THROUGH THE API, and it is written here
    on purpose. submit_proposal used to ask only whether the campaign was
    published, so any signed-in creator could open a chain on a direct order
    addressed to somebody else; it now refuses that with board_direct_order
    (campaigns.service, PR #124). What the guard cannot do is unwrite the rows
    that landed before it, which is why orders._load_order has to refuse this
    caller on its own — and the only way to reconstruct that state is to put
    the row in the database the way the old endpoint did.

    VERSION 1 AND NOT 2, deliberately: latest_in_chain is per creator, so the
    stranger's chain started over instead of superseding the buyer's offer,
    leaving two live v1 rows on one campaign. That is the shape the bug had.

    author_role defaults to the creator, which is what the old endpoint wrote.
    The accept test overrides it, for the reason stated there.

    NO LICENCE, for the same reason the old endpoint wrote none: this row is a
    creator's own, and a creator never states one. Every test using it is
    refused before generation anyway.
    """
    db = client.session_factory()
    try:
        buyer_offer = (
            db.query(campaigns.Proposal)
            .filter(campaigns.Proposal.campaign_id == campaign_id)
            .first()
        )
        row = campaigns.Proposal(
            campaign_id=campaign_id,
            influencer_user_id=stranger_id,
            version=1,
            rate_amount=rate,
            rate_currency="XOF",
            timeline_days=days,
            author_role=author_role or campaigns.AUTHOR_INFLUENCER,
            status=campaigns.SUBMITTED,
            # The order's own clock, which submit_proposal carried forward.
            expires_at=buyer_offer.expires_at,
        )
        db.add(row); db.commit(); db.refresh(row)
        return row.id
    finally:
        db.close()


def _publish_brief(client, biz):
    return client.post(
        "/campaigns/",
        json={
            "title": "Ramadan push",
            "budget_amount": 500000,
            "budget_currency": "XOF",
            "deliverables": [{"platform": "instagram", "type": "post", "quantity": 3}],
            # Relative, because a brief past its deadline no longer takes
            # proposals (campaigns.service) and both callers below bid on this
            # one. A hard-coded date would read as "a live brief" only until
            # it arrived, and then take them down on a morning nobody had
            # changed anything.
            "deadline": str(date.today() + timedelta(days=90)),
            "publish": True,
            # An OPEN brief, because both tests below have a creator nobody
            # invited bid on it — which is what `open` means. The flag is new
            # (campaigns.board) and defaults to false, so this helper was
            # describing an open brief while building a closed one.
            "is_open": True,
            # NO LICENCE, deliberately, unlike the orders this file places.
            # Neither test that uses this brief reaches a contract, and a brief
            # with no licence stated is a real and publishable state: the only
            # thing it cannot do is become a contract. Stating one here would
            # imply publishing requires it, which it does not.
        },
        headers=_headers(biz),
    )


# --------------------------------------------------------------------------
# Placing an order
# --------------------------------------------------------------------------


def test_order_creates_campaign_invitation_and_proposal_from_package_terms(client):
    biz, creator, pkg = _setup(client, price=25000, currency="XOF", quantity=2)
    r = _order(client, biz, pkg, note="For the December launch")
    assert r.status_code == 201
    body = r.json()

    campaign = _rows(client, campaigns.Campaign, id=body["campaign_id"])[0]
    assert campaign.is_direct is True
    assert campaign.status == campaigns.PUBLISHED
    assert campaign.title == "Two reels, shot and edited"
    assert campaign.budget_amount == 25000
    assert campaign.budget_currency == "XOF"
    assert campaign.deadline is None
    assert campaign.deliverables == [{"platform": "instagram", "type": "reel", "quantity": 2}]
    # The licence is NOT on the wrapper campaign. On an order the brand's offer
    # is the proposal, which is the row the creator reads and answers, so the
    # block goes there and contracts._licence_snapshot reads it first.
    assert campaign.licence_terms is None

    invitations = _rows(client, campaigns.CampaignInvitation, campaign_id=campaign.id)
    assert len(invitations) == 1
    assert invitations[0].influencer_user_id == creator
    assert invitations[0].status == campaigns.INVITED

    proposal = _rows(client, campaigns.Proposal, id=body["proposal_id"])[0]
    assert proposal.version == 1
    # The BUSINESS is proposing here: the buyer picked a published price and
    # offered it back, which is what makes the creator's reply an answer.
    assert proposal.author_role == campaigns.AUTHOR_BUSINESS
    assert proposal.rate_amount == 25000
    assert proposal.rate_currency == "XOF"
    assert proposal.timeline_days == campaigns_service.DEFAULT_ORDER_TIMELINE_DAYS
    assert proposal.status == campaigns.SUBMITTED
    assert proposal.note == "For the December launch"
    # Every other term came off the package; this one came off the buyer, and
    # it is stored exactly as sent because a contract quotes it verbatim.
    assert proposal.licence_terms == LICENCE_TERMS


def test_order_expires_in_48_hours_and_notifies_the_creator(client):
    biz, creator, pkg = _setup(client)
    body = _order(client, biz, pkg).json()

    expected = campaigns.utcnow() + timedelta(hours=campaigns_service.ORDER_ACCEPT_WINDOW_HOURS)
    expires_at = datetime.fromisoformat(body["expires_at"])
    assert abs((expires_at - expected).total_seconds()) < 60

    kinds = [n.type for n in _rows(client, Notification, user_id=creator)]
    assert "direct_order" in kinds


def test_cannot_order_your_own_package(client):
    biz, creator, pkg = _setup(client)
    r = _order(client, creator, pkg)
    assert r.status_code == 400
    assert r.json()["detail"] == "You cannot order your own package."


def test_an_influencer_cannot_order_someone_elses_package(client):
    biz, creator, pkg = _setup(client)
    other_id, _ = _second_package(client, phone="+22990000003")
    # Same rule as authoring a brief: buying is the brand side of the market.
    assert _order(client, other_id, pkg).status_code == 403


def test_an_inactive_package_cannot_be_ordered(client):
    biz, creator, pkg = _setup(client, active=False)
    r = _order(client, biz, pkg)
    assert r.status_code == 400
    assert "not available" in r.json()["detail"]


def test_unknown_package_is_404(client):
    biz, creator, pkg = _setup(client)
    assert _order(client, biz, "no-such-package").status_code == 404


def test_ordering_requires_auth(client):
    biz, creator, pkg = _setup(client)
    assert client.post("/campaigns/orders", json={"package_id": pkg}).status_code == 401


def test_an_order_with_a_half_stated_licence_is_refused(client):
    """Option 2 without a duration is not a licence anybody can rely on.

    Refused at the point the brand states it rather than later, which is the
    whole reason capture is validated: the alternative is a stored block that
    only fails when somebody tries to accept the order, by which time the
    refusal has landed on the creator.

    licence_terms_invalid naming the fields that are missing, as
    party_details_invalid names its own. The option itself decides which they
    are, so the sentence cannot name them without the values.
    """
    biz, creator, pkg = _setup(client)
    r = client.post(
        "/campaigns/orders",
        json={
            "package_id": pkg,
            "licence_terms": {"licence_option": "2", "licence_duration": "douze mois"},
        },
        headers=_headers(biz),
    )
    assert r.status_code == 400
    assert r.json()["code"] == "licence_terms_invalid"
    assert r.json()["values"]["fields"] == "licence_territories, licence_media"
    # And nothing was written: a refused licence leaves no order behind.
    assert _rows(client, campaigns.Campaign) == []
    assert _rows(client, campaigns.Proposal) == []


def test_an_order_with_an_unknown_licence_option_is_refused(client):
    """Three options, and the refusal names all of them.

    The set is closed because it IS Article 10 of the approved model: a fourth
    option is a change to a document counsel signed off, not a configuration
    value.
    """
    biz, creator, pkg = _setup(client)
    r = client.post(
        "/campaigns/orders",
        json={"package_id": pkg, "licence_terms": {"licence_option": "4"}},
        headers=_headers(biz),
    )
    assert r.status_code == 400
    assert r.json()["code"] == "licence_terms_invalid"
    assert r.json()["values"]["options"] == "1, 2, 3"
    assert _rows(client, campaigns.Campaign) == []


def test_an_order_can_be_placed_with_no_licence_and_then_not_contracted(client):
    """Capture is optional and generation is the gate, which is a real seam.

    The columns are nullable because every brief and order written before this
    existed has nothing in them, so an order with no licence is accepted and
    sits there answerable. What it cannot do is become a contract, and the
    refusal then lands on the CREATOR, who is the one accepting and the one
    person who cannot fix it.

    That asymmetry is pinned here rather than hidden, because it is the
    argument for requiring a licence when an order is placed. Doing that is a
    change to what both clients send; contracts/service.py says so beside the
    refusal.
    """
    biz, creator, pkg = _setup(client)
    placed = client.post(
        "/campaigns/orders", json={"package_id": pkg}, headers=_headers(biz)
    )
    assert placed.status_code == 201
    order = placed.json()
    assert _rows(client, campaigns.Proposal, id=order["proposal_id"])[0].licence_terms is None

    r = client.post(f"/campaigns/orders/{order['proposal_id']}/accept", headers=_headers(creator))
    assert r.status_code == 400
    assert r.json()["code"] == "contract_licence_terms_missing"
    assert _rows(client, contracts.Contract) == []
    # And the order is exactly as it was: the creator can still decline it,
    # which is what a refusal written above the accepted-marking leaves them.
    assert _rows(client, campaigns.Proposal, id=order["proposal_id"])[0].status == campaigns.SUBMITTED
    assert _rows(client, campaigns.CampaignInvitation, campaign_id=order["campaign_id"])[0].status == campaigns.INVITED


def test_a_direct_order_is_hidden_from_outsiders_but_visible_to_both_parties(client):
    """A direct order is a private transaction, not a brief anyone can bid on.

    There is no public campaign board in this codebase — every campaign listing
    is already scoped to a participant — so "hidden" is tested as: a third
    party finds it nowhere, while the buyer and the invited creator each find
    it on their own surface.
    """
    biz, creator, pkg = _setup(client)
    body = _order(client, biz, pkg).json()
    campaign_id = body["campaign_id"]

    mine = client.get("/campaigns/mine", headers=_headers(biz)).json()
    assert [c["id"] for c in mine] == [campaign_id]
    assert mine[0]["is_direct"] is True

    invitations = client.get("/campaigns/invitations/mine", headers=_headers(creator)).json()
    assert [i["campaign_id"] for i in invitations] == [campaign_id]
    assert invitations[0]["campaign"]["is_direct"] is True
    # The order's terms, on the row the creator answers. This list is the only
    # creator-facing surface a direct order appears on, so it is the only place
    # the licence can reach them before they accept.
    assert invitations[0]["proposal"]["licence_terms"] == LICENCE_TERMS

    # A stranger sees it on no listing and cannot open it.
    assert client.get("/campaigns/mine", headers=_headers("stranger")).json() == []
    assert client.get("/campaigns/invitations/mine", headers=_headers("stranger")).json() == []
    assert client.get(f"/campaigns/{campaign_id}", headers=_headers("stranger")).status_code == 403
    # Nor can the creator: campaign detail has always been the owner's view,
    # and the creator reaches the order through their invitation instead.
    assert client.get(f"/campaigns/{campaign_id}", headers=_headers(creator)).status_code == 403


def test_a_brief_is_not_marked_direct_and_its_proposals_never_expire(client):
    """The normal brief flow is untouched by any of this."""
    biz, creator, pkg = _setup(client)
    created = _publish_brief(client, biz)
    assert created.status_code == 201
    assert created.json()["is_direct"] is False

    proposal = client.post(
        f"/campaigns/{created.json()['id']}/proposals",
        json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 5},
        headers=_headers(creator),
    )
    assert proposal.status_code == 201
    assert proposal.json()["expires_at"] is None


# --------------------------------------------------------------------------
# Answering an order
# --------------------------------------------------------------------------


def test_creator_accepts_and_a_contract_exists_on_the_package_terms(client):
    biz, creator, pkg = _setup(client, price=25000)
    order = _order(client, biz, pkg).json()

    r = client.post(f"/campaigns/orders/{order['proposal_id']}/accept", headers=_headers(creator))
    assert r.status_code == 201
    contract = r.json()
    assert contract["campaign_id"] == order["campaign_id"]
    assert contract["proposal_id"] == order["proposal_id"]
    assert contract["business_user_id"] == biz
    assert contract["influencer_user_id"] == creator
    # The package's terms, carried the whole way through without re-entry.
    assert contract["rate_amount"] == 25000
    assert contract["rate_currency"] == "XOF"
    assert contract["timeline_days"] == campaigns_service.DEFAULT_ORDER_TIMELINE_DAYS
    assert contract["status"] == contracts.PENDING
    assert contract["fully_signed"] is False
    # And the licence the order was placed under, frozen onto the contract off
    # the offer row. test_contracts.py owns the snapshot rules.
    assert _rows(client, contracts.Contract, id=contract["id"])[0].licence_terms == LICENCE_TERMS

    proposal = _rows(client, campaigns.Proposal, id=order["proposal_id"])[0]
    assert proposal.status == campaigns.PROPOSAL_ACCEPTED
    invitation = _rows(client, campaigns.CampaignInvitation, campaign_id=order["campaign_id"])[0]
    assert invitation.status == campaigns.ACCEPTED

    # Both parties can find it through the ordinary contracts endpoints: the
    # point of reusing that path is that nothing downstream knows the
    # difference between an order and a brief.
    assert client.get(f"/contracts/by-proposal/{order['proposal_id']}", headers=_headers(biz)).status_code == 200
    assert [c["id"] for c in client.get("/contracts/mine", headers=_headers(creator)).json()] == [contract["id"]]


def test_only_the_invited_creator_can_accept(client):
    biz, creator, pkg = _setup(client)
    order = _order(client, biz, pkg).json()
    proposal_id = order["proposal_id"]

    assert client.post(f"/campaigns/orders/{proposal_id}/accept", headers=_headers("stranger")).status_code == 403
    # Not even the buyer: accepting is the answer, and the buyer already spoke.
    assert client.post(f"/campaigns/orders/{proposal_id}/accept", headers=_headers(biz)).status_code == 403
    assert client.post(f"/campaigns/orders/{proposal_id}/decline", headers=_headers("stranger")).status_code == 403
    assert _rows(client, contracts.Contract) == []


def test_accepting_after_the_window_closed_is_rejected(client):
    biz, creator, pkg = _setup(client)
    order = _order(client, biz, pkg).json()
    _age_out(client, order["proposal_id"])

    r = client.post(f"/campaigns/orders/{order['proposal_id']}/accept", headers=_headers(creator))
    assert r.status_code == 400
    assert r.json()["detail"] == "This order has expired."
    assert _rows(client, contracts.Contract) == []


def test_decline_closes_the_order_and_tells_the_buyer(client):
    biz, creator, pkg = _setup(client)
    order = _order(client, biz, pkg).json()

    r = client.post(f"/campaigns/orders/{order['proposal_id']}/decline", headers=_headers(creator))
    assert r.status_code == 200
    assert r.json()["status"] == campaigns.PROPOSAL_DECLINED

    campaign = _rows(client, campaigns.Campaign, id=order["campaign_id"])[0]
    assert campaign.status == campaigns.CANCELLED
    invitation = _rows(client, campaigns.CampaignInvitation, campaign_id=campaign.id)[0]
    assert invitation.status == campaigns.DECLINED

    messages = [n.message for n in _rows(client, Notification, user_id=biz, type="direct_order")]
    assert any("declined" in m for m in messages)
    # Nothing was ever funded, so there is nothing to give back.
    assert any("not charged" in m for m in messages)
    # And no contract was written.
    assert _rows(client, contracts.Contract) == []


def test_an_answered_order_cannot_be_answered_again(client):
    biz, creator, pkg = _setup(client)
    order = _order(client, biz, pkg).json()
    proposal_id = order["proposal_id"]
    assert client.post(f"/campaigns/orders/{proposal_id}/decline", headers=_headers(creator)).status_code == 200
    assert client.post(f"/campaigns/orders/{proposal_id}/accept", headers=_headers(creator)).status_code == 400


# --------------------------------------------------------------------------
# Who the order was addressed to
#
# Answering an order is authorised by the invitation _place_order wrote for
# the one creator the buyer chose — not by owning a proposal chain, which
# anybody could open and which before PR #124 anybody could.
#
# EVERY REFUSAL HERE IS ASSERTED TWICE: the status and code the caller gets
# back, and the fact that nothing was written. A guard that answers 403 and
# cancels the campaign anyway reads as green in a test that only checks the
# status, and it is the worse of the two bugs — the stranger is told no while
# the order dies anyway.
# --------------------------------------------------------------------------


def test_a_creator_with_no_invitation_cannot_decline_someone_elses_order(client):
    """The bug: a stranger's "no" killed an order between two other parties.

    _load_order authorised by the PROPOSAL's creator, so the stranger's own
    row passed the check. decline_direct_order then ran the whole way through:
    it cancelled the campaign, _set_invitation silently did nothing (there is
    no invitation of theirs to move), and the creator the order was actually
    addressed to lost it with nobody told why.
    """
    biz, creator, pkg = _setup(client)
    order = _order(client, biz, pkg).json()
    stranger = _outsider(client)
    stranger_proposal = _stranger_chain(client, order["campaign_id"], stranger)

    r = client.post(f"/campaigns/orders/{stranger_proposal}/decline", headers=_headers(stranger))
    assert r.status_code == 403
    assert r.json()["code"] == "order_not_yours"

    # AND THE ORDER IS STILL LIVE, which is the half of this that mattered.
    assert _rows(client, campaigns.Campaign, id=order["campaign_id"])[0].status == campaigns.PUBLISHED
    assert _rows(client, campaigns.Proposal, id=order["proposal_id"])[0].status == campaigns.SUBMITTED
    # The addressed creator's invitation is untouched: still waiting for them.
    invitation = _rows(client, campaigns.CampaignInvitation, campaign_id=order["campaign_id"])[0]
    assert invitation.influencer_user_id == creator
    assert invitation.status == campaigns.INVITED
    # And the buyer was never told their order had been declined.
    assert not any("declined" in n.message for n in _rows(client, Notification, user_id=biz))


def test_a_creator_with_no_invitation_cannot_accept_someone_elses_order(client):
    """Accept routes through _load_order too, so the same line guards it.

    The seeded row is BUSINESS-authored here, which is the point of the test.
    A creator-authored row would be refused by _require_business_offer anyway,
    for a different reason and with a different code — a 400 that would make
    this look guarded while the authorisation underneath it was still wrong.
    This shape reaches the authorisation, and _load_order runs first.
    """
    biz, creator, pkg = _setup(client)
    order = _order(client, biz, pkg).json()
    stranger = _outsider(client)
    stranger_proposal = _stranger_chain(
        client, order["campaign_id"], stranger, author_role=campaigns.AUTHOR_BUSINESS
    )

    r = client.post(f"/campaigns/orders/{stranger_proposal}/accept", headers=_headers(stranger))
    assert r.status_code == 403
    assert r.json()["code"] == "order_not_yours"

    # Nothing signed, and the order is still open for the creator it was sent to.
    assert _rows(client, contracts.Contract) == []
    assert _rows(client, campaigns.Proposal, id=stranger_proposal)[0].status == campaigns.SUBMITTED
    assert _rows(client, campaigns.Campaign, id=order["campaign_id"])[0].status == campaigns.PUBLISHED
    assert _rows(client, campaigns.CampaignInvitation, campaign_id=order["campaign_id"])[0].status == campaigns.INVITED


def test_the_addressed_creator_can_still_decline_their_own_order(client):
    """The feature the fix must not cost: the invited creator's own no.

    The stranger's row is seeded here too, so that what lets this caller
    through is visibly the invitation and not the absence of anybody else on
    the campaign.
    """
    biz, creator, pkg = _setup(client)
    order = _order(client, biz, pkg).json()
    _stranger_chain(client, order["campaign_id"], _outsider(client))

    r = client.post(f"/campaigns/orders/{order['proposal_id']}/decline", headers=_headers(creator))
    assert r.status_code == 200
    assert r.json()["status"] == campaigns.PROPOSAL_DECLINED
    assert _rows(client, campaigns.Campaign, id=order["campaign_id"])[0].status == campaigns.CANCELLED
    invitation = _rows(client, campaigns.CampaignInvitation, campaign_id=order["campaign_id"])[0]
    assert invitation.status == campaigns.DECLINED
    assert any("declined" in n.message for n in _rows(client, Notification, user_id=biz, type="direct_order"))


def test_the_addressed_creator_can_still_accept_their_own_order(client):
    """The same, on the path that writes a contract."""
    biz, creator, pkg = _setup(client)
    order = _order(client, biz, pkg).json()
    _stranger_chain(client, order["campaign_id"], _outsider(client))

    r = client.post(f"/campaigns/orders/{order['proposal_id']}/accept", headers=_headers(creator))
    assert r.status_code == 201
    assert r.json()["influencer_user_id"] == creator
    assert _rows(client, campaigns.Proposal, id=order["proposal_id"])[0].status == campaigns.PROPOSAL_ACCEPTED
    invitation = _rows(client, campaigns.CampaignInvitation, campaign_id=order["campaign_id"])[0]
    assert invitation.status == campaigns.ACCEPTED


# --------------------------------------------------------------------------
# The expiry sweep
# --------------------------------------------------------------------------


def test_the_sweep_expires_a_stale_order_and_leaves_a_fresh_one_alone(client, admin_headers):
    biz, creator, pkg = _setup(client)
    other_creator, other_pkg = _second_package(client)
    stale = _order(client, biz, pkg).json()
    fresh = _order(client, biz, other_pkg).json()
    _age_out(client, stale["proposal_id"])

    r = client.post("/campaigns/orders/expire", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == {"expired": 1}

    assert _rows(client, campaigns.Proposal, id=stale["proposal_id"])[0].status == campaigns.PROPOSAL_DECLINED
    assert _rows(client, campaigns.Campaign, id=stale["campaign_id"])[0].status == campaigns.CANCELLED
    assert _rows(client, campaigns.Proposal, id=fresh["proposal_id"])[0].status == campaigns.SUBMITTED
    assert _rows(client, campaigns.Campaign, id=fresh["campaign_id"])[0].status == campaigns.PUBLISHED

    # Both sides hear about it: the creator lost the job, the buyer can stop
    # waiting.
    assert any("expired" in n.message for n in _rows(client, Notification, user_id=creator))
    assert any("expired" in n.message for n in _rows(client, Notification, user_id=biz))


def test_the_sweep_never_touches_a_brief_proposal(client, admin_headers):
    """No expires_at means no expiry, however long the proposal sits there."""
    biz, creator, pkg = _setup(client)
    brief = _publish_brief(client, biz).json()
    proposal = client.post(
        f"/campaigns/{brief['id']}/proposals",
        json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 5},
        headers=_headers(creator),
    ).json()

    assert client.post("/campaigns/orders/expire", headers=admin_headers).json() == {"expired": 0}
    assert _rows(client, campaigns.Proposal, id=proposal["id"])[0].status == campaigns.SUBMITTED
    assert _rows(client, campaigns.Campaign, id=brief["id"])[0].status == campaigns.PUBLISHED


def test_the_sweep_requires_an_admin(client):
    biz, creator, pkg = _setup(client)
    order = _order(client, biz, pkg).json()
    _age_out(client, order["proposal_id"])
    assert client.post("/campaigns/orders/expire").status_code == 401
    assert _rows(client, campaigns.Proposal, id=order["proposal_id"])[0].status == campaigns.SUBMITTED


# --------------------------------------------------------------------------
# The sweep expires THE ORDER, not whatever else is lying on the campaign
#
# Same stranger's chain as the section above, from the same helper, reaching
# the same campaign by the other door. _load_order refuses a CALLER holding
# one of these rows; the sweep has no caller — it reads the table itself — so
# closing the endpoint did nothing for it and it needs the rule of its own.
#
# These are SKIPS rather than refusals: a batch passes the row over and keeps
# going, so every test here asserts the count as well as the rows, because a
# row that was skipped and still counted as expired is a report that lies.
# --------------------------------------------------------------------------


def test_an_orphan_chain_does_not_expire_somebody_elses_live_order(client, admin_headers):
    """A stranger's lapsed row must not close an order it has nothing to do with.

    The buyer's own offer here is FRESH — its full window still to run — so the
    only lapsed row in the table belongs to somebody who was never addressed.
    The sweep used to read that row, cancel whichever campaign it happened to
    hang off, and tell the buyer their order had expired while it was still
    live and still answerable.
    """
    biz, creator, pkg = _setup(client)
    order = _order(client, biz, pkg).json()
    orphan = _stranger_chain(client, order["campaign_id"], _outsider(client))
    _age_out(client, orphan)

    assert client.post("/campaigns/orders/expire", headers=admin_headers).json() == {"expired": 0}

    # The order is exactly where it was, and the creator can still answer it.
    assert _rows(client, campaigns.Campaign, id=order["campaign_id"])[0].status == campaigns.PUBLISHED
    assert _rows(client, campaigns.Proposal, id=order["proposal_id"])[0].status == campaigns.SUBMITTED
    invitation = _rows(client, campaigns.CampaignInvitation, campaign_id=order["campaign_id"])[0]
    assert invitation.influencer_user_id == creator
    assert invitation.status == campaigns.INVITED

    # Passed over, not closed: answering it is not this sweep's business either.
    assert _rows(client, campaigns.Proposal, id=orphan)[0].status == campaigns.SUBMITTED

    # And nobody is told an order lapsed when none did.
    assert not any("expired" in n.message for n in _rows(client, Notification, user_id=biz))
    assert not any("expired" in n.message for n in _rows(client, Notification, user_id=creator))


def test_an_orphan_chain_does_not_cancel_an_order_that_was_already_accepted(client, admin_headers):
    """The serious one: the campaign carries a contract by the time this runs.

    Accepting supersedes only the accepted chain's OWN earlier versions, so the
    stranger's row sits `submitted` for good and its window lapses against a
    campaign that now has an agreement on it. Cancelling here would kill a
    contract two people are about to sign and an escrow the buyer may already
    have funded — and unlike a decline, nobody asked for it.

    The contract is still PENDING rather than fully signed, deliberately.
    Pending is the weaker state and the guard has to count it, which is the
    same reading campaigns.editing._contract takes when it refuses the buyer
    their own cancellation.
    """
    biz, creator, pkg = _setup(client)
    order = _order(client, biz, pkg).json()
    accepted = client.post(
        f"/campaigns/orders/{order['proposal_id']}/accept", headers=_headers(creator)
    )
    assert accepted.status_code == 201
    contract = accepted.json()
    orphan = _stranger_chain(client, order["campaign_id"], _outsider(client))
    _age_out(client, orphan)

    assert client.post("/campaigns/orders/expire", headers=admin_headers).json() == {"expired": 0}

    assert _rows(client, campaigns.Campaign, id=order["campaign_id"])[0].status == campaigns.PUBLISHED
    assert _rows(client, campaigns.Proposal, id=order["proposal_id"])[0].status == campaigns.PROPOSAL_ACCEPTED
    assert _rows(client, campaigns.CampaignInvitation, campaign_id=order["campaign_id"])[0].status == campaigns.ACCEPTED

    # The contract is untouched: same row, same proposal, same status.
    row = _rows(client, contracts.Contract, id=contract["id"])[0]
    assert row.campaign_id == order["campaign_id"]
    assert row.proposal_id == order["proposal_id"]
    assert row.status == contracts.PENDING

    assert _rows(client, campaigns.Proposal, id=orphan)[0].status == campaigns.SUBMITTED
    assert not any("expired" in n.message for n in _rows(client, Notification, user_id=biz))


def test_a_campaign_carrying_a_contract_is_never_cancelled_by_the_sweep(client, admin_headers):
    """The contract guard on its own, with no stranger involved.

    The lapsed row below belongs to the ADDRESSED creator, so it clears the
    invitation half and only the contract half can stop it. That state is not
    reachable through the API today — submit_proposal refuses a new version
    once the chain is accepted — so it is seeded, because what is being pinned
    is the invariant rather than a path: a campaign that already carries an
    agreement is not the sweep's to cancel, whoever the lapsed row belongs to.

    AND THE WAY IN IS SHUT AT THE OTHER END TOO, which the last assertion
    covers. Once this row exists it is what latest_in_chain returns, and it is
    `submitted` — so the accepted-chain guard named above does NOT refuse a
    further counter on it: the accepted row is not the latest any more. What
    refuses it is the expiry check submit_proposal gained alongside this,
    which was the one path in the codebase that never asked. Without it a
    creator could pile version onto version of an order that no longer has a
    window, and every one of them would be dead on arrival — unacceptable,
    unanswerable and uncontractable by anybody.
    """
    biz, creator, pkg = _setup(client)
    order = _order(client, biz, pkg).json()
    contract = client.post(
        f"/campaigns/orders/{order['proposal_id']}/accept", headers=_headers(creator)
    ).json()

    db = client.session_factory()
    try:
        db.add(
            campaigns.Proposal(
                campaign_id=order["campaign_id"],
                influencer_user_id=creator,
                version=2,
                rate_amount=25000,
                rate_currency="XOF",
                timeline_days=7,
                author_role=campaigns.AUTHOR_INFLUENCER,
                status=campaigns.SUBMITTED,
                expires_at=campaigns.utcnow() - timedelta(hours=1),
            )
        )
        db.commit()
    finally:
        db.close()

    assert client.post("/campaigns/orders/expire", headers=admin_headers).json() == {"expired": 0}
    assert _rows(client, campaigns.Campaign, id=order["campaign_id"])[0].status == campaigns.PUBLISHED
    assert _rows(client, contracts.Contract, id=contract["id"])[0].status == contracts.PENDING

    # The chain takes no further versions either, and order_expired is what
    # says so. See the docstring for why it is this guard and not the
    # accepted-chain one.
    refused = client.post(
        f"/campaigns/{order['campaign_id']}/proposals",
        json={"rate_amount": 30000, "rate_currency": "XOF", "timeline_days": 9},
        headers=_headers(creator),
    )
    assert refused.status_code == 400
    assert refused.json()["code"] == "order_expired"
    # Two rows still, and the lapsed one was not superseded on the way out:
    # a refusal that rewrote the chain would be the worse half of the bug.
    chain = _rows(client, campaigns.Proposal, campaign_id=order["campaign_id"])
    assert len(chain) == 2
    assert [p.status for p in sorted(chain, key=lambda p: p.version)] == [
        campaigns.PROPOSAL_ACCEPTED,
        campaigns.SUBMITTED,
    ]


def test_a_genuinely_lapsed_order_still_expires_beside_an_orphan_chain(client, admin_headers):
    """The guard must not have disabled the feature it is guarding.

    Both rows on ONE campaign and both past their window: the buyer's real
    order, unanswered, and a stranger's chain. Exactly one of the two is an
    order that lapsed, so exactly one thing ends and the count says one — a
    skipped row is not an expired row.
    """
    biz, creator, pkg = _setup(client)
    order = _order(client, biz, pkg).json()
    stranger = _outsider(client)
    orphan = _stranger_chain(client, order["campaign_id"], stranger)
    _age_out(client, order["proposal_id"])
    _age_out(client, orphan)

    assert client.post("/campaigns/orders/expire", headers=admin_headers).json() == {"expired": 1}

    # The order ended exactly as it did before the guard existed.
    assert _rows(client, campaigns.Proposal, id=order["proposal_id"])[0].status == campaigns.PROPOSAL_DECLINED
    assert _rows(client, campaigns.Campaign, id=order["campaign_id"])[0].status == campaigns.CANCELLED
    assert _rows(client, campaigns.CampaignInvitation, campaign_id=order["campaign_id"])[0].status == campaigns.DECLINED
    assert any("expired" in n.message for n in _rows(client, Notification, user_id=biz))
    assert any("expired" in n.message for n in _rows(client, Notification, user_id=creator))

    # The orphan was passed over, and was never counted as one of the expired.
    assert _rows(client, campaigns.Proposal, id=orphan)[0].status == campaigns.SUBMITTED
    assert _rows(client, Notification, user_id=stranger) == []

"""Editing, deleting and cancelling a campaign.

The claim under test is one rule with three faces: what a buyer may still
change depends entirely on who is already looking at the campaign.

  * A draft is one person's notes. Everything is editable and the row can go.
  * A published brief with a proposal on it has somebody's evening in it. The
    terms they priced against — budget, currency, deliverables, deadline —
    stop being the buyer's alone, while the words around them stay editable.
  * A campaign with anything attached is cancelled, never deleted, because
    proposals and contracts are the other party's record too.

A separate file from test_campaigns.py, which is about creating a brief and
running the negotiation on it.
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
from app.modules.notifications.models import Notification
from app.modules.profiles.models import Package


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
    app.include_router(campaigns_router, prefix="/campaigns")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _user(client, phone, role="business"):
    db = client.session_factory()
    try:
        u = User(phone=phone, password_hash="x", country_code="BJ", role=role, is_verified=True)
        db.add(u); db.commit(); db.refresh(u)
        return u.id
    finally:
        db.close()


def _rows(client, model, **filters):
    db = client.session_factory()
    try:
        query = db.query(model)
        for field, value in filters.items():
            query = query.filter(getattr(model, field) == value)
        return query.all()
    finally:
        db.close()


DRAFT_BODY = {
    "title": "Idea only",
    "description": "Rough thoughts",
}

PUBLISHED_BODY = {
    "title": "Launch push",
    "description": "Warm, everyday, no studio lighting.",
    "budget_amount": 500000,
    "budget_currency": "XOF",
    "deliverables": [{"platform": "instagram", "type": "post", "quantity": 2}],
    "deadline": "2026-12-01",
    "publish": True,
}


def _draft(client, biz):
    return client.post("/campaigns/", json=DRAFT_BODY, headers=_headers(biz)).json()


def _published(client, biz):
    return client.post("/campaigns/", json=PUBLISHED_BODY, headers=_headers(biz)).json()


def _propose(client, campaign_id, creator):
    return client.post(
        f"/campaigns/{campaign_id}/proposals",
        json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7},
        headers=_headers(creator),
    )


def _contract_on(client, campaign_id, biz, creator):
    """A contract written straight into the database.

    The route that produces one honestly (accept a proposal) is tested in the
    contracts suite; here the contract is only a fact the campaign has to
    respect, so it is created directly rather than dragging the whole accept
    flow into every test.
    """
    db = client.session_factory()
    try:
        proposal = (
            db.query(campaigns.Proposal)
            .filter(campaigns.Proposal.campaign_id == campaign_id)
            .first()
        )
        db.add(contracts.Contract(
            campaign_id=campaign_id,
            proposal_id=proposal.id,
            business_user_id=biz,
            influencer_user_id=creator,
            language="fr",
            body="placeholder",
            rate_amount=40000,
            rate_currency="XOF",
            timeline_days=7,
            deliverables=[],
            status=contracts.PENDING,
        ))
        db.commit()
    finally:
        db.close()


# --------------------------------------------------------------------------
# A draft is one person's notes
# --------------------------------------------------------------------------


def test_a_draft_is_fully_editable(client):
    """Nobody has seen it, so there is nothing to protect."""
    biz = _user(client, "+22990020001")
    draft = _draft(client, biz)

    r = client.patch(
        f"/campaigns/{draft['id']}",
        json={
            "title": "Now a real brief",
            "description": "Rewritten from scratch",
            "budget_amount": 250000,
            "budget_currency": "XOF",
            "deliverables": [{"platform": "tiktok", "type": "video", "quantity": 4}],
            "deadline": "2027-01-15",
        },
        headers=_headers(biz),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Now a real brief"
    assert body["description"] == "Rewritten from scratch"
    assert body["budget_amount"] == 250000
    assert body["deliverables"] == [{"platform": "tiktok", "type": "video", "quantity": 4}]
    assert body["deadline"] == "2027-01-15"
    assert body["status"] == campaigns.DRAFT


def test_a_patch_only_touches_what_it_sends(client):
    """exclude_unset, the same contract the profile upsert runs on: a form
    that edits the title must not blank the budget by not mentioning it."""
    biz = _user(client, "+22990020002")
    published = _published(client, biz)

    body = client.patch(
        f"/campaigns/{published['id']}",
        json={"title": "Launch push (v2)"},
        headers=_headers(biz),
    ).json()
    assert body["title"] == "Launch push (v2)"
    assert body["budget_amount"] == 500000
    assert body["description"] == "Warm, everyday, no studio lighting."
    assert body["deliverables"] == [{"platform": "instagram", "type": "post", "quantity": 2}]


def test_an_edit_cannot_smuggle_in_a_deliverable_the_catalog_rejects(client):
    """The same check create and publish run. An edit must not be the way a
    brief ends up asking for something no platform sells."""
    biz = _user(client, "+22990020003")
    draft = _draft(client, biz)
    r = client.patch(
        f"/campaigns/{draft['id']}",
        json={"deliverables": [{"platform": "instagram", "type": "short", "quantity": 1}]},
        headers=_headers(biz),
    )
    assert r.status_code == 400
    assert "short" in r.json()["detail"] and "reel" in r.json()["detail"]


def test_a_draft_with_nothing_attached_is_deleted_outright(client):
    biz = _user(client, "+22990020004")
    draft = _draft(client, biz)

    r = client.delete(f"/campaigns/{draft['id']}", headers=_headers(biz))
    assert r.status_code == 200
    assert r.json() == {"id": draft["id"], "deleted": True}
    assert _rows(client, campaigns.Campaign, id=draft["id"]) == []
    # And its invitation rows go with it — empty here, because a draft cannot
    # be invited to, which is exactly why deleting one is safe.
    assert _rows(client, campaigns.CampaignInvitation, campaign_id=draft["id"]) == []


# --------------------------------------------------------------------------
# Published: the terms lock once somebody has priced against them
# --------------------------------------------------------------------------


def test_a_published_brief_with_no_proposals_can_still_change_everything(client):
    """Live is not the same as relied upon. No creator has spent an evening
    pricing this yet, so fixing a budget with a missing zero costs nobody."""
    biz = _user(client, "+22990020005")
    published = _published(client, biz)

    r = client.patch(
        f"/campaigns/{published['id']}",
        json={
            "budget_amount": 900000,
            "budget_currency": "GHS",
            "deliverables": [{"platform": "instagram", "type": "reel", "quantity": 1}],
            "deadline": "2027-02-02",
        },
        headers=_headers(biz),
    )
    assert r.status_code == 200
    assert r.json()["budget_amount"] == 900000
    assert r.json()["budget_currency"] == "GHS"
    assert r.json()["deadline"] == "2027-02-02"


@pytest.mark.parametrize(
    "field,value",
    [
        ("budget_amount", 200000),
        ("budget_currency", "GHS"),
        ("deliverables", [{"platform": "instagram", "type": "post", "quantity": 6}]),
        ("deadline", "2027-03-03"),
    ],
)
def test_a_proposal_locks_the_terms_it_was_priced_against(client, field, value):
    """A creator who bid 40k for two posts against 500k did not bid for six
    posts against 200k. Changing it silently would turn a submitted bid into
    a bid for different work."""
    biz = _user(client, "+22990020006")
    creator = _user(client, "+22990020007", role="influencer")
    published = _published(client, biz)
    assert _propose(client, published["id"], creator).status_code == 201

    r = client.patch(f"/campaigns/{published['id']}", json={field: value}, headers=_headers(biz))
    assert r.status_code == 400
    assert field in r.json()["detail"]
    # Nothing moved.
    assert client.get(f"/campaigns/{published['id']}", headers=_headers(biz)).json()["budget_amount"] == 500000


def test_the_words_around_the_terms_stay_editable(client):
    """Title and description are description, not terms: rewriting them does
    not change what the creator bid FOR."""
    biz = _user(client, "+22990020008")
    creator = _user(client, "+22990020009", role="influencer")
    published = _published(client, biz)
    _propose(client, published["id"], creator)

    r = client.patch(
        f"/campaigns/{published['id']}",
        json={"title": "Launch push — December", "description": "Clearer brief"},
        headers=_headers(biz),
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Launch push — December"
    assert r.json()["description"] == "Clearer brief"


def test_resending_a_locked_field_unchanged_is_not_a_change(client):
    """Clients post whole forms. Failing a PATCH that asked for nothing would
    make the title uneditable in every UI that does."""
    biz = _user(client, "+22990020010")
    creator = _user(client, "+22990020011", role="influencer")
    published = _published(client, biz)
    _propose(client, published["id"], creator)

    r = client.patch(
        f"/campaigns/{published['id']}",
        json={
            "title": "Same brief, new title",
            "budget_amount": 500000,
            "budget_currency": "XOF",
            "deliverables": [{"platform": "instagram", "type": "post", "quantity": 2}],
            "deadline": "2026-12-01",
        },
        headers=_headers(biz),
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Same brief, new title"


# --------------------------------------------------------------------------
# Deleting versus cancelling
# --------------------------------------------------------------------------


def test_a_campaign_with_activity_is_never_deleted(client):
    """A proposal is somebody else's work, and an invitation is somebody else
    holding a date. Neither is the buyer's to erase."""
    biz = _user(client, "+22990020012")
    creator = _user(client, "+22990020013", role="influencer")
    published = _published(client, biz)

    # Published alone already counts: it has been shown to the market.
    r = client.delete(f"/campaigns/{published['id']}", headers=_headers(biz))
    assert r.status_code == 409
    assert r.json()["detail"] == "This campaign has activity; cancel it instead."

    client.post(
        f"/campaigns/{published['id']}/invitations",
        json={"influencer_id": creator},
        headers=_headers(biz),
    )
    _propose(client, published["id"], creator)
    assert client.delete(f"/campaigns/{published['id']}", headers=_headers(biz)).status_code == 409
    assert _rows(client, campaigns.Campaign, id=published["id"]) != []
    assert _rows(client, campaigns.Proposal, campaign_id=published["id"]) != []


def test_cancelling_keeps_everything_and_tells_the_invited_creators(client):
    biz = _user(client, "+22990020014")
    creator = _user(client, "+22990020015", role="influencer")
    published = _published(client, biz)
    client.post(
        f"/campaigns/{published['id']}/invitations",
        json={"influencer_id": creator},
        headers=_headers(biz),
    )
    _propose(client, published["id"], creator)

    r = client.post(f"/campaigns/{published['id']}/cancel", headers=_headers(biz))
    assert r.status_code == 200
    assert r.json()["status"] == campaigns.CANCELLED

    # The record survives: that is the entire difference from a delete.
    assert _rows(client, campaigns.Campaign, id=published["id"]) != []
    assert len(_rows(client, campaigns.Proposal, campaign_id=published["id"])) == 1
    assert len(_rows(client, campaigns.CampaignInvitation, campaign_id=published["id"])) == 1

    kinds = [n.type for n in _rows(client, Notification, user_id=creator)]
    assert "campaign_cancelled" in kinds


def test_cancelling_closes_the_live_bids_and_the_open_invitations(client):
    """Cancelling used to move the status and leave everything under it alone:
    the proposal stayed `submitted` and the invitation stayed `invited` on a
    brief that no longer existed. That is the state withdraw_invitation refuses
    against ("this creator has already sent a proposal") and the one contract
    generation had to grow a guard for. A terminal state now closes what hangs
    off it, through the same code completion uses."""
    biz = _user(client, "+22990020026")
    creator = _user(client, "+22990020027", role="influencer")
    published = _published(client, biz)
    client.post(
        f"/campaigns/{published['id']}/invitations",
        json={"influencer_id": creator},
        headers=_headers(biz),
    )
    _propose(client, published["id"], creator)

    assert client.post(f"/campaigns/{published['id']}/cancel", headers=_headers(biz)).status_code == 200

    proposal = _rows(client, campaigns.Proposal, campaign_id=published["id"])[0]
    assert proposal.status == campaigns.PROPOSAL_REJECTED
    invitation = _rows(client, campaigns.CampaignInvitation, campaign_id=published["id"])[0]
    assert invitation.status == campaigns.WITHDRAWN
    # Withdrawn, not declined: the creator refused nothing.
    assert invitation.status != campaigns.DECLINED


def test_cancelling_does_not_also_claim_the_brief_was_filled(client):
    """The cascade is shared with completion; the message is not. Cancelling
    has just told every invited creator the brief is off, and a second row
    saying their proposal is closed because it was FILLED is both noise and
    untrue — nothing was filled here."""
    biz = _user(client, "+22990020028")
    creator = _user(client, "+22990020029", role="influencer")
    published = _published(client, biz)
    client.post(
        f"/campaigns/{published['id']}/invitations",
        json={"influencer_id": creator},
        headers=_headers(biz),
    )
    _propose(client, published["id"], creator)
    client.post(f"/campaigns/{published['id']}/cancel", headers=_headers(biz))

    rows = _rows(client, Notification, user_id=creator)
    keys = [(n.params or {}).get("key") for n in rows]
    assert "campaign_cancelled" in keys
    assert "brief_filled" not in keys
    assert [n.type for n in rows].count("proposal_closed") == 0


def test_cancelling_twice_is_refused_rather_than_notifying_twice(client):
    biz = _user(client, "+22990020016")
    published = _published(client, biz)
    assert client.post(f"/campaigns/{published['id']}/cancel", headers=_headers(biz)).status_code == 200
    assert client.post(f"/campaigns/{published['id']}/cancel", headers=_headers(biz)).status_code == 400


def test_a_cancelled_campaign_is_not_editable(client):
    biz = _user(client, "+22990020017")
    published = _published(client, biz)
    client.post(f"/campaigns/{published['id']}/cancel", headers=_headers(biz))
    r = client.patch(f"/campaigns/{published['id']}", json={"title": "Reopened?"}, headers=_headers(biz))
    assert r.status_code == 400


def test_a_contract_takes_cancelling_out_of_the_buyers_hands(client):
    """Two parties agreed terms and money may already be in escrow against
    them. Ending that is the dispute and refund path, which has the rules."""
    biz = _user(client, "+22990020018")
    creator = _user(client, "+22990020019", role="influencer")
    published = _published(client, biz)
    _propose(client, published["id"], creator)
    _contract_on(client, published["id"], biz, creator)

    r = client.post(f"/campaigns/{published['id']}/cancel", headers=_headers(biz))
    assert r.status_code == 409
    assert "dispute" in r.json()["detail"]
    assert _rows(client, campaigns.Campaign, id=published["id"])[0].status == campaigns.PUBLISHED


# --------------------------------------------------------------------------
# Who may do any of it
# --------------------------------------------------------------------------


def test_only_the_owner_can_edit_delete_or_cancel(client):
    biz = _user(client, "+22990020020")
    other = _user(client, "+22990020021")
    draft = _draft(client, biz)

    assert client.patch(f"/campaigns/{draft['id']}", json={"title": "Mine now"}, headers=_headers(other)).status_code == 403
    assert client.delete(f"/campaigns/{draft['id']}", headers=_headers(other)).status_code == 403
    assert client.post(f"/campaigns/{draft['id']}/cancel", headers=_headers(other)).status_code == 403
    assert _rows(client, campaigns.Campaign, id=draft["id"])[0].title == "Idea only"


def test_editing_requires_auth(client):
    biz = _user(client, "+22990020022")
    draft = _draft(client, biz)
    assert client.patch(f"/campaigns/{draft['id']}", json={"title": "x"}).status_code == 401
    assert client.delete(f"/campaigns/{draft['id']}").status_code == 401
    assert client.post(f"/campaigns/{draft['id']}/cancel").status_code == 401


def test_an_unknown_campaign_is_404(client):
    biz = _user(client, "+22990020023")
    assert client.patch("/campaigns/nope", json={"title": "x"}, headers=_headers(biz)).status_code == 404
    assert client.delete("/campaigns/nope", headers=_headers(biz)).status_code == 404
    assert client.post("/campaigns/nope/cancel", headers=_headers(biz)).status_code == 404


# --------------------------------------------------------------------------
# A direct order is not a document one side edits
# --------------------------------------------------------------------------


def _order(client, biz, creator):
    db = client.session_factory()
    try:
        pkg = Package(
            user_id=creator, platform="instagram", deliverable_type="reel",
            title="Two reels", price_amount=25000, currency="XOF", quantity=2, is_active=True,
        )
        db.add(pkg); db.commit(); db.refresh(pkg)
        package_id = pkg.id
    finally:
        db.close()
    return client.post("/campaigns/orders", json={"package_id": package_id}, headers=_headers(biz)).json()


def test_a_direct_order_is_not_editable_through_these_endpoints(client):
    """An order is a transaction: the buyer named terms and the creator is
    answering exactly those. Moving them under the creator mid-decision is
    what countering exists for, and it is visible to both sides."""
    biz = _user(client, "+22990020024")
    creator = _user(client, "+22990020025", role="influencer")
    order = _order(client, biz, creator)

    patched = client.patch(
        f"/campaigns/{order['campaign_id']}",
        json={"title": "Actually four reels"},
        headers=_headers(biz),
    )
    assert patched.status_code == 400
    assert "direct order" in patched.json()["detail"].lower()

    assert client.delete(f"/campaigns/{order['campaign_id']}", headers=_headers(biz)).status_code == 400
    assert client.post(f"/campaigns/{order['campaign_id']}/cancel", headers=_headers(biz)).status_code == 400

    # Untouched: still a live order the creator can answer.
    campaign = _rows(client, campaigns.Campaign, id=order["campaign_id"])[0]
    assert campaign.title == "Two reels"
    assert campaign.status == campaigns.PUBLISHED

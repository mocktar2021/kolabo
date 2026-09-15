"""Tests for Epic D (KOL-11): campaigns, invitations, proposals."""
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.campaigns.router import router as campaigns_router
from app.modules.profiles.models import BusinessProfile, InfluencerProfile

# A brief past its deadline takes no proposals (campaigns.service), so the
# briefs here have to stay live as the calendar moves rather than until a
# literal arrives.
LIVE_DEADLINE = date.today() + timedelta(days=90)


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
    app.include_router(campaigns_router, prefix="/campaigns")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = testing_session
    return c


def _user(client, phone, role, verified=True):
    db = client.session_factory()
    try:
        u = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x", country_code="BJ", role=role, is_verified=verified)
        db.add(u); db.commit(); db.refresh(u)
        return u.id, {"Authorization": f"Bearer {create_access_token(u.id)}"}
    finally:
        db.close()


def _business_profile(client, user_id, company_name):
    db = client.session_factory()
    try:
        db.add(BusinessProfile(user_id=user_id, company_name=company_name))
        db.commit()
    finally:
        db.close()


def _influencer_profile(client, user_id, display_name, avatar_media_id=None):
    """The creator's public identity, which is what a proposal row shows."""
    db = client.session_factory()
    try:
        db.add(InfluencerProfile(
            user_id=user_id, display_name=display_name, avatar_media_id=avatar_media_id,
        ))
        db.commit()
    finally:
        db.close()


def _published_campaign(client, headers):
    r = client.post("/campaigns/", json={
        "title": "Launch push",
        "budget_amount": 50000,
        "budget_currency": "XOF",
        "deliverables": [{"platform": "instagram", "type": "post", "quantity": 2}],
        "deadline": str(LIVE_DEADLINE),
        "publish": True,
        "is_open": True,
    }, headers=headers)
    return r


def test_draft_save_allows_missing_fields(client):
    _, headers = _user(client, "+22990000001", "business")
    r = client.post("/campaigns/", json={"title": "Idea only"}, headers=headers)
    assert r.status_code == 201
    assert r.json()["status"] == "draft"


def test_publish_requires_budget_deliverables_deadline(client):
    _, headers = _user(client, "+22990000002", "business")
    r = client.post("/campaigns/", json={"title": "Incomplete", "publish": True}, headers=headers)
    assert r.status_code == 400


def test_create_published_with_all_fields(client):
    _, headers = _user(client, "+22990000003", "business")
    r = _published_campaign(client, headers)
    assert r.status_code == 201
    assert r.json()["status"] == "published"


def test_invite_verified_influencer_notifies(client):
    _, biz = _user(client, "+22990000004", "business")
    inf_id, _ = _user(client, "+22990000005", "influencer", verified=True)
    camp = _published_campaign(client, biz).json()
    r = client.post(f"/campaigns/{camp['id']}/invitations", json={"influencer_id": inf_id}, headers=biz)
    assert r.status_code == 201
    from app.modules.notifications.models import Notification
    db = client.session_factory()
    note = db.query(Notification).filter(Notification.user_id == inf_id).first()
    db.close()
    assert note is not None and note.type == "campaign_invitation"


def test_invite_unverified_influencer_blocked(client):
    _, biz = _user(client, "+22990000006", "business")
    inf_id, _ = _user(client, "+22990000007", "influencer", verified=False)
    camp = _published_campaign(client, biz).json()
    r = client.post(f"/campaigns/{camp['id']}/invitations", json={"influencer_id": inf_id}, headers=biz)
    assert r.status_code == 400


def test_invite_requires_ownership(client):
    _, biz = _user(client, "+22990000008", "business")
    _, other = _user(client, "+22990000009", "business")
    inf_id, _ = _user(client, "+22990000010", "influencer")
    camp = _published_campaign(client, biz).json()
    r = client.post(f"/campaigns/{camp['id']}/invitations", json={"influencer_id": inf_id}, headers=other)
    assert r.status_code == 403


def test_proposal_versions_and_supersede(client):
    _, biz = _user(client, "+22990000011", "business")
    inf_id, inf = _user(client, "+22990000012", "influencer")
    camp = _published_campaign(client, biz).json()
    r1 = client.post(f"/campaigns/{camp['id']}/proposals", json={"rate_amount": 10000, "rate_currency": "xof", "timeline_days": 7}, headers=inf)
    assert r1.status_code == 201
    assert r1.json()["version"] == 1
    assert r1.json()["rate_currency"] == "XOF"
    r2 = client.post(f"/campaigns/{camp['id']}/proposals", json={"rate_amount": 12000, "rate_currency": "XOF", "timeline_days": 10}, headers=inf)
    assert r2.json()["version"] == 2
    # The business owner is notified of the proposal.
    from app.modules.notifications.models import Notification
    db = client.session_factory()
    notes = db.query(Notification).filter(Notification.type == "proposal_submitted").all()
    # First submitted proposal is now superseded.
    from app.modules.campaigns.models import Proposal
    v1 = db.query(Proposal).filter(Proposal.version == 1).first()
    db.close()
    assert len(notes) == 2
    assert v1.status == "superseded"


def test_endpoints_require_auth(client):
    r = client.post("/campaigns/", json={"title": "x"})
    assert r.status_code == 401


def test_list_my_campaigns_only_mine(client):
    _, biz_a = _user(client, "+22990000101", "business")
    _, biz_b = _user(client, "+22990000102", "business")
    _published_campaign(client, biz_a)
    client.post("/campaigns/", json={"title": "Draft only"}, headers=biz_a)
    _published_campaign(client, biz_b)

    mine = client.get("/campaigns/mine", headers=biz_a).json()
    assert len(mine) == 2
    assert {c["title"] for c in mine} == {"Launch push", "Draft only"}
    other = client.get("/campaigns/mine", headers=biz_b).json()
    assert len(other) == 1


def test_campaign_detail_shows_invitations_and_proposals(client):
    _, biz = _user(client, "+22990000103", "business")
    inf_id, inf = _user(client, "+22990000104", "influencer")
    cid = _published_campaign(client, biz).json()["id"]
    client.post(f"/campaigns/{cid}/invitations", json={"influencer_id": inf_id}, headers=biz)
    client.post(f"/campaigns/{cid}/proposals", json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7}, headers=inf)

    detail = client.get(f"/campaigns/{cid}", headers=biz).json()
    assert detail["id"] == cid
    assert len(detail["invitations"]) == 1
    assert detail["invitations"][0]["influencer_user_id"] == inf_id
    assert len(detail["proposals"]) == 1
    assert detail["proposals"][0]["rate_amount"] == 40000


def test_campaign_detail_owner_only(client):
    _, biz = _user(client, "+22990000105", "business")
    _, other = _user(client, "+22990000106", "business")
    cid = _published_campaign(client, biz).json()["id"]
    assert client.get(f"/campaigns/{cid}", headers=other).status_code == 403


def test_list_my_invitations_for_influencer(client):
    _, biz = _user(client, "+22990000107", "business")
    inf_id, inf = _user(client, "+22990000108", "influencer")
    cid = _published_campaign(client, biz).json()["id"]
    client.post(f"/campaigns/{cid}/invitations", json={"influencer_id": inf_id}, headers=biz)

    invites = client.get("/campaigns/invitations/mine", headers=inf).json()
    assert len(invites) == 1
    assert invites[0]["campaign"]["id"] == cid
    assert invites[0]["campaign"]["title"] == "Launch push"


def test_invitation_carries_the_full_brief_and_company_name(client):
    """The invitation card is where a creator decides what to charge, so it
    carries what they are pricing — deliverables as stored, budget, deadline,
    title — and the name of the buyer asking for it."""
    biz_id, biz = _user(client, "+22990000109", "business")
    inf_id, inf = _user(client, "+22990000110", "influencer")
    _business_profile(client, biz_id, "Maison Kola")
    cid = _published_campaign(client, biz).json()["id"]
    client.post(f"/campaigns/{cid}/invitations", json={"influencer_id": inf_id}, headers=biz)

    row = client.get("/campaigns/invitations/mine", headers=inf).json()[0]
    assert row["business_company_name"] == "Maison Kola"
    brief = row["campaign"]
    assert brief["deliverables"] == [{"platform": "instagram", "type": "post", "quantity": 2}]
    assert brief["title"] == "Launch push"
    assert brief["budget_amount"] == 50000
    assert brief["budget_currency"] == "XOF"
    assert brief["deadline"] == str(LIVE_DEADLINE)


def test_invitation_company_name_is_null_without_a_business_profile(client):
    """No profile means no name. It must never fall back to the users table:
    the only identifier there is a phone number."""
    biz_id, biz = _user(client, "+22990000111", "business")
    inf_id, inf = _user(client, "+22990000112", "influencer")
    cid = _published_campaign(client, biz).json()["id"]
    client.post(f"/campaigns/{cid}/invitations", json={"influencer_id": inf_id}, headers=biz)

    row = client.get("/campaigns/invitations/mine", headers=inf).json()[0]
    assert row["business_company_name"] is None
    assert "+22990000111" not in str(row)


def test_proposal_row_names_the_proposer(client):
    """The business is choosing between people. A row reading "Créateur
    424275c0" cannot be chosen, so the proposal carries the creator's name
    and photo."""
    _, biz = _user(client, "+22990000113", "business")
    inf_id, inf = _user(client, "+22990000114", "influencer")
    _influencer_profile(client, inf_id, "Ama K.", avatar_media_id="media-abc")
    cid = _published_campaign(client, biz).json()["id"]
    client.post(f"/campaigns/{cid}/proposals", json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7}, headers=inf)

    row = client.get(f"/campaigns/{cid}", headers=biz).json()["proposals"][0]
    assert row["influencer_user_id"] == inf_id
    assert row["display_name"] == "Ama K."
    assert row["avatar_url"] == "/profiles/media/media-abc"


def test_proposal_row_is_null_without_a_creator_profile(client):
    """Same rule as the invitation card: no profile means no name, and never
    a phone number standing in for one."""
    _, biz = _user(client, "+22990000115", "business")
    inf_id, inf = _user(client, "+22990000116", "influencer")
    cid = _published_campaign(client, biz).json()["id"]
    client.post(f"/campaigns/{cid}/proposals", json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7}, headers=inf)

    row = client.get(f"/campaigns/{cid}", headers=biz).json()["proposals"][0]
    assert row["display_name"] is None
    assert row["avatar_url"] is None
    assert "+22990000116" not in str(row)


def test_mine_requires_auth(client):
    assert client.get("/campaigns/mine").status_code == 401


def test_create_with_invalid_pair_rejected(client):
    """A "short" exists on YouTube, not Instagram: the catalog rejects the
    pair and the error says what Instagram actually offers."""
    _, headers = _user(client, "+22990000201", "business")
    r = client.post("/campaigns/", json={
        "title": "Bad brief",
        "deliverables": [{"platform": "instagram", "type": "short", "quantity": 1}],
    }, headers=headers)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "short" in detail and "instagram" in detail
    # The error teaches: it lists what IS allowed on the platform.
    assert "reel" in detail


def test_create_with_unknown_platform_rejected(client):
    _, headers = _user(client, "+22990000202", "business")
    r = client.post("/campaigns/", json={
        "title": "Typo brief",
        "deliverables": [{"platform": "instagramm", "type": "post", "quantity": 1}],
    }, headers=headers)
    assert r.status_code == 400
    assert "instagramm" in r.json()["detail"]


def test_ugc_deliverables_accepted(client):
    """UGC is a first-class part of the catalog: briefs can ask for ad
    creative that never gets posted on the creator's own account."""
    _, headers = _user(client, "+22990000203", "business")
    r = client.post("/campaigns/", json={
        "title": "Ad creative batch",
        "budget_amount": 80000,
        "budget_currency": "XOF",
        "deliverables": [{"platform": "ugc", "type": "ugc_video", "quantity": 3}],
        "deadline": str(LIVE_DEADLINE),
        "publish": True,
    }, headers=headers)
    assert r.status_code == 201
    assert r.json()["status"] == "published"


def test_publish_still_requires_nonempty_deliverables(client):
    """Catalog validation passes an empty list through, but publishing still
    demands at least one deliverable — that gate is _publish_ready's."""
    _, headers = _user(client, "+22990000204", "business")
    r = client.post("/campaigns/", json={
        "title": "No deliverables",
        "budget_amount": 10000,
        "budget_currency": "XOF",
        "deadline": str(LIVE_DEADLINE),
    }, headers=headers)
    assert r.status_code == 201
    cid = r.json()["id"]
    assert client.post(f"/campaigns/{cid}/publish", headers=headers).status_code == 400


def test_deliverable_quantity_zero_rejected(client):
    # The schema floor (ge=1) catches zero before the service range check.
    _, headers = _user(client, "+22990000205", "business")
    r = client.post("/campaigns/", json={
        "title": "Zero of something",
        "deliverables": [{"platform": "instagram", "type": "post", "quantity": 0}],
    }, headers=headers)
    assert r.status_code == 422


def test_deliverable_quantity_over_cap_rejected(client):
    # Past the cap the number is a typo, not a brief; the service says so.
    _, headers = _user(client, "+22990000206", "business")
    r = client.post("/campaigns/", json={
        "title": "Impossible volume",
        "deliverables": [{"platform": "instagram", "type": "post", "quantity": 101}],
    }, headers=headers)
    assert r.status_code == 400


def test_influencer_cannot_create_campaign(client):
    """A campaign is a brand-side brief; a creator's equivalent is packages.
    Creators posting briefs muddles who is buying, and everything downstream
    of a campaign assumes a business counterparty."""
    _, headers = _user(client, "+22990000301", "influencer")
    r = client.post("/campaigns/", json={"title": "Hire me"}, headers=headers)
    assert r.status_code == 403
    assert r.json()["detail"] == "Only businesses and agencies can create campaigns."


def test_influencer_blocked_before_payload_validation(client):
    """The gate is about the caller, not the brief: a creator gets the role
    error, not a lecture about their deliverables."""
    _, headers = _user(client, "+22990000302", "influencer")
    r = client.post("/campaigns/", json={
        "title": "Hire me",
        "deliverables": [{"platform": "instagramm", "type": "post", "quantity": 1}],
    }, headers=headers)
    assert r.status_code == 403


def test_business_can_create_campaign(client):
    _, headers = _user(client, "+22990000303", "business")
    r = client.post("/campaigns/", json={"title": "Brand brief"}, headers=headers)
    assert r.status_code == 201


def test_agency_can_create_campaign(client):
    """Agencies buy on behalf of brands: same side of the market as a
    business, so they brief just like one."""
    _, headers = _user(client, "+22990000304", "agency")
    r = client.post("/campaigns/", json={"title": "Client brief"}, headers=headers)
    assert r.status_code == 201

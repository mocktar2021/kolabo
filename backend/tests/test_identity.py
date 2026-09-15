"""One identity shape, everywhere a creator is listed.

A business used to get three different answers to "who is this person" on one
screen: the favourites list had a name and a photo, the proposals list had its
own name and photo, and the invitations list had a raw user id. These tests
pin the shared shape (app.core.identity) down on every surface that spends it,
and pin the one rule that is easy to get wrong: the audience number is the
biggest single platform, never a sum across platforms.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db, import_all_models
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.campaigns.router import router as campaigns_router
from app.modules.discovery.router import router as discovery_router
from app.modules.profiles import models as pmodels


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    import_all_models()
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    # Both surfaces in one app on purpose: the whole claim under test is that
    # a favourite row and a campaign row describe a creator the same way.
    app.include_router(discovery_router, prefix="/discovery")
    app.include_router(campaigns_router, prefix="/campaigns")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _business(client, phone="+22990001000"):
    db = client.session_factory()
    try:
        user = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x", country_code="BJ", role="business", is_verified=True)
        db.add(user); db.commit(); db.refresh(user)
        return user.id
    finally:
        db.close()


def _creator(client, phone, display_name="Ama K.", with_profile=True, with_avatar=False):
    """A creator, optionally with a profile and an avatar. Returns (id, media_id)."""
    db = client.session_factory()
    try:
        user = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add(user); db.commit(); db.refresh(user)
        media_id = None
        if with_avatar:
            asset = pmodels.MediaAsset(owner_user_id=user.id, content_type="image/png", data=b"fake")
            db.add(asset); db.commit(); db.refresh(asset)
            media_id = asset.id
        if with_profile:
            db.add(pmodels.InfluencerProfile(
                user_id=user.id,
                display_name=display_name,
                headline="Lifestyle creator",
                bio="Creator",
                categories=["fashion"],
                rate_card={},
                avatar_media_id=media_id,
            ))
            db.commit()
        return user.id, media_id
    finally:
        db.close()


def _social(client, user_id, platform, followers, handle="handle"):
    db = client.session_factory()
    try:
        db.add(pmodels.SocialAccount(
            user_id=user_id, platform=platform, handle=handle, method="manual",
            status="verified", follower_count=followers,
        ))
        db.commit()
    finally:
        db.close()


def _published_campaign(client, biz):
    return client.post(
        "/campaigns/",
        json={
            "title": "Ramadan push",
            "budget_amount": 500000,
            "budget_currency": "XOF",
            "deliverables": [{"platform": "instagram", "type": "post", "quantity": 3}],
            "deadline": "2026-12-01",
            "publish": True,
        },
        headers=_headers(biz),
    ).json()


def test_a_favourite_row_carries_the_name_the_face_and_the_audience(client):
    """Inviting somebody to a campaign starts from this list, so the row has
    to be a person: a name, a face, and the audience they reach."""
    creator, media_id = _creator(client, "+22990001001", with_avatar=True)
    _social(client, creator, "instagram", 42000)
    biz = _business(client)

    assert client.post(f"/discovery/favorites/{creator}", headers=_headers(biz)).status_code == 201
    row = client.get("/discovery/favorites", headers=_headers(biz)).json()[0]
    assert row["display_name"] == "Ama K."
    assert row["avatar_url"] == f"/profiles/media/{media_id}"
    assert row["top_platform"] == "instagram"
    assert row["top_follower_count"] == 42000
    # Never, on any surface: the users table's only human-readable column is
    # the phone number, and it is not ours to hand over.
    assert "+22990001001" not in str(row)


def test_an_invitation_row_on_the_campaign_page_names_the_creator_too(client):
    """This is the list that used to read "Créateur e66cf36a" beside a
    proposals list that read names — the same person, twice, two ways."""
    creator, media_id = _creator(client, "+22990001002", with_avatar=True)
    _social(client, creator, "tiktok", 88000)
    biz = _business(client, phone="+22990001003")
    campaign = _published_campaign(client, biz)

    invited = client.post(
        f"/campaigns/{campaign['id']}/invitations",
        json={"influencer_id": creator},
        headers=_headers(biz),
    )
    assert invited.status_code == 201
    # The response to the invite itself already names them, so the row does
    # not have to wait for a page reload to become a person.
    assert invited.json()["display_name"] == "Ama K."

    row = client.get(f"/campaigns/{campaign['id']}", headers=_headers(biz)).json()["invitations"][0]
    assert row["influencer_user_id"] == creator
    assert row["display_name"] == "Ama K."
    assert row["avatar_url"] == f"/profiles/media/{media_id}"
    assert row["top_platform"] == "tiktok"
    assert row["top_follower_count"] == 88000
    assert "+22990001002" not in str(row)


def test_a_proposal_row_carries_the_same_fields_as_the_invitation(client):
    """The two lists sit on the same page and are read against each other."""
    creator, _ = _creator(client, "+22990001004")
    _social(client, creator, "youtube", 15000)
    biz = _business(client, phone="+22990001005")
    campaign = _published_campaign(client, biz)
    client.post(
        f"/campaigns/{campaign['id']}/invitations",
        json={"influencer_id": creator},
        headers=_headers(biz),
    )
    client.post(
        f"/campaigns/{campaign['id']}/proposals",
        json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 5},
        headers=_headers(creator),
    )

    detail = client.get(f"/campaigns/{campaign['id']}", headers=_headers(biz)).json()
    invitation = detail["invitations"][0]
    proposal = detail["proposals"][0]
    for field in ("display_name", "avatar_url", "top_platform", "top_follower_count"):
        assert proposal[field] == invitation[field]
    assert proposal["top_follower_count"] == 15000


def test_the_audience_is_the_biggest_platform_and_never_a_sum(client):
    """Adding platforms would double-count the same person following on two
    networks, and the public profile already shows audience one platform at a
    time — the two must not quote a brand different numbers."""
    creator, _ = _creator(client, "+22990001006")
    _social(client, creator, "instagram", 12000, handle="ig")
    _social(client, creator, "tiktok", 30000, handle="tt")
    # WhatsApp Status has no public metric, so whatever number is on the row
    # is not an audience we can stand behind: not eligible, however large.
    _social(client, creator, "whatsapp", 999999, handle="wa")
    biz = _business(client, phone="+22990001007")

    client.post(f"/discovery/favorites/{creator}", headers=_headers(biz))
    row = client.get("/discovery/favorites", headers=_headers(biz)).json()[0]
    assert row["top_platform"] == "tiktok"
    assert row["top_follower_count"] == 30000


def test_a_creator_with_no_connected_account_reports_nulls(client):
    """Null is a real answer here: an unknown audience, not an empty one. A
    zero would read as "nobody follows them", which is a different claim."""
    creator, _ = _creator(client, "+22990001008")
    biz = _business(client, phone="+22990001009")

    client.post(f"/discovery/favorites/{creator}", headers=_headers(biz))
    row = client.get("/discovery/favorites", headers=_headers(biz)).json()[0]
    assert row["display_name"] == "Ama K."
    assert row["top_platform"] is None
    assert row["top_follower_count"] is None


def test_a_creator_with_no_profile_at_all_still_returns_a_row(client):
    """Somebody can be favourited or invited the day they sign up. That row
    comes back empty rather than taking the whole list down with it — and
    empty means empty: no phone number stands in for the missing name."""
    creator, _ = _creator(client, "+22990001010", with_profile=False)
    biz = _business(client, phone="+22990001011")

    assert client.post(f"/discovery/favorites/{creator}", headers=_headers(biz)).status_code == 201
    favourites = client.get("/discovery/favorites", headers=_headers(biz))
    assert favourites.status_code == 200
    row = favourites.json()[0]
    assert row["influencer_user_id"] == creator
    assert row["display_name"] is None
    assert row["avatar_url"] is None
    assert row["top_platform"] is None
    assert row["top_follower_count"] is None
    assert "+22990001010" not in str(row)

    # And the same on the campaign page, which is the other half of the claim.
    campaign = _published_campaign(client, biz)
    client.post(
        f"/campaigns/{campaign['id']}/invitations",
        json={"influencer_id": creator},
        headers=_headers(biz),
    )
    detail = client.get(f"/campaigns/{campaign['id']}", headers=_headers(biz))
    assert detail.status_code == 200
    assert detail.json()["invitations"][0]["display_name"] is None

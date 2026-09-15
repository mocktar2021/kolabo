"""Notifications as events: what raises one, what it says, and who may read it.

test_notifications.py covers the delivery half — the email sender, the
critical types, the unsubscribe. This file covers the other half, which had no
coverage at all because nothing consumed these endpoints: that the moments
people are waiting on actually raise a notification, that the sentence is
worth reading on its own in an email, and that a notification belongs to
exactly one person.
"""
from datetime import date, timedelta

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
from app.modules.notifications import email as email_module
from app.modules.notifications import service as notif_service
from app.modules.notifications.router import router as notifications_router
from app.modules.profiles.models import InfluencerProfile

TERMS = {"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7}

# Every brief here is bid on, and a brief past its deadline takes no proposals
# (campaigns.service), so the date has to stay in the future as the calendar
# moves. A literal would turn this whole file red on a morning nobody touched
# it.
LIVE_DEADLINE = date.today() + timedelta(days=90)


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    # The campaigns module writes Notification rows through notify(), so the
    # whole metadata has to exist and not just the campaigns tables.
    import_all_models()
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    # The default sender would try to reach a provider; this one records.
    notif_service.email_sender = email_module.LoggingEmailSender()

    app = FastAPI()
    app.include_router(campaigns_router, prefix="/campaigns")
    app.include_router(notifications_router, prefix="/notifications")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _user(client, phone, role, verified=True):
    db = client.session_factory()
    try:
        u = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x", country_code="BJ", role=role, is_verified=verified)
        db.add(u); db.commit(); db.refresh(u)
        return u.id, {"Authorization": f"Bearer {create_access_token(u.id)}"}
    finally:
        db.close()


def _influencer_profile(client, user_id, display_name):
    db = client.session_factory()
    try:
        db.add(InfluencerProfile(user_id=user_id, display_name=display_name))
        db.commit()
    finally:
        db.close()


# OPEN by default, because every test below has a creator nobody invited bid
# on the brief — which is what `open` means. The flag is new (campaigns.board)
# and the column defaults to false, so this helper was describing an open brief
# while building a closed one.
def _brief(client, headers, title="Launch push", is_open=True):
    return client.post(
        "/campaigns/",
        json={
            "title": title,
            "budget_amount": 50000,
            "budget_currency": "XOF",
            "deliverables": [{"platform": "instagram", "type": "post", "quantity": 2}],
            "deadline": str(LIVE_DEADLINE),
            "publish": True,
            "is_open": is_open,
        },
        headers=headers,
    ).json()["id"]


def _notes(client, headers, **params):
    return client.get("/notifications/", params=params, headers=headers).json()


def _unread(client, headers):
    return client.get("/notifications/unread-count", headers=headers).json()["unread"]


# --------------------------------------------------------------------------
# Things happening
# --------------------------------------------------------------------------


def test_a_proposal_notifies_the_owner_and_names_the_creator(client):
    """The sentence has to work alone. It goes out by email too, where the
    reader has no screen to cross-reference "a new proposal" against."""
    _, biz = _user(client, "+22990000401", "business")
    inf_id, inf = _user(client, "+22990000402", "influencer")
    _influencer_profile(client, inf_id, "Ama K.")
    cid = _brief(client, biz)

    assert client.post(f"/campaigns/{cid}/proposals", json=TERMS, headers=inf).status_code == 201

    note = _notes(client, biz)[0]
    assert note["type"] == "proposal_submitted"
    assert "Ama K." in note["message"]
    assert "Launch push" in note["message"]


def test_a_creator_with_no_profile_still_produces_a_readable_sentence(client):
    """Somebody can bid the day they sign up. A user id in the sentence would
    be a notification nobody can read, so there is a placeholder."""
    _, biz = _user(client, "+22990000403", "business")
    inf_id, inf = _user(client, "+22990000404", "influencer")
    cid = _brief(client, biz)

    client.post(f"/campaigns/{cid}/proposals", json=TERMS, headers=inf)

    message = _notes(client, biz)[0]["message"]
    assert "Launch push" in message
    assert inf_id not in message


def test_an_application_is_distinguishable_from_an_invited_bid(client):
    """Same row, same version chain, different news.

    An invited creator's bid is an answer the brand was waiting for; an
    application is a stranger it now has to decide whether to look at. One
    line of a bell has to tell them apart, because that is where the brand
    picks which one to open.
    """
    _, biz = _user(client, "+22990000405", "business")
    applicant_id, applicant = _user(client, "+22990000406", "influencer")
    _influencer_profile(client, applicant_id, "Ama K.")
    invited_id, invited = _user(client, "+22990000407", "influencer")
    _influencer_profile(client, invited_id, "Koffi B.")
    cid = _brief(client, biz, is_open=True)

    client.post(f"/campaigns/{cid}/proposals", json=TERMS, headers=invited)
    assert client.post(f"/campaigns/{cid}/apply", json=TERMS, headers=applicant).status_code == 201

    by_type = {n["type"]: n for n in _notes(client, biz)}
    assert set(by_type) == {"proposal_submitted", "brief_application"}

    application = by_type["brief_application"]["message"]
    assert "Ama K." in application
    assert "applied" in application
    assert "Launch push" in application
    # And the invited bid does not read as an application.
    assert "applied" not in by_type["proposal_submitted"]["message"]
    assert "Koffi B." in by_type["proposal_submitted"]["message"]


# --------------------------------------------------------------------------
# Reading it: the bell, the badge, the page
# --------------------------------------------------------------------------


def test_the_unread_count_moves_and_mark_read_clears_it(client):
    _, biz = _user(client, "+22990000408", "business")
    _, inf = _user(client, "+22990000409", "influencer")
    cid = _brief(client, biz)

    assert _unread(client, biz) == 0
    client.post(f"/campaigns/{cid}/proposals", json=TERMS, headers=inf)
    assert _unread(client, biz) == 1

    note = _notes(client, biz)[0]
    assert client.post(f"/notifications/{note['id']}/read", headers=biz).status_code == 200
    assert _unread(client, biz) == 0
    # The row stays. Only the badge moved: a bell is history as well as an
    # alert, and deleting on read would throw the history away.
    assert _notes(client, biz)[0]["is_read"] is True


def test_mark_all_read_clears_the_whole_bell_and_says_how_many(client):
    _, biz = _user(client, "+22990000410", "business")
    _, inf = _user(client, "+22990000411", "influencer")
    first = _brief(client, biz, title="Launch push")
    second = _brief(client, biz, title="Ramadan push")
    client.post(f"/campaigns/{first}/proposals", json=TERMS, headers=inf)
    client.post(f"/campaigns/{second}/proposals", json=TERMS, headers=inf)

    assert _unread(client, biz) == 2
    assert client.post("/notifications/read-all", headers=biz).json()["marked"] == 2
    assert _unread(client, biz) == 0
    assert all(n["is_read"] for n in _notes(client, biz))
    # A second sweep touches nothing rather than re-stamping read rows.
    assert client.post("/notifications/read-all", headers=biz).json()["marked"] == 0


def test_newest_first_and_the_page_is_capped(client):
    _, biz = _user(client, "+22990000412", "business")
    _, inf = _user(client, "+22990000413", "influencer")
    older = _brief(client, biz, title="Older brief")
    newer = _brief(client, biz, title="Newer brief")
    client.post(f"/campaigns/{older}/proposals", json=TERMS, headers=inf)
    client.post(f"/campaigns/{newer}/proposals", json=TERMS, headers=inf)

    rows = _notes(client, biz)
    assert ["Newer brief" in rows[0]["message"], "Older brief" in rows[1]["message"]] == [True, True]
    # Every row is dated, which is most of what tells a reader whether a line
    # still matters.
    assert rows[0]["created_at"]

    page_one = _notes(client, biz, limit=1)
    page_two = _notes(client, biz, limit=1, offset=1)
    assert len(page_one) == 1 and len(page_two) == 1
    assert "Newer brief" in page_one[0]["message"]
    assert "Older brief" in page_two[0]["message"]


def test_an_absurd_limit_is_clamped_rather_than_refused(client):
    """A bell asking for too much wants as much as it can have; a 422 there is
    a blank menu. The ceiling is what stops a paged endpoint being turned back
    into an unpaged one."""
    _, biz = _user(client, "+22990000414", "business")
    _, inf = _user(client, "+22990000415", "influencer")
    cid = _brief(client, biz)
    client.post(f"/campaigns/{cid}/proposals", json=TERMS, headers=inf)

    r = client.get("/notifications/", params={"limit": 100000}, headers=biz)
    assert r.status_code == 200
    assert len(r.json()) == 1


# --------------------------------------------------------------------------
# Whose it is
# --------------------------------------------------------------------------


def test_a_third_party_cannot_read_or_clear_somebody_elses_notification(client):
    """A notification is readable by exactly one person.

    404 rather than 403 on the mark-read, deliberately: a 403 would confirm
    the id exists and belongs to someone.
    """
    _, biz = _user(client, "+22990000416", "business")
    _, inf = _user(client, "+22990000417", "influencer")
    _, stranger = _user(client, "+22990000418", "business")
    cid = _brief(client, biz)
    client.post(f"/campaigns/{cid}/proposals", json=TERMS, headers=inf)

    note = _notes(client, biz)[0]
    assert _notes(client, stranger) == []
    assert _unread(client, stranger) == 0
    assert client.post(f"/notifications/{note['id']}/read", headers=stranger).status_code == 404
    # A stranger's sweep must not reach across accounts either.
    assert client.post("/notifications/read-all", headers=stranger).json()["marked"] == 0
    # And it is still unread for the person it belongs to.
    assert _unread(client, biz) == 1


def test_the_reading_endpoints_require_auth(client):
    assert client.get("/notifications/unread-count").status_code == 401
    assert client.post("/notifications/read-all").status_code == 401

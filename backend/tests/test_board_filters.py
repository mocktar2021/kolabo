"""Filters on the two campaign lists, and the one thing they must not become.

THE CLAIM UNDER TEST is that narrowing and ranking are separate mechanisms.
GET /campaigns/open gained six filters; match_score gained nothing. A filtered
board is still a ranked board, and the test at the bottom of the first section
is the one that would catch somebody quietly folding the filters into the
score (or the score into the filters) later.

A separate file from test_board.py, which is about what the board shows and
what applying to a brief does. This one is about what a creator, and a buyer,
can narrow those lists down to.

Why the filters are allowed to hide briefs when the brand's targeting is not:
the creator set them, can see they are set, and clears them in one click.
Nobody is kept out of a room they did not know was there. That asymmetry is
why test_a_filter_can_hide_a_brief_the_creator_could_still_apply_to exists.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.campaigns import board, models as campaigns
from app.modules.campaigns.router import router as campaigns_router
from app.modules.profiles.models import InfluencerProfile


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    from app.core.db import import_all_models
    import_all_models()
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


def _user(client, phone, role, country="BJ"):
    db = client.session_factory()
    try:
        u = User(phone=phone, password_hash="x", country_code=country, role=role, is_verified=True)
        db.add(u); db.commit(); db.refresh(u)
        return u.id, {"Authorization": f"Bearer {create_access_token(u.id)}"}
    finally:
        db.close()


def _creator_profile(client, user_id, categories, followers=5000):
    db = client.session_factory()
    try:
        db.add(InfluencerProfile(
            user_id=user_id, display_name="Ama K.", categories=categories,
            follower_count=followers, rate_card={},
        ))
        db.commit()
    finally:
        db.close()


def _open_brief(
    client, headers, title, *, budget=50000, deadline="2026-09-01",
    platform="instagram", deliverable="post", publish=True, **targeting,
):
    """A published brief, open from the start.

    Created open rather than opened by a later PATCH — test_board.py already
    covers the PATCH path, and every brief here exists only to be filtered.
    """
    r = client.post("/campaigns/", json={
        "title": title,
        "budget_amount": budget,
        "budget_currency": "XOF",
        "deliverables": [{"platform": platform, "type": deliverable, "quantity": 2}],
        "deadline": deadline,
        "publish": publish,
        "is_open": True,
        **targeting,
    }, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _titles(client, headers, query=""):
    r = client.get(f"/campaigns/open{query}", headers=headers)
    assert r.status_code == 200, r.text
    return [row["title"] for row in r.json()]


# --- the board's filters ---------------------------------------------------


def test_the_budget_band_narrows_the_board(client):
    """A creator whose floor is 100k should not have to read past briefs that
    cannot pay it. Either end may be left open."""
    _, biz = _user(client, "+22990030001", "business")
    _, inf = _user(client, "+22990030002", "influencer")
    _open_brief(client, biz, "Small", budget=40000)
    _open_brief(client, biz, "Medium", budget=150000)
    _open_brief(client, biz, "Large", budget=900000)

    assert set(_titles(client, inf, "?min_budget=100000")) == {"Medium", "Large"}
    assert set(_titles(client, inf, "?max_budget=200000")) == {"Small", "Medium"}
    assert _titles(client, inf, "?min_budget=100000&max_budget=200000") == ["Medium"]
    # The bounds are inclusive: a brief paying exactly the floor pays it.
    assert _titles(client, inf, "?min_budget=900000") == ["Large"]


def test_the_category_filter_reads_the_briefs_targeting(client):
    """"Briefs aimed at fashion" is the question, so it answers off the brand's
    target list — which is why the brief aimed at nobody in particular is not
    one of them. Clearing the filter brings it back."""
    _, biz = _user(client, "+22990030010", "business")
    _, inf = _user(client, "+22990030011", "influencer")
    _open_brief(client, biz, "Fashion", target_categories=["fashion", "beauty"])
    _open_brief(client, biz, "Tech", target_categories=["tech"])
    _open_brief(client, biz, "Anyone at all")

    assert _titles(client, inf, "?category=fashion") == ["Fashion"]
    assert _titles(client, inf, "?category=beauty") == ["Fashion"]
    assert len(_titles(client, inf)) == 3


def test_the_country_filter_reads_the_briefs_targeting(client):
    _, biz = _user(client, "+22990030020", "business")
    _, inf = _user(client, "+22990030021", "influencer")
    _open_brief(client, biz, "Benin", target_countries=["BJ"])
    _open_brief(client, biz, "Ghana", target_countries=["GH"])

    assert _titles(client, inf, "?country=BJ") == ["Benin"]
    assert _titles(client, inf, "?country=TG") == []


def test_the_platform_filter_matches_any_one_deliverable(client):
    """A brief is work a creator can do part of. Matching on ANY deliverable
    rather than all of them keeps a TikTok creator's board from hiding a job
    they could bid on half of."""
    _, biz = _user(client, "+22990030030", "business")
    _, inf = _user(client, "+22990030031", "influencer")
    _open_brief(client, biz, "Instagram only", platform="instagram", deliverable="post")
    _open_brief(client, biz, "TikTok only", platform="tiktok", deliverable="video")

    mixed = client.post("/campaigns/", json={
        "title": "Both", "budget_amount": 50000, "budget_currency": "XOF",
        "deliverables": [
            {"platform": "instagram", "type": "post", "quantity": 2},
            {"platform": "tiktok", "type": "video", "quantity": 1},
        ],
        "deadline": "2026-09-01", "publish": True, "is_open": True,
    }, headers=biz)
    assert mixed.status_code == 201, mixed.text

    assert set(_titles(client, inf, "?platform=tiktok")) == {"TikTok only", "Both"}
    assert set(_titles(client, inf, "?platform=instagram")) == {"Instagram only", "Both"}


def test_the_deadline_filter_is_inclusive_and_drops_undated_briefs(client):
    """"Work I can still deliver by then" includes a brief due on precisely
    that day — and cannot honestly include one that never said when it is due.
    An undated published brief is only reachable behind the API (a deadline is
    required to publish), so it is written straight to the database."""
    biz_id, biz = _user(client, "+22990030040", "business")
    _, inf = _user(client, "+22990030041", "influencer")
    _open_brief(client, biz, "Due August", deadline="2026-08-30")
    _open_brief(client, biz, "Due December", deadline="2026-12-01")

    db = client.session_factory()
    db.add(campaigns.Campaign(
        business_user_id=biz_id, title="No date", budget_amount=50000,
        budget_currency="XOF", deliverables=[], deadline=None,
        status=campaigns.PUBLISHED, is_open=True,
    ))
    db.commit(); db.close()

    assert _titles(client, inf, "?deadline_before=2026-09-30") == ["Due August"]
    assert _titles(client, inf, "?deadline_before=2026-08-30") == ["Due August"]
    assert _titles(client, inf, "?deadline_before=2026-08-01") == []
    # And with no filter the undated brief is on the board like anything else.
    assert "No date" in _titles(client, inf)


def test_filters_combine_and_narrow_together(client):
    _, biz = _user(client, "+22990030050", "business")
    _, inf = _user(client, "+22990030051", "influencer")
    _open_brief(client, biz, "Wanted", budget=200000, platform="tiktok",
                deliverable="video", deadline="2026-09-01",
                target_categories=["fashion"])
    _open_brief(client, biz, "Too cheap", budget=20000, platform="tiktok",
                deliverable="video", target_categories=["fashion"])
    _open_brief(client, biz, "Wrong platform", budget=200000, platform="instagram",
                deliverable="post", target_categories=["fashion"])
    _open_brief(client, biz, "Wrong category", budget=200000, platform="tiktok",
                deliverable="video", target_categories=["tech"])

    got = _titles(
        client, inf,
        "?min_budget=100000&platform=tiktok&category=fashion&deadline_before=2026-10-01",
    )
    assert got == ["Wanted"]


def test_a_filtered_board_is_still_match_ranked(client):
    """THE ASSERTION THIS FILE EXISTS FOR. The filters decide WHICH briefs come
    back; match_score still decides what order they come back IN. Both briefs
    below survive the budget filter, and the one this creator matches is
    first — exactly as it would be with no filter at all."""
    _, biz = _user(client, "+22990030060", "business")
    inf_id, inf = _user(client, "+22990030061", "influencer", country="BJ")
    _creator_profile(client, inf_id, ["fashion"])

    _open_brief(client, biz, "Elsewhere", budget=300000,
                target_categories=["tech"], target_countries=["GH"])
    _open_brief(client, biz, "For me", budget=300000,
                target_categories=["fashion"], target_countries=["BJ"])
    _open_brief(client, biz, "Too cheap to see", budget=1000,
                target_categories=["fashion"], target_countries=["BJ"])

    rows = client.get("/campaigns/open?min_budget=100000", headers=inf).json()
    assert [row["title"] for row in rows] == ["For me", "Elsewhere"]
    assert rows[0]["match_score"] == board.CATEGORY_WEIGHT + board.COUNTRY_WEIGHT
    # The zero-scoring brief was not filtered out by its score. It is on the
    # board, below the match, because the score ranks and never hides.
    assert rows[1]["match_score"] == 0


def test_a_filter_can_hide_a_brief_the_creator_could_still_apply_to(client):
    """The filters are a view, not a rule. A creator who narrowed their board
    to briefs over 100k may still bid on a 40k one they reached another way —
    which is the difference between a creator's own filter and the hard
    targeting filter campaigns.board refuses to build."""
    _, biz = _user(client, "+22990030070", "business")
    _, inf = _user(client, "+22990030071", "influencer")
    cid = _open_brief(client, biz, "Small", budget=40000)

    assert _titles(client, inf, "?min_budget=100000") == []
    r = client.post(f"/campaigns/{cid}/apply",
                    json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7},
                    headers=inf)
    assert r.status_code == 201


def test_a_board_with_no_filters_is_the_board_it_always_was(client):
    """Every filter defaults to no opinion, so a client that has never heard
    of them gets exactly what it got before."""
    _, biz = _user(client, "+22990030080", "business")
    _, inf = _user(client, "+22990030081", "influencer")
    _open_brief(client, biz, "One")
    _open_brief(client, biz, "Two", target_categories=["tech"])

    assert len(_titles(client, inf)) == 2


# --- the buyer's own list --------------------------------------------------


def test_the_buyers_list_filters_by_status(client):
    _, biz = _user(client, "+22990030090", "business")
    draft = client.post("/campaigns/", json={"title": "Idea only"}, headers=biz).json()["id"]
    _open_brief(client, biz, "Live")
    called_off = _open_brief(client, biz, "Called off")
    assert client.post(f"/campaigns/{called_off}/cancel", headers=biz).status_code == 200

    def titles(query):
        r = client.get(f"/campaigns/mine{query}", headers=biz)
        assert r.status_code == 200, r.text
        return sorted(row["title"] for row in r.json())

    assert titles("") == ["Called off", "Idea only", "Live"]
    assert titles("?status=draft") == ["Idea only"]
    assert titles("?status=published") == ["Live"]
    assert titles("?status=cancelled") == ["Called off"]
    assert draft  # the id is only here to make the draft's existence explicit


def test_the_buyers_list_takes_a_date_range(client):
    """created_before is inclusive of the whole day, which is what somebody
    picking a date on a calendar means. The range is in UTC, because that is
    what created_at is stored in."""
    _, biz = _user(client, "+22990030100", "business")
    _open_brief(client, biz, "Today")
    today = datetime.now(timezone.utc).date()

    def count(query):
        r = client.get(f"/campaigns/mine{query}", headers=biz)
        assert r.status_code == 200, r.text
        return len(r.json())

    assert count(f"?created_after={today}") == 1
    assert count(f"?created_after={today + timedelta(days=1)}") == 0
    assert count(f"?created_before={today}") == 1
    assert count(f"?created_before={today - timedelta(days=1)}") == 0
    assert count(f"?created_after={today}&created_before={today}") == 1


def test_an_unknown_status_is_refused_rather_than_answered_with_nothing(client):
    """This is the buyer's own work. An empty list would read as "you have no
    campaigns", which is the one answer that sends somebody to support."""
    _, biz = _user(client, "+22990030110", "business")
    _open_brief(client, biz, "Live")

    r = client.get("/campaigns/mine?status=archived", headers=biz)
    assert r.status_code == 400
    assert "published" in r.json()["detail"]


def test_the_filtered_lists_still_require_auth(client):
    assert client.get("/campaigns/open?min_budget=1000").status_code == 401
    assert client.get("/campaigns/mine?status=draft").status_code == 401

"""Tests for the open board: GET /campaigns/open and POST /campaigns/{id}/apply.

What this feature must not get wrong, in order of how badly it would hurt:

  1. A brief that was never opened must not appear. Every campaign in the
     system predates the board, and showing one would deliver applications
     from strangers to a brand that thought it was briefing three people it
     picked.
  2. Targeting must not hide anything. It is a soft filter: a creator who
     matches nothing still sees every open brief, because a pilot-sized
     roster plus a hard filter is an empty board, and an empty board is a
     creator who does not come back.
  3. An application must be an ordinary proposal. The brand answers it from
     the page it already uses, and nothing downstream can tell it apart from
     a bid by somebody it invited.
"""
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
from app.modules.campaigns import board, models as campaigns
from app.modules.campaigns.router import router as campaigns_router
from app.modules.profiles.models import BusinessProfile, InfluencerProfile

# Every brief in this file has to be LIVE, and that is now a property the board
# reads rather than a detail of the fixture: a brief past its deadline is off
# the board entirely and takes no applications (campaigns.board). A fixed date
# would therefore describe a brief that is on the board until it arrives and
# invisible from then on, which empties most of the assertions below on a
# morning nobody has touched this file.
LIVE_DEADLINE = date.today() + timedelta(days=90)


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


def _user(client, phone, role, country="BJ", verified=True):
    db = client.session_factory()
    try:
        u = User(phone=phone, password_hash="x", country_code=country, role=role, is_verified=verified)
        db.add(u); db.commit(); db.refresh(u)
        return u.id, {"Authorization": f"Bearer {create_access_token(u.id)}"}
    finally:
        db.close()


def _creator_profile(client, user_id, categories, followers):
    """What the scorer reads off the caller: what they cover and how big they are."""
    db = client.session_factory()
    try:
        db.add(InfluencerProfile(
            user_id=user_id, display_name="Ama K.", categories=categories,
            follower_count=followers, rate_card={},
        ))
        db.commit()
    finally:
        db.close()


def _brief(client, headers, title, publish=True):
    return client.post("/campaigns/", json={
        "title": title,
        "budget_amount": 50000,
        "budget_currency": "XOF",
        "deliverables": [{"platform": "instagram", "type": "post", "quantity": 2}],
        "deadline": str(LIVE_DEADLINE),
        "publish": publish,
    }, headers=headers).json()["id"]


def _open_brief(client, headers, title, **targeting):
    """A published brief put on the board through the PATCH endpoint.

    Opened by PATCH rather than at creation on purpose: it exercises the
    edit path the product actually uses when a brand decides mid-flight that
    invitations are not filling the brief.
    """
    cid = _brief(client, headers, title)
    r = client.patch(f"/campaigns/{cid}", json={"is_open": True, **targeting}, headers=headers)
    assert r.status_code == 200, r.text
    return cid


def _titles(rows):
    return [row["title"] for row in rows]


# --- the score itself, tested without a database ---------------------------
#
# The scorer is pure, so the ranking rule can be pinned down on its own. The
# board query is then only tested for what it filters, and the two failures
# stay apart: a brief missing from a board and a brief in the wrong position
# are different bugs with different fixes.


def test_score_is_zero_when_a_brief_targets_nothing():
    """An untargeted brief ranks below any deliberate match, and that is the
    decision rather than an accident: a brand that named nobody has expressed
    no preference and has no claim on the top of anybody's board."""
    assert board.match_score(
        creator_categories=["fashion"], creator_country="BJ", creator_followers=5000
    ) == 0


def test_each_dimension_contributes_its_own_weight():
    assert board.match_score(
        target_categories=["fashion"], creator_categories=["fashion"]
    ) == board.CATEGORY_WEIGHT
    assert board.match_score(
        target_countries=["BJ"], creator_country="BJ"
    ) == board.COUNTRY_WEIGHT
    assert board.match_score(
        target_min_followers=1000, target_max_followers=10000, creator_followers=5000
    ) == board.FOLLOWER_WEIGHT
    # All three together is the ceiling, and the ceiling is small enough to
    # explain to a brand asking why its brief is not being seen.
    assert board.match_score(
        target_categories=["fashion"], target_countries=["BJ"],
        target_min_followers=1000, target_max_followers=10000,
        creator_categories=["fashion"], creator_country="BJ", creator_followers=5000,
    ) == board.MAX_MATCH_SCORE


def test_any_category_overlap_scores_the_full_weight():
    """Not proportional on purpose: scaling by how many categories are shared
    would rank a generalist listing eight of them above the specialist the
    brand actually wants."""
    assert board.match_score(
        target_categories=["fashion", "beauty", "travel"], creator_categories=["fashion"]
    ) == board.CATEGORY_WEIGHT


def test_a_missed_dimension_scores_nothing_and_does_not_go_negative():
    assert board.match_score(
        target_categories=["tech"], target_countries=["GH"],
        creator_categories=["fashion"], creator_country="BJ",
    ) == 0


def test_an_unknown_follower_count_scores_nothing_rather_than_zero_followers():
    """Zero is a claim we cannot make. Reading an unfilled field as zero would
    sink every creator who has not entered one to the bottom of every
    targeted board."""
    assert board.match_score(
        target_min_followers=1000, target_max_followers=10000, creator_followers=None
    ) == 0


def test_an_open_ended_band_stays_open_at_that_end():
    # "at least 1000", with no ceiling.
    assert board.match_score(target_min_followers=1000, creator_followers=900000) == (
        board.FOLLOWER_WEIGHT
    )
    # "up to 10000", with no floor.
    assert board.match_score(target_max_followers=10000, creator_followers=5) == (
        board.FOLLOWER_WEIGHT
    )
    assert board.match_score(target_min_followers=1000, creator_followers=999) == 0


# --- the board -------------------------------------------------------------


def test_a_creator_sees_only_open_published_briefs(client):
    """Everything else on the board is a brief somebody did not offer to the
    market: a draft nobody finished, a brief addressed to invited creators,
    and a direct order that is a private transaction between two parties."""
    _, biz = _user(client, "+22990001001", "business")
    inf_id, inf = _user(client, "+22990001002", "influencer")

    _open_brief(client, biz, "On the board")
    _brief(client, biz, "Invite only")  # published, never opened
    draft = _brief(client, biz, "Half written", publish=False)
    client.patch(f"/campaigns/{draft}", json={"is_open": True}, headers=biz)

    # A direct order, written straight to the database: reaching one through
    # the real path needs a package and a creator to sell it, and what is
    # under test is that the board refuses is_direct even when it is open.
    db = client.session_factory()
    db.add(campaigns.Campaign(
        business_user_id=_user(client, "+22990001003", "business")[0],
        title="Private order", budget_amount=1000, budget_currency="XOF",
        deliverables=[], status=campaigns.PUBLISHED, is_direct=True, is_open=True,
    ))
    db.commit(); db.close()

    rows = client.get("/campaigns/open", headers=inf).json()
    assert _titles(rows) == ["On the board"]


def test_a_cancelled_brief_leaves_the_board(client):
    """A called-off brief must never sit on a board collecting bids nobody
    will read."""
    _, biz = _user(client, "+22990001010", "business")
    _, inf = _user(client, "+22990001011", "influencer")
    cid = _open_brief(client, biz, "Called off")
    assert client.post(f"/campaigns/{cid}/cancel", headers=biz).status_code == 200
    assert client.get("/campaigns/open", headers=inf).json() == []


def test_a_business_gets_403_not_an_empty_list(client):
    """Briefs carry budgets and a brand's plans for the quarter, so the board
    stays behind a creator login. An empty list would read as "there are no
    open briefs", which is a different and untrue answer."""
    _, biz = _user(client, "+22990001020", "business")
    _open_brief(client, biz, "On the board")

    r = client.get("/campaigns/open", headers=biz)
    assert r.status_code == 403
    assert "creators" in r.json()["detail"]

    _, agency = _user(client, "+22990001021", "agency")
    assert client.get("/campaigns/open", headers=agency).status_code == 403


def test_the_board_requires_auth(client):
    assert client.get("/campaigns/open").status_code == 401


def test_a_category_and_country_match_ranks_above_a_non_match(client):
    _, biz = _user(client, "+22990001030", "business")
    inf_id, inf = _user(client, "+22990001031", "influencer", country="BJ")
    _creator_profile(client, inf_id, ["fashion"], 5000)

    _open_brief(client, biz, "Elsewhere",
                target_categories=["tech"], target_countries=["GH"])
    _open_brief(client, biz, "For me",
                target_categories=["fashion"], target_countries=["BJ"])

    rows = client.get("/campaigns/open", headers=inf).json()
    assert _titles(rows) == ["For me", "Elsewhere"]
    assert rows[0]["match_score"] == board.CATEGORY_WEIGHT + board.COUNTRY_WEIGHT
    # The brief that matches nothing is still on the board. Targeting ranks,
    # it never hides — a brand can decline an application it did not want but
    # can never receive one it never saw.
    assert rows[1]["match_score"] == 0


def test_an_untargeted_brief_still_appears(client):
    _, biz = _user(client, "+22990001040", "business")
    inf_id, inf = _user(client, "+22990001041", "influencer")
    _creator_profile(client, inf_id, ["fashion"], 5000)

    _open_brief(client, biz, "Anyone at all")
    _open_brief(client, biz, "Fashion in Benin",
                target_categories=["fashion"], target_countries=["BJ"])

    rows = client.get("/campaigns/open", headers=inf).json()
    assert _titles(rows) == ["Fashion in Benin", "Anyone at all"]
    assert rows[1]["match_score"] == 0
    assert rows[1]["target_categories"] == []


def test_a_creator_with_no_profile_still_gets_a_board(client):
    """An empty board would be the worst possible first screen for somebody
    who signed up an hour ago. They match nothing, so everything scores zero
    and they see the newest briefs first, which is a perfectly good board."""
    _, biz = _user(client, "+22990001050", "business")
    _, inf = _user(client, "+22990001051", "influencer")
    _open_brief(client, biz, "Fashion in Benin", target_categories=["fashion"])

    rows = client.get("/campaigns/open", headers=inf).json()
    assert _titles(rows) == ["Fashion in Benin"]
    assert rows[0]["match_score"] == 0


def test_the_row_carries_the_brief_the_buyer_and_the_caller_s_state(client):
    biz_id, biz = _user(client, "+22990001060", "business")
    inf_id, inf = _user(client, "+22990001061", "influencer")
    db = client.session_factory()
    db.add(BusinessProfile(user_id=biz_id, company_name="Maison Kola"))
    db.commit(); db.close()

    cid = _open_brief(client, biz, "Launch push", target_categories=["fashion"])
    row = client.get("/campaigns/open", headers=inf).json()[0]

    # The whole brief: a creator prices from this card.
    assert row["id"] == cid
    assert row["budget_amount"] == 50000
    assert row["deliverables"] == [{"platform": "instagram", "type": "post", "quantity": 2}]
    assert row["deadline"] == str(LIVE_DEADLINE)
    assert row["business_company_name"] == "Maison Kola"
    assert row["is_open"] is True
    assert row["has_applied"] is False
    assert row["is_invited"] is False
    # Never the buyer's phone number, on this payload or any other.
    assert "+22990001060" not in str(row)

    client.post(f"/campaigns/{cid}/apply",
                json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7},
                headers=inf)
    row = client.get("/campaigns/open", headers=inf).json()[0]
    assert row["has_applied"] is True


def test_the_invited_flag_marks_a_brief_addressed_to_the_caller(client):
    _, biz = _user(client, "+22990001070", "business")
    inf_id, inf = _user(client, "+22990001071", "influencer")
    cid = _open_brief(client, biz, "Both at once")
    client.post(f"/campaigns/{cid}/invitations", json={"influencer_id": inf_id}, headers=biz)

    row = client.get("/campaigns/open", headers=inf).json()[0]
    assert row["is_invited"] is True


def test_patching_targeting_echoes_it_back(client):
    """A PATCH that changed the targeting has to say what it changed: the
    campaign payload carries the fields rather than leaving the client to
    guess from a 200."""
    _, biz = _user(client, "+22990001080", "business")
    cid = _brief(client, biz, "Launch push")
    body = client.patch(f"/campaigns/{cid}", json={
        "is_open": True,
        "target_categories": ["fashion", "beauty"],
        "target_countries": ["BJ", "TG"],
        "target_min_followers": 1000,
        "target_max_followers": 50000,
    }, headers=biz).json()
    assert body["is_open"] is True
    assert body["target_categories"] == ["fashion", "beauty"]
    assert body["target_countries"] == ["BJ", "TG"]
    assert body["target_min_followers"] == 1000
    assert body["target_max_followers"] == 50000

    # And the buyer's own list says which of its briefs strangers can apply to.
    assert client.get("/campaigns/mine", headers=biz).json()[0]["is_open"] is True


def test_a_brief_created_open_is_open(client):
    """Deciding who a brief is for is part of writing it; making a brand save
    and then open it would be two calls for one decision."""
    _, biz = _user(client, "+22990001090", "business")
    body = client.post("/campaigns/", json={
        "title": "Open from the start",
        "budget_amount": 50000,
        "budget_currency": "XOF",
        "deliverables": [{"platform": "instagram", "type": "post", "quantity": 1}],
        "deadline": str(LIVE_DEADLINE),
        "publish": True,
        "is_open": True,
        "target_categories": ["fashion"],
    }, headers=biz).json()
    assert body["is_open"] is True
    assert body["target_categories"] == ["fashion"]


def test_a_brief_does_not_open_itself(client):
    """The default is what protects every brief written before the board
    existed: a client that has never heard of it cannot open one by accident."""
    _, biz = _user(client, "+22990001100", "business")
    body = client.post("/campaigns/", json={"title": "Idea only"}, headers=biz).json()
    assert body["is_open"] is False
    assert body["target_categories"] == []


def test_clearing_targeting_with_null_is_not_a_crash(client):
    """A form whose last chip was removed posts [] in some clients and null in
    others. Both mean the same thing, and the column is NOT NULL."""
    _, biz = _user(client, "+22990001110", "business")
    cid = _brief(client, biz, "Launch push")
    client.patch(f"/campaigns/{cid}", json={"target_categories": ["fashion"]}, headers=biz)
    body = client.patch(f"/campaigns/{cid}", json={"target_categories": None}, headers=biz).json()
    assert body["target_categories"] == []


# --- applying --------------------------------------------------------------


def test_applying_creates_a_proposal_the_brand_sees_in_its_proposals_list(client):
    """An application is an ordinary proposal on the ordinary chain. The brand
    answers it from the campaign page it already uses, with no new surface —
    and it IS told which kind of proposal arrived: an unsolicited application
    rings as `brief_application`, not as the `proposal_submitted` an invited
    creator's bid rings as. Those are two different decisions for the brand,
    and only one of them was expected. The row and the chain stay identical;
    the wording of the bell is the only thing that differs."""
    _, biz = _user(client, "+22990001120", "business")
    inf_id, inf = _user(client, "+22990001121", "influencer")
    cid = _open_brief(client, biz, "Launch push")

    r = client.post(f"/campaigns/{cid}/apply",
                    json={"rate_amount": 40000, "rate_currency": "xof",
                          "timeline_days": 7, "note": "I shoot in Cotonou"},
                    headers=inf)
    assert r.status_code == 201
    assert r.json()["version"] == 1
    assert r.json()["rate_currency"] == "XOF"
    assert r.json()["author_role"] == "influencer"
    # A brief's proposals never expire; only a direct order runs on a clock.
    assert r.json()["expires_at"] is None

    detail = client.get(f"/campaigns/{cid}", headers=biz).json()
    assert len(detail["proposals"]) == 1
    assert detail["proposals"][0]["influencer_user_id"] == inf_id
    assert detail["proposals"][0]["note"] == "I shoot in Cotonou"
    # And it really was an application: nobody invited this creator.
    assert detail["invitations"] == []

    # The buyer is told, through the path submit_proposal already had — and
    # told that it was an application rather than an invited creator's answer.
    from app.modules.notifications.models import Notification
    db = client.session_factory()
    notifications = [(n.type, n.message) for n in db.query(Notification).all()]
    db.close()
    types = [t for t, _ in notifications]
    assert "brief_application" in types
    assert "proposal_submitted" not in types
    # And the sentence says so too, naming the brief the brand has to go and
    # answer: a bell that only says "a proposal" sends it hunting.
    message = next(m for t, m in notifications if t == "brief_application")
    assert "applied to your open brief" in message
    assert "Launch push" in message


def test_applying_twice_conflicts(client):
    """A second application would supersede terms the brand may be reading
    right now, changing the offer under it without either side meaning to."""
    _, biz = _user(client, "+22990001130", "business")
    _, inf = _user(client, "+22990001131", "influencer")
    cid = _open_brief(client, biz, "Launch push")
    offer = {"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7}

    assert client.post(f"/campaigns/{cid}/apply", json=offer, headers=inf).status_code == 201
    r = client.post(f"/campaigns/{cid}/apply", json=offer, headers=inf)
    assert r.status_code == 409

    # Only one proposal was written: the refusal is not a silent second row.
    detail = client.get(f"/campaigns/{cid}", headers=biz).json()
    assert len(detail["proposals"]) == 1


def test_a_withdrawn_application_can_be_replaced(client):
    """The 409 is about a LIVE proposal, not about having ever applied. A
    creator who pulled their offer has nothing on the table and may bid
    again."""
    _, biz = _user(client, "+22990001140", "business")
    _, inf = _user(client, "+22990001141", "influencer")
    cid = _open_brief(client, biz, "Launch push")
    offer = {"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7}

    pid = client.post(f"/campaigns/{cid}/apply", json=offer, headers=inf).json()["id"]
    assert client.post(f"/campaigns/proposals/{pid}/withdraw", headers=inf).status_code == 200
    r = client.post(f"/campaigns/{cid}/apply", json=offer, headers=inf)
    assert r.status_code == 201
    assert r.json()["version"] == 2


def test_applying_to_a_brief_that_is_not_open_is_refused(client):
    _, biz = _user(client, "+22990001150", "business")
    _, inf = _user(client, "+22990001151", "influencer")
    cid = _brief(client, biz, "Invite only")

    r = client.post(f"/campaigns/{cid}/apply",
                    json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7},
                    headers=inf)
    assert r.status_code == 400
    assert r.json()["detail"] == board.NOT_OPEN_DETAIL


def test_applying_to_a_direct_order_is_refused(client):
    """An order is addressed to one creator and is not a brief anyone may bid
    on. The message says what was found, not just that it is not open."""
    biz_id, biz = _user(client, "+22990001160", "business")
    _, inf = _user(client, "+22990001161", "influencer")
    db = client.session_factory()
    order = campaigns.Campaign(
        business_user_id=biz_id, title="Private order", budget_amount=1000,
        budget_currency="XOF", deliverables=[], status=campaigns.PUBLISHED,
        is_direct=True, is_open=True,
    )
    db.add(order); db.commit(); db.refresh(order)
    cid = order.id
    db.close()

    r = client.post(f"/campaigns/{cid}/apply",
                    json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7},
                    headers=inf)
    assert r.status_code == 400
    assert r.json()["detail"] == board.DIRECT_ORDER_DETAIL


def test_applying_to_a_draft_or_a_cancelled_brief_is_refused(client):
    """submit_proposal owns the published rule and is not second-guessed here,
    so both answer with its sentence."""
    _, biz = _user(client, "+22990001170", "business")
    _, inf = _user(client, "+22990001171", "influencer")
    offer = {"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7}

    draft = _brief(client, biz, "Half written", publish=False)
    client.patch(f"/campaigns/{draft}", json={"is_open": True}, headers=biz)
    assert client.post(f"/campaigns/{draft}/apply", json=offer, headers=inf).status_code == 400

    cancelled = _open_brief(client, biz, "Called off")
    client.post(f"/campaigns/{cancelled}/cancel", headers=biz)
    assert client.post(f"/campaigns/{cancelled}/apply", json=offer, headers=inf).status_code == 400


def test_a_business_cannot_apply(client):
    _, biz = _user(client, "+22990001180", "business")
    _, other = _user(client, "+22990001181", "business")
    cid = _open_brief(client, biz, "Launch push")
    r = client.post(f"/campaigns/{cid}/apply",
                    json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7},
                    headers=other)
    assert r.status_code == 403


def test_applying_to_an_unknown_campaign_is_a_404(client):
    _, inf = _user(client, "+22990001190", "influencer")
    r = client.post("/campaigns/nope/apply",
                    json={"rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7},
                    headers=inf)
    assert r.status_code == 404


def test_apply_requires_auth(client):
    assert client.post("/campaigns/x/apply", json={
        "rate_amount": 40000, "rate_currency": "XOF", "timeline_days": 7,
    }).status_code == 401


def test_an_application_and_its_counter_reach_the_creators_own_list(client):
    """The other half of "an application is an ordinary proposal": it must be
    ordinary for the CREATOR too. A board application writes no invitation
    row, and /campaigns/invitations/mine used to iterate invitation rows only
    — so when the brand countered an application, the creator got a
    notification with no surface behind it: an offer on the table, invisible.
    The list now carries a synthetic `applied` row for each such chain, with
    the same campaign, live proposal and full history every invited row has."""
    _, biz = _user(client, "+22990001130", "business")
    _, inf = _user(client, "+22990001131", "influencer")
    cid = _open_brief(client, biz, "Countered brief")

    r = client.post(f"/campaigns/{cid}/apply",
                    json={"rate_amount": 40000, "rate_currency": "XOF",
                          "timeline_days": 7, "note": None},
                    headers=inf)
    assert r.status_code == 201
    proposal_id = r.json()["id"]

    # Visible to the creator immediately, as an applied row with the chain.
    mine = client.get("/campaigns/invitations/mine", headers=inf).json()
    row = next(i for i in mine if i["campaign_id"] == cid)
    assert row["status"] == "applied"
    assert row["campaign"]["title"] == "Countered brief"
    assert row["proposal"]["rate_amount"] == 40000
    assert len(row["proposal_history"]) == 1

    # The brand counters; the counter must land in the same row.
    r = client.post(f"/campaigns/{cid}/proposals/{proposal_id}/reply",
                    json={"rate_amount": 30000, "note": "Budget stops at 30k"},
                    headers=biz)
    assert r.status_code == 201

    mine = client.get("/campaigns/invitations/mine", headers=inf).json()
    row = next(i for i in mine if i["campaign_id"] == cid)
    assert row["proposal"]["rate_amount"] == 30000
    assert row["proposal"]["author_role"] == "business"
    assert [v["rate_amount"] for v in row["proposal_history"]] == [40000, 30000]

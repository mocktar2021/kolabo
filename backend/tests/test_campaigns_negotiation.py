"""Tests for the negotiation half of Epic D (KOL-23).

Notes on proposals, the business reply, the version chain the campaign page
reads, and the rule that an acceptance signs the last version rather than
whichever id the page was holding. Kept out of test_campaigns.py, which is
already long enough to be read in one sitting only just.
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
from app.modules.contracts.router import router as contracts_router

# Every negotiation here runs on a live brief, and a brief past its deadline
# takes no proposals and no replies (campaigns.service). Relative rather than
# a literal, so the file does not start failing on a date instead of on a
# change.
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
    # Accepting an offer is the contracts module's endpoint, and accepting is
    # exactly where "the latest version wins" has to hold, so both routers sit
    # on the same in-memory database here.
    app.include_router(contracts_router, prefix="/contracts")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = testing_session
    return c


def _user(client, phone, role, verified=True):
    db = client.session_factory()
    try:
        u = User(phone=phone, password_hash="x", country_code="BJ", role=role, is_verified=verified)
        db.add(u); db.commit(); db.refresh(u)
        return u.id, {"Authorization": f"Bearer {create_access_token(u.id)}"}
    finally:
        db.close()


def _published_campaign(client, headers):
    return client.post("/campaigns/", json={
        "title": "Launch push",
        "budget_amount": 50000,
        "budget_currency": "XOF",
        "deliverables": [{"platform": "instagram", "type": "post", "quantity": 2}],
        "deadline": str(LIVE_DEADLINE),
        "publish": True,
        "is_open": True,
    }, headers=headers).json()["id"]


def _submit(client, cid, headers, rate=10000, days=7, note=None):
    payload = {"rate_amount": rate, "rate_currency": "XOF", "timeline_days": days}
    if note is not None:
        payload["note"] = note
    return client.post(f"/campaigns/{cid}/proposals", json=payload, headers=headers)


def _reply(client, cid, pid, headers, note="Noted.", rate=None, days=None):
    payload = {"note": note}
    if rate is not None:
        payload["rate_amount"] = rate
    if days is not None:
        payload["timeline_days"] = days
    return client.post(f"/campaigns/{cid}/proposals/{pid}/reply", json=payload, headers=headers)


def _negotiation(client, biz_phone, inf_phone):
    """A published campaign with one creator's opening offer on it."""
    _, biz = _user(client, biz_phone, "business")
    inf_id, inf = _user(client, inf_phone, "influencer")
    cid = _published_campaign(client, biz)
    first = _submit(client, cid, inf, note="Includes two rounds of revisions.").json()
    return biz, inf, inf_id, cid, first


def _invite(client, cid, headers, influencer_id):
    """Put the creator on the campaign's invitation list.

    The creator's own list is keyed on invitations, not on proposals, so a
    chain with nobody invited to it does not appear there at all — which is
    why _negotiation on its own is not enough for the tests below.
    """
    return client.post(
        f"/campaigns/{cid}/invitations", json={"influencer_id": influencer_id}, headers=headers
    )


def _mine(client, headers):
    """The one row of GET /campaigns/invitations/mine these tests care about."""
    r = client.get("/campaigns/invitations/mine", headers=headers)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    return rows[0]


def test_a_proposal_carries_the_reason_for_its_price(client):
    """A rate with no reasoning attached gets discussed on WhatsApp, and a
    deal agreed there has no contract and no escrow behind it."""
    _, _, _, _, first = _negotiation(client, "+22990001001", "+22990001002")
    assert first["note"] == "Includes two rounds of revisions."
    assert first["author_role"] == "influencer"
    assert first["version"] == 1


def test_a_proposal_without_a_note_is_still_a_proposal(client):
    _, biz = _user(client, "+22990001003", "business")
    _, inf = _user(client, "+22990001004", "influencer")
    cid = _published_campaign(client, biz)
    body = _submit(client, cid, inf).json()
    assert body["note"] is None
    assert body["author_role"] == "influencer"


def test_a_note_past_the_cap_is_rejected(client):
    """Past two thousand characters somebody is holding a conversation in a
    text box, and that is what messaging is for."""
    _, biz = _user(client, "+22990001005", "business")
    _, inf = _user(client, "+22990001006", "influencer")
    cid = _published_campaign(client, biz)
    assert _submit(client, cid, inf, note="x" * 2001).status_code == 422
    assert _submit(client, cid, inf, note="x" * 2000).status_code == 201


def test_a_reply_without_a_counter_repeats_the_terms(client):
    """Every row in a chain is a complete offer, so nobody has to read
    backwards through four versions to reassemble what was agreed."""
    biz, _, _, cid, first = _negotiation(client, "+22990001007", "+22990001008")
    r = _reply(client, cid, first["id"], biz, note="Looks good, one question first.")
    assert r.status_code == 201
    body = r.json()
    assert body["version"] == 2
    assert body["author_role"] == "business"
    assert body["note"] == "Looks good, one question first."
    assert body["rate_amount"] == first["rate_amount"]
    assert body["timeline_days"] == first["timeline_days"]
    assert body["rate_currency"] == "XOF"


def test_a_reply_can_counter_one_term_and_leave_the_other(client):
    biz, _, _, cid, first = _negotiation(client, "+22990001009", "+22990001010")
    body = _reply(client, cid, first["id"], biz, note="Budget stops at 8000.", rate=8000).json()
    assert body["rate_amount"] == 8000
    assert body["timeline_days"] == first["timeline_days"]


def test_a_reply_supersedes_the_offer_it_answers(client):
    biz, _, _, cid, first = _negotiation(client, "+22990001011", "+22990001012")
    _reply(client, cid, first["id"], biz, note="Counter.", rate=8000, days=10)
    from app.modules.campaigns.models import Proposal
    db = client.session_factory()
    v1 = db.query(Proposal).filter(Proposal.id == first["id"]).first()
    db.close()
    assert v1.status == "superseded"


def test_a_reply_needs_something_to_say(client):
    """Terms alone are not an answer: the note is the part a person reads."""
    biz, _, _, cid, first = _negotiation(client, "+22990001013", "+22990001014")
    r = client.post(
        f"/campaigns/{cid}/proposals/{first['id']}/reply",
        json={"rate_amount": 8000},
        headers=biz,
    )
    assert r.status_code == 422


def test_only_the_campaign_owner_can_reply(client):
    biz, inf, _, cid, first = _negotiation(client, "+22990001015", "+22990001016")
    _, other = _user(client, "+22990001017", "business")
    assert _reply(client, cid, first["id"], other).status_code == 403
    # Nor can the creator answer themselves in the business's voice.
    assert _reply(client, cid, first["id"], inf).status_code == 403


def test_reply_to_an_unknown_proposal_is_404(client):
    biz, _, _, cid, _first = _negotiation(client, "+22990001018", "+22990001019")
    assert _reply(client, cid, "no-such-proposal", biz).status_code == 404


def test_the_creator_notices_the_reply(client):
    biz, _, inf_id, cid, first = _negotiation(client, "+22990001020", "+22990001021")
    _reply(client, cid, first["id"], biz, note="Can you do 8000?", rate=8000)
    from app.modules.notifications.models import Notification
    db = client.session_factory()
    kinds = [n.type for n in db.query(Notification).filter(Notification.user_id == inf_id).all()]
    db.close()
    assert "proposal_reply" in kinds


def test_the_creator_answers_the_reply_in_the_same_chain(client):
    """Back and forth in one numbered thread: alternating authors, one version
    number each, and no restart at 1 just because the last word was the
    business's."""
    biz, inf, _, cid, first = _negotiation(client, "+22990001022", "+22990001023")
    _reply(client, cid, first["id"], biz, note="8000 is our ceiling.", rate=8000)
    third = _submit(client, cid, inf, rate=9000, days=7, note="Meeting you at 9000.").json()
    assert third["version"] == 3
    assert third["author_role"] == "influencer"

    rows = client.get(f"/campaigns/{cid}", headers=biz).json()["proposals"]
    assert [p["version"] for p in rows] == [1, 2, 3]
    assert [p["author_role"] for p in rows] == ["influencer", "business", "influencer"]


def test_the_chain_is_oldest_first_and_capped(client):
    """A page has to stay renderable, and a conversation reads downwards. The
    cap keeps the most recent twenty: the last version is the live offer and
    the only one that can be accepted, so cutting from that end would hide the
    single row the page exists to act on."""
    biz, inf, _, cid, first = _negotiation(client, "+22990001024", "+22990001025")
    # Twenty-five versions: the business and the creator taking turns. The
    # reply always names the first proposal, which is also a stale id — the
    # chain, not the version, is what an id has to identify.
    for i in range(24):
        if i % 2 == 0:
            assert _reply(client, cid, first["id"], biz, note=f"round {i}").status_code == 201
        else:
            assert _submit(client, cid, inf, rate=10000 + i, note=f"round {i}").status_code == 201

    rows = client.get(f"/campaigns/{cid}", headers=biz).json()["proposals"]
    assert len(rows) == 20
    assert [p["version"] for p in rows] == list(range(6, 26))
    assert rows[-1]["status"] == "submitted"


def test_accepting_signs_the_latest_version(client):
    """The business accepts from a page holding the opening offer's id, after
    two more rounds moved the terms. The contract must carry the LAST version:
    a proposal id names a negotiation, not a frozen offer.

    The chain ends on the CREATOR's version deliberately. Accepting is
    answering, so the live offer has to be the other side's — a business
    accepting its own counter is refused with contract_own_offer
    (contracts/service.py), and test_contracts.py owns that case. Before that
    guard existed this test stopped at the business's own counter and accepted
    it, which is the bug rather than the behaviour being pinned here.
    """
    biz, inf, _, cid, first = _negotiation(client, "+22990001026", "+22990001027")
    _reply(client, cid, first["id"], biz, note="8000 over ten days.", rate=8000, days=10)
    latest = _submit(client, cid, inf, rate=9000, days=10, note="9000 and we have a deal.").json()

    r = client.post(f"/contracts/from-proposal/{first['id']}", headers=biz)
    assert r.status_code == 201
    contract = r.json()
    assert contract["rate_amount"] == 9000
    assert contract["timeline_days"] == 10
    assert contract["proposal_id"] == latest["id"]

    from app.modules.campaigns.models import Proposal
    db = client.session_factory()
    statuses = {p.version: p.status for p in db.query(Proposal).filter(Proposal.campaign_id == cid).all()}
    db.close()
    assert statuses == {1: "superseded", 2: "superseded", 3: "accepted"}


def test_a_closed_negotiation_cannot_be_answered(client):
    """Once a contract has been written from the terms, reopening the chain by
    reply would let them drift out from under it."""
    biz, _, _, cid, first = _negotiation(client, "+22990001028", "+22990001029")
    assert client.post(f"/contracts/from-proposal/{first['id']}", headers=biz).status_code == 201
    r = _reply(client, cid, first["id"], biz, note="Actually, about the price...")
    assert r.status_code == 400


def test_a_signed_negotiation_takes_no_new_version_from_the_creator(client):
    """The submit-side mirror of test_a_closed_negotiation_cannot_be_answered,
    which only pinned the business reply. Once a contract is written from the
    chain the campaign stays published, so this guard is the only thing between
    a creator and a fresh 'counter' posted onto a signed contract — which would
    let the terms drift out from under it. A direct-order counter takes the
    identical submit path, so this covers that hole too."""
    biz, inf, _, cid, first = _negotiation(client, "+22990001032", "+22990001033")
    assert client.post(f"/contracts/from-proposal/{first['id']}", headers=biz).status_code == 201
    r = _submit(client, cid, inf, rate=12000, days=5)
    assert r.status_code == 400
    # And nothing was written: the chain still ends at the accepted version.
    from app.modules.campaigns.models import Proposal
    db = client.session_factory()
    versions = sorted(p.version for p in db.query(Proposal).filter(Proposal.campaign_id == cid).all())
    db.close()
    assert versions == [1]


def test_a_withdrawn_chain_can_still_be_re_bid(client):
    """The other edge of the same guard: withdrawn is NOT a terminal refusal,
    so a creator who pulled their offer may bid again. If the guard used
    reply's blanket '!= submitted' this would be wrongly refused."""
    biz, inf, _, cid, first = _negotiation(client, "+22990001036", "+22990001037")
    assert client.post(f"/campaigns/proposals/{first['id']}/withdraw", headers=inf).status_code == 200
    again = _submit(client, cid, inf, rate=11000, days=6)
    assert again.status_code == 201
    assert again.json()["version"] == 2


def test_a_draft_brief_takes_no_proposals(client):
    """A brief nobody has published is not open to bids. Covers the
    campaign-status guard, which had no test of its own."""
    _, biz = _user(client, "+22990001034", "business")
    _, inf = _user(client, "+22990001035", "influencer")
    cid = client.post("/campaigns/", json={
        "title": "Just an idea",
        "budget_amount": 50000,
        "budget_currency": "XOF",
        "deliverables": [{"platform": "instagram", "type": "post", "quantity": 1}],
        "deadline": str(LIVE_DEADLINE),
        "publish": False,
    }, headers=biz).json()["id"]
    assert _submit(client, cid, inf).status_code == 400


def test_reply_requires_auth(client):
    _, _, _, cid, first = _negotiation(client, "+22990001030", "+22990001031")
    r = client.post(f"/campaigns/{cid}/proposals/{first['id']}/reply", json={"note": "hello"})
    assert r.status_code == 401


def test_the_creator_reads_every_round_of_their_own_negotiation(client):
    """The brand has always had the whole thread and the creator had one line
    of it.

    campaign_detail sends every proposal row and the brand's page reassembles
    them per creator; the creator's invitations list nested the LIVE version
    and nothing else. So from version two onwards the person being negotiated
    with was reading a number with no idea what it was answering — and
    /campaigns/{id} answers a creator 403, so there was nowhere else to look.

    Oldest first, because a conversation reads downwards and the row the
    creator has to act on is the one at the bottom.
    """
    biz, inf, inf_id, cid, first = _negotiation(client, "+22990001040", "+22990001041")
    assert _invite(client, cid, biz, inf_id).status_code == 201
    _reply(client, cid, first["id"], biz, note="8000 is our ceiling.", rate=8000)
    _submit(client, cid, inf, rate=9000, days=7, note="Meeting you at 9000.")

    history = _mine(client, inf)["proposal_history"]
    assert [v["version"] for v in history] == [1, 2, 3]
    assert [v["author_role"] for v in history] == ["influencer", "business", "influencer"]
    assert [v["rate_amount"] for v in history] == [10000, 8000, 9000]
    assert [v["note"] for v in history] == [
        "Includes two rounds of revisions.",
        "8000 is our ceiling.",
        "Meeting you at 9000.",
    ]
    # Every row is a complete offer rather than a diff, and it is timestamped:
    # "they countered four days ago" is most of what somebody needs to decide
    # whether to chase.
    assert all(v["rate_currency"] == "XOF" for v in history)
    assert all(v["timeline_days"] for v in history)
    assert all(v["created_at"] for v in history)


def test_the_live_version_stays_its_own_field_and_is_the_end_of_the_history(client):
    """`proposal` is what accept and decline are addressed to, so it must not
    move when a history is added beside it.

    The server still computes it with latest_in_chain rather than reading the
    last element of the list — the two agree, but a client sending an id to
    /orders/{id}/accept has to be sending the id the accept endpoint will also
    call live. This pins the agreement, so the day the two ever disagree a
    test says so instead of a creator signing the wrong terms.
    """
    biz, inf, inf_id, cid, first = _negotiation(client, "+22990001042", "+22990001043")
    assert _invite(client, cid, biz, inf_id).status_code == 201
    _reply(client, cid, first["id"], biz, note="8000 is our ceiling.", rate=8000)
    third = _submit(client, cid, inf, rate=9000, days=7, note="Meeting you at 9000.").json()

    row = _mine(client, inf)
    assert row["proposal"] is not None
    assert row["proposal"]["id"] == third["id"]
    assert row["proposal"] == row["proposal_history"][-1]
    # And the one at the end is the only one still open: everything above it
    # was superseded by its own author when they wrote the next round.
    assert row["proposal"]["status"] == "submitted"
    assert [v["status"] for v in row["proposal_history"][:-1]] == ["superseded", "superseded"]


def test_an_invitation_nobody_has_priced_yet_carries_an_empty_history(client):
    """The ordinary state of a fresh brief invitation, and the one a client
    renders a blank proposal form for.

    Empty list and not null, and no live version: a creator invited this
    morning has nothing to read and nothing to answer, and a page that
    crashed on the absence would break the most common row in the list.
    """
    _, biz = _user(client, "+22990001044", "business")
    inf_id, inf = _user(client, "+22990001045", "influencer")
    cid = _published_campaign(client, biz)
    assert _invite(client, cid, biz, inf_id).status_code == 201

    row = _mine(client, inf)
    assert row["proposal_history"] == []
    assert row["proposal"] is None


def test_the_creator_s_history_is_capped_from_the_recent_end_like_the_brand_s(client):
    """Same cap and same reasoning as the brand's list, in the same shape.

    MAX_PROPOSAL_VERSIONS is taken from the RECENT end on both sides: the last
    version is the live offer and the only one that can be accepted, so
    truncating from that end would hide the single row the creator's page
    exists to act on. Twenty-five versions built the way
    test_the_chain_is_oldest_first_and_capped builds them, so the two lists
    are proved to cut identically rather than assumed to.
    """
    biz, inf, inf_id, cid, first = _negotiation(client, "+22990001046", "+22990001047")
    assert _invite(client, cid, biz, inf_id).status_code == 201
    for i in range(24):
        if i % 2 == 0:
            assert _reply(client, cid, first["id"], biz, note=f"round {i}").status_code == 201
        else:
            assert _submit(client, cid, inf, rate=10000 + i, note=f"round {i}").status_code == 201

    from app.modules.campaigns.service import MAX_PROPOSAL_VERSIONS

    history = _mine(client, inf)["proposal_history"]
    assert len(history) == MAX_PROPOSAL_VERSIONS
    assert [v["version"] for v in history] == list(range(6, 26))
    # The identical window the brand is looking at, row for row.
    brand_side = client.get(f"/campaigns/{cid}", headers=biz).json()["proposals"]
    assert [v["version"] for v in history] == [p["version"] for p in brand_side]
    # And the live offer survived the cut, which is the whole point of cutting
    # from the old end.
    assert history[-1]["status"] == "submitted"

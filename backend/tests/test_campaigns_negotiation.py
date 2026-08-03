"""Tests for the negotiation half of Epic D (KOL-23).

Notes on proposals, the business reply, the version chain the campaign page
reads, and the rule that an acceptance signs the last version rather than
whichever id the page was holding. Kept out of test_campaigns.py, which is
already long enough to be read in one sitting only just.
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
from app.modules.contracts.router import router as contracts_router


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
        "deadline": "2026-09-01",
        "publish": True,
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
    its own counter moved the terms. The contract must carry the counter: a
    proposal id names a negotiation, not a frozen offer."""
    biz, _, _, cid, first = _negotiation(client, "+22990001026", "+22990001027")
    counter = _reply(client, cid, first["id"], biz, note="8000 over ten days.", rate=8000, days=10).json()

    r = client.post(f"/contracts/from-proposal/{first['id']}", headers=biz)
    assert r.status_code == 201
    contract = r.json()
    assert contract["rate_amount"] == 8000
    assert contract["timeline_days"] == 10
    assert contract["proposal_id"] == counter["id"]

    from app.modules.campaigns.models import Proposal
    db = client.session_factory()
    statuses = {p.version: p.status for p in db.query(Proposal).filter(Proposal.campaign_id == cid).all()}
    db.close()
    assert statuses == {1: "superseded", 2: "accepted"}


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
        "deadline": "2026-09-01",
        "publish": False,
    }, headers=biz).json()["id"]
    assert _submit(client, cid, inf).status_code == 400


def test_reply_requires_auth(client):
    _, _, _, cid, first = _negotiation(client, "+22990001030", "+22990001031")
    r = client.post(f"/campaigns/{cid}/proposals/{first['id']}/reply", json={"note": "hello"})
    assert r.status_code == 401

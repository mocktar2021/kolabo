"""One thread per counterparty, however many contracts are underneath it.

The product decision under test: an inbox row is a PERSON, not a job. A
creator on their third campaign with the same brand should see one
conversation carrying three contracts, not three conversations carrying the
same name — the relationship is worth more each time it repeats, and the old
shape chopped it up in response.

What must NOT change with it: the gate. A stranger is still refused, because
messaging opens when a contract does and not before.
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
from app.modules.contracts import models as contracts
from app.modules.messaging.models import Message
from app.modules.messaging.router import router as messaging_router
from app.modules.profiles.models import BusinessProfile, InfluencerProfile


@pytest.fixture()
def client():
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
    app.include_router(messaging_router, prefix="/messaging")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


@pytest.fixture()
def world(client):
    """A brand and a creator with profiles, plus a stranger with neither
    contract nor claim."""
    db = client.session_factory()
    try:
        biz = User(phone="+22990070001", password_hash="x", country_code="BJ",
                   role="business", is_verified=True)
        inf = User(phone="+22990070002", password_hash="x", country_code="BJ",
                   role="influencer", is_verified=True)
        third = User(phone="+22990070003", password_hash="x", country_code="BJ",
                     role="influencer", is_verified=True)
        db.add_all([biz, inf, third]); db.commit()
        db.refresh(biz); db.refresh(inf); db.refresh(third)
        db.add(BusinessProfile(user_id=biz.id, company_name="Maison Kola"))
        db.add(InfluencerProfile(user_id=inf.id, display_name="Ama K.",
                                 avatar_media_id="media-abc"))
        db.commit()
        return {"biz": biz.id, "inf": inf.id, "third": third.id}
    finally:
        db.close()


def _job(client, world, title, tag, creator=None):
    """One campaign with one contract on it: a job these two did together."""
    db = client.session_factory()
    try:
        camp = campaigns.Campaign(
            business_user_id=world["biz"], title=title, budget_amount=100000,
            budget_currency="XOF",
            deliverables=[{"platform": "instagram", "type": "post", "quantity": 1}],
            status=campaigns.PUBLISHED,
        )
        db.add(camp); db.commit(); db.refresh(camp)
        proposal = campaigns.Proposal(
            campaign_id=camp.id, influencer_user_id=creator or world["inf"], version=1,
            rate_amount=100000, rate_currency="XOF", timeline_days=7,
            status=campaigns.SUBMITTED,
        )
        db.add(proposal); db.commit(); db.refresh(proposal)
        contract = contracts.Contract(
            campaign_id=camp.id, proposal_id=proposal.id, business_user_id=world["biz"],
            influencer_user_id=creator or world["inf"], language="fr", body="placeholder",
            rate_amount=100000, rate_currency="XOF", timeline_days=7, deliverables=[],
            status=contracts.PENDING,
        )
        db.add(contract); db.commit(); db.refresh(contract)
        return {"campaign": camp.id, "contract": contract.id}
    finally:
        db.close()


def _threads(client, uid):
    return client.get("/messaging/threads", headers=_headers(uid)).json()


def _send(client, sender, to, body):
    return client.post(
        f"/messaging/with/{to}", json={"body": body}, headers=_headers(sender)
    )


def _read(client, reader, other):
    return client.get(f"/messaging/with/{other}", headers=_headers(reader))


# --------------------------------------------------------------------------
# One row per person
# --------------------------------------------------------------------------


def test_two_contracts_with_the_same_counterparty_are_one_thread(client, world):
    """Three jobs with the same brand used to be three inboxes. The
    relationship is the row; the contracts hang off it."""
    first = _job(client, world, "Launch push", "a")
    second = _job(client, world, "Ramadan push", "b")

    inbox = _threads(client, world["inf"])
    assert len(inbox) == 1
    row = inbox[0]
    assert row["counterparty_user_id"] == world["biz"]
    assert row["counterparty_name"] == "Maison Kola"
    assert row["contract_count"] == 2
    assert set(row["contract_ids"]) == {first["contract"], second["contract"]}
    # Newest first, so the job they are currently on leads.
    assert row["contract_ids"][0] == second["contract"]
    assert row["contract_id"] == second["contract"]
    assert row["campaign_id"] == second["campaign"]
    assert row["campaign_title"] == "Ramadan push"


def test_two_different_counterparties_are_two_threads(client, world):
    """Grouping is by person, not a blanket collapse: the brand still has one
    row per creator it works with."""
    _job(client, world, "Launch push", "a")
    _job(client, world, "Second creator", "b", creator=world["third"])

    inbox = _threads(client, world["biz"])
    assert len(inbox) == 2
    assert {r["counterparty_user_id"] for r in inbox} == {world["inf"], world["third"]}
    assert all(r["contract_count"] == 1 for r in inbox)


def test_the_brand_side_names_the_creator_the_shared_way(client, world):
    _job(client, world, "Launch push", "a")
    row = _threads(client, world["biz"])[0]
    assert row["counterparty_name"] == "Ama K."
    assert row["counterparty_avatar_url"] == "/profiles/media/media-abc"


def test_a_contract_with_no_messages_still_shows_a_thread(client, world):
    """An empty thread is exactly the one somebody needs to start."""
    _job(client, world, "Launch push", "a")
    row = _threads(client, world["biz"])[0]
    assert row["last_message"] is None
    assert row["last_message_at"] is None
    assert row["unread_count"] == 0


# --------------------------------------------------------------------------
# One conversation, across the jobs
# --------------------------------------------------------------------------


def test_messages_across_two_contracts_read_as_one_conversation(client, world):
    """A question asked during the second job and answered during the third is
    a conversation, and used to read as two disconnected threads."""
    first = _job(client, world, "Launch push", "a")
    _send(client, world, world["biz"], world["inf"], "one") if False else None

    # Sent on the first job, through the per-campaign endpoint that still works.
    client.post(
        f"/messaging/campaigns/{first['campaign']}/messages",
        json={"to_user_id": world["inf"], "body": "how did the first shoot go"},
        headers=_headers(world["biz"]),
    )
    # Then a second job, and a message addressed to the PERSON.
    second = _job(client, world, "Ramadan push", "b")
    assert _send(client, world["inf"], world["biz"], "ready for the next one").status_code == 201

    thread = _read(client, world["biz"], world["inf"]).json()
    assert [m["body"] for m in thread] == [
        "how did the first shoot go",
        "ready for the next one",
    ]
    # campaign_id is still on every row: which job a message was about is
    # history worth keeping, and a dispute reads it.
    assert thread[0]["campaign_id"] == first["campaign"]
    # A message sent through the counterparty endpoint carries the most recent
    # shared contract's campaign.
    assert thread[1]["campaign_id"] == second["campaign"]


def test_the_last_message_on_the_row_spans_both_contracts(client, world):
    first = _job(client, world, "Launch push", "a")
    client.post(
        f"/messaging/campaigns/{first['campaign']}/messages",
        json={"to_user_id": world["inf"], "body": "old news"},
        headers=_headers(world["biz"]),
    )
    _job(client, world, "Ramadan push", "b")
    _send(client, world["biz"], world["inf"], "the newest thing")

    row = _threads(client, world["inf"])[0]
    assert row["last_message"] == "the newest thing"
    assert row["last_message_at"] is not None


# --------------------------------------------------------------------------
# The gate is unchanged
# --------------------------------------------------------------------------


def test_a_stranger_is_still_refused(client, world):
    """Messaging opens when a contract does. A person you have never worked
    with is a cold lead, and an inbox full of those is an inbox nobody opens.
    """
    _job(client, world, "Launch push", "a")

    assert _send(client, world["biz"], world["third"], "you are next").status_code == 403
    assert _send(client, world["third"], world["biz"], "me too?").status_code == 403
    assert _read(client, world["third"], world["biz"]).status_code == 403
    assert _threads(client, world["third"]) == []

    db = client.session_factory()
    try:
        assert db.query(Message).count() == 0
    finally:
        db.close()


def test_writing_to_yourself_is_refused(client, world):
    _job(client, world, "Launch push", "a")
    assert _send(client, world["biz"], world["biz"], "note to self").status_code == 400


def test_the_counterparty_endpoints_need_auth(client, world):
    assert client.get("/messaging/with/someone").status_code == 401
    assert client.post("/messaging/with/someone", json={"body": "x"}).status_code == 401


# --------------------------------------------------------------------------
# Unread is per counterparty
# --------------------------------------------------------------------------


def test_unread_is_counted_per_counterparty_across_contracts(client, world):
    """An unanswered question is unanswered whichever contract it was asked
    under, so the count belongs to the relationship."""
    first = _job(client, world, "Launch push", "a")
    client.post(
        f"/messaging/campaigns/{first['campaign']}/messages",
        json={"to_user_id": world["inf"], "body": "one"},
        headers=_headers(world["biz"]),
    )
    _job(client, world, "Ramadan push", "b")
    _send(client, world["biz"], world["inf"], "two")
    _send(client, world["biz"], world["inf"], "three")

    row = _threads(client, world["inf"])[0]
    assert row["contract_count"] == 2
    assert row["unread_count"] == 3

    # The brand counts nothing: it sent all three.
    assert _threads(client, world["biz"])[0]["unread_count"] == 0


def test_reading_the_conversation_clears_the_whole_relationship(client, world):
    first = _job(client, world, "Launch push", "a")
    client.post(
        f"/messaging/campaigns/{first['campaign']}/messages",
        json={"to_user_id": world["inf"], "body": "one"},
        headers=_headers(world["biz"]),
    )
    _job(client, world, "Ramadan push", "b")
    _send(client, world["biz"], world["inf"], "two")

    read = _read(client, world["inf"], world["biz"]).json()
    assert all(m["read_at"] is not None for m in read)
    assert _threads(client, world["inf"])[0]["unread_count"] == 0

    # And a new one afterwards is unread again.
    _send(client, world["biz"], world["inf"], "three")
    assert _threads(client, world["inf"])[0]["unread_count"] == 1


def test_reading_never_marks_your_own_messages_read(client, world):
    """read_at answers "when did the OTHER person see this". Stamping your own
    outgoing messages would make it useless in a dispute."""
    _job(client, world, "Launch push", "a")
    _send(client, world["biz"], world["inf"], "shot list attached")

    mine = _read(client, world["biz"], world["inf"]).json()
    assert mine[0]["sender_user_id"] == world["biz"]
    assert mine[0]["read_at"] is None

    _read(client, world["inf"], world["biz"])
    db = client.session_factory()
    try:
        assert db.query(Message).first().read_at is not None
    finally:
        db.close()

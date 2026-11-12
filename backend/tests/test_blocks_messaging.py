"""A block mutes the thread without closing it.

THE SHAPE OF EVERY TEST HERE: establish that the message goes through, then
block, then establish that it does not and that the history is still there.
Asserting only the refusal would pass just as happily against messaging that
was broken for everybody.

WHAT IS BEING PINNED, and it is not obvious from the guideline alone. Apple
asks for the ability to block abusive users. A social app satisfies that by
making two people vanish from each other. This product cannot: the two may be
bound by a signed contract with money in escrow, and the thread between them
is the evidence a dispute reads. So the rule is narrower and has to be held
in place by tests, because every instinct pulls towards the social-app answer:

  sending      refused, both paths, both directions
  reading      allowed, both paths, for both parties
  the inbox    the row stays
  the contract untouched
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
from app.modules.campaigns import models as campaigns
from app.modules.contracts import models as contracts
from app.modules.messaging.router import router as messaging_router
from app.modules.trust_safety.models import Block


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    # Sending notifies, which writes a Notification row, so the whole metadata
    # has to exist rather than only the tables this module's imports reached.
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


def _setup(client):
    """A brand, a creator, a campaign and the signed contract between them."""
    db = client.session_factory()
    try:
        biz = User(phone="+22990090001", email="22990090001@kolabo.test", password_hash="x",
                   country_code="BJ", role="business", is_verified=True)
        inf = User(phone="+22990090002", email="22990090002@kolabo.test", password_hash="x",
                   country_code="BJ", role="influencer", is_verified=True)
        db.add_all([biz, inf]); db.commit(); db.refresh(biz); db.refresh(inf)
        camp = campaigns.Campaign(
            business_user_id=biz.id, title="Launch", budget_amount=1000, budget_currency="XOF",
            deliverables=[{"platform": "instagram", "type": "post", "quantity": 1}],
            status=campaigns.PUBLISHED,
        )
        db.add(camp); db.commit(); db.refresh(camp)
        proposal = campaigns.Proposal(
            campaign_id=camp.id, influencer_user_id=inf.id, version=1, rate_amount=100,
            rate_currency="XOF", timeline_days=5, status=campaigns.SUBMITTED,
        )
        db.add(proposal); db.commit(); db.refresh(proposal)
        db.add(contracts.Contract(
            campaign_id=camp.id, proposal_id=proposal.id, business_user_id=biz.id,
            influencer_user_id=inf.id, language="fr", body="placeholder", rate_amount=100,
            rate_currency="XOF", timeline_days=5, deliverables=[], status=contracts.PENDING,
        ))
        db.commit()
        return biz.id, inf.id, camp.id
    finally:
        db.close()


def _block(client, blocker, blocked):
    db = client.session_factory()
    try:
        db.add(Block(blocker_user_id=blocker, blocked_user_id=blocked))
        db.commit()
    finally:
        db.close()


def _send_on_campaign(client, camp, sender, to, body="Shot list attached"):
    return client.post(
        f"/messaging/campaigns/{camp}/messages",
        json={"to_user_id": to, "body": body},
        headers=_headers(sender),
    )


def _send_direct(client, sender, to, body="Filming Thursday"):
    return client.post(f"/messaging/with/{to}", json={"body": body}, headers=_headers(sender))


# ---- sending is refused, on both paths and in both directions ----

def test_the_person_who_blocked_cannot_send_on_the_campaign_path(client):
    biz, inf, camp = _setup(client)
    assert _send_on_campaign(client, camp, biz, inf).status_code == 201

    _block(client, biz, inf)
    r = _send_on_campaign(client, camp, biz, inf, "anything")
    assert r.status_code == 403
    assert r.json()["code"] == "blocked_user"


def test_the_person_who_was_blocked_cannot_send_either_and_is_told(client):
    """The sentence they get is the deliberate part. Silence would leave
    somebody mid-contract believing they had answered."""
    biz, inf, camp = _setup(client)
    _block(client, biz, inf)

    r = _send_on_campaign(client, camp, inf, biz, "I delivered it")
    assert r.status_code == 403
    assert r.json()["code"] == "blocked_by_user"


def test_the_counterparty_path_is_guarded_too(client):
    """Two ways to write a message must not mean one way to be blocked."""
    biz, inf, camp = _setup(client)
    assert _send_direct(client, biz, inf).status_code == 201

    _block(client, biz, inf)
    assert _send_direct(client, biz, inf, "anything").json()["code"] == "blocked_user"
    assert _send_direct(client, inf, biz, "anything").json()["code"] == "blocked_by_user"


def test_a_block_the_other_way_round_reads_the_other_way_round(client):
    biz, inf, camp = _setup(client)
    _block(client, inf, biz)

    assert _send_on_campaign(client, camp, inf, biz, "x").json()["code"] == "blocked_user"
    assert _send_on_campaign(client, camp, biz, inf, "x").json()["code"] == "blocked_by_user"


def test_the_gate_still_answers_first_for_somebody_with_no_contract(client):
    """Order of disclosure: a stranger learns nothing about a block, because
    they never get past the contract gate to hear about one."""
    biz, inf, camp = _setup(client)
    db = client.session_factory()
    outsider = User(phone="+22990090003", email="22990090003@kolabo.test", password_hash="x",
                    country_code="BJ", role="influencer", is_verified=True)
    db.add(outsider); db.commit(); db.refresh(outsider)
    oid = outsider.id
    db.close()

    _block(client, biz, oid)
    r = _send_on_campaign(client, camp, biz, oid, "x")
    assert r.status_code == 403
    assert r.json()["code"] == "message_gate"


# ---- reading is untouched ----

def test_both_parties_can_still_read_the_thread_after_a_block(client):
    """The history is the evidence a dispute runs on, and the party most
    likely to need it is the one who just blocked somebody."""
    biz, inf, camp = _setup(client)
    _send_on_campaign(client, camp, biz, inf, "one")
    _send_on_campaign(client, camp, inf, biz, "two")

    _block(client, biz, inf)

    for reader, other in ((biz, inf), (inf, biz)):
        thread = client.get(
            f"/messaging/campaigns/{camp}/messages",
            params={"with_user_id": other},
            headers=_headers(reader),
        )
        assert thread.status_code == 200
        assert [m["body"] for m in thread.json()] == ["one", "two"]


def test_the_counterparty_conversation_still_reads_after_a_block(client):
    biz, inf, camp = _setup(client)
    _send_direct(client, biz, inf, "one")
    _block(client, inf, biz)

    r = client.get(f"/messaging/with/{inf}", headers=_headers(biz))
    assert r.status_code == 200
    assert [m["body"] for m in r.json()] == ["one"]


def test_the_inbox_row_survives_a_block(client):
    """Hiding the thread would hide the job. The contract still exists and the
    work may still be owed."""
    biz, inf, camp = _setup(client)
    _block(client, biz, inf)

    threads = client.get("/messaging/threads", headers=_headers(biz)).json()
    assert [t["counterparty_user_id"] for t in threads] == [inf]
    assert threads[0]["contract_count"] == 1


# ---- the unrelated cases still behave ----

def test_an_unblocked_pair_is_entirely_unaffected(client):
    biz, inf, camp = _setup(client)
    assert _send_on_campaign(client, camp, biz, inf).status_code == 201
    assert _send_direct(client, inf, biz).status_code == 201


def test_writing_to_yourself_is_still_the_answer_it_was(client):
    """The self check runs before the gate and before the block, so blocking
    cannot change what this says."""
    biz, inf, camp = _setup(client)
    assert _send_on_campaign(client, camp, biz, biz, "note to self").status_code == 400

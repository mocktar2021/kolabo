"""The contract gate on messaging, and the inbox it makes possible.

The product decision under test: a thread opens ONLY once a contract exists
between the two parties on that campaign. Open messaging between any brand and
any creator is a lead channel people mine and abandon, and a conversation that
starts before there is a deal is a conversation that leaves for WhatsApp —
where there is no contract, no escrow and no recourse. After a contract it is
a work channel, the platform has earned its fee, and the thread is the
evidence trail a dispute reads.

Nobody outside the contract gets in, including an admin: this module has no
admin path, so an administrator is simply a third party here, which is what
the third-party test is really pinning down.
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
    app.include_router(messaging_router, prefix="/messaging")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _rows(client, model, **filters):
    db = client.session_factory()
    try:
        query = db.query(model)
        for field, value in filters.items():
            query = query.filter(getattr(model, field) == value)
        return query.all()
    finally:
        db.close()


@pytest.fixture()
def world(client):
    """A brand and a creator on a campaign, plus an unrelated third party.

    Both sides have a profile, because the inbox has to name them: a creator
    by display name, a business by company name. No contract yet — the tests
    that need one call _sign_contract, so the locked case is the default.
    """
    db = client.session_factory()
    try:
        biz = User(phone="+22990040001", password_hash="x", country_code="BJ", role="business", is_verified=True)
        inf = User(phone="+22990040002", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        third = User(phone="+22990040003", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add_all([biz, inf, third]); db.commit()
        db.refresh(biz); db.refresh(inf); db.refresh(third)
        db.add(BusinessProfile(user_id=biz.id, company_name="Maison Kola"))
        db.add(InfluencerProfile(user_id=inf.id, display_name="Ama K.", avatar_media_id="media-abc"))
        camp = campaigns.Campaign(
            business_user_id=biz.id, title="Launch push", budget_amount=500000,
            budget_currency="XOF",
            deliverables=[{"platform": "instagram", "type": "post", "quantity": 2}],
            status=campaigns.PUBLISHED,
        )
        db.add(camp); db.commit(); db.refresh(camp)
        # An invitation AND a proposal, both of which used to unlock messaging
        # and now do not. Their presence is what makes the locked tests mean
        # something.
        db.add(campaigns.CampaignInvitation(
            campaign_id=camp.id, influencer_user_id=inf.id, status=campaigns.INVITED
        ))
        proposal = campaigns.Proposal(
            campaign_id=camp.id, influencer_user_id=inf.id, version=1, rate_amount=40000,
            rate_currency="XOF", timeline_days=7, status=campaigns.SUBMITTED,
        )
        db.add(proposal); db.commit(); db.refresh(proposal)
        return {
            "biz": biz.id, "inf": inf.id, "third": third.id,
            "campaign": camp.id, "proposal": proposal.id,
        }
    finally:
        db.close()


def _sign_contract(client, world):
    db = client.session_factory()
    try:
        contract = contracts.Contract(
            campaign_id=world["campaign"], proposal_id=world["proposal"],
            business_user_id=world["biz"], influencer_user_id=world["inf"],
            language="fr", body="placeholder", rate_amount=40000, rate_currency="XOF",
            timeline_days=7, deliverables=[], status=contracts.PENDING,
        )
        db.add(contract); db.commit(); db.refresh(contract)
        return contract.id
    finally:
        db.close()


def _send(client, world, sender, to, body):
    return client.post(
        f"/messaging/campaigns/{world['campaign']}/messages",
        json={"to_user_id": to, "body": body},
        headers=_headers(sender),
    )


def _read(client, world, reader, other):
    return client.get(
        f"/messaging/campaigns/{world['campaign']}/messages",
        params={"with_user_id": other},
        headers=_headers(reader),
    )


# --------------------------------------------------------------------------
# Before a contract there is no thread
# --------------------------------------------------------------------------


def test_without_a_contract_neither_side_can_send(client, world):
    """An invitation and a proposal exist on this campaign. Neither is a deal."""
    from_brand = _send(client, world, world["biz"], world["inf"], "What are your rates?")
    assert from_brand.status_code == 403
    assert "contract" in from_brand.json()["detail"].lower()

    from_creator = _send(client, world, world["inf"], world["biz"], "Can we talk off-platform?")
    assert from_creator.status_code == 403

    assert _rows(client, Message) == []


def test_without_a_contract_neither_side_can_list(client, world):
    assert _read(client, world, world["biz"], world["inf"]).status_code == 403
    assert _read(client, world, world["inf"], world["biz"]).status_code == 403


def test_without_a_contract_the_inbox_is_empty(client, world):
    assert client.get("/messaging/threads", headers=_headers(world["biz"])).json() == []
    assert client.get("/messaging/threads", headers=_headers(world["inf"])).json() == []


# --------------------------------------------------------------------------
# A contract opens it, for exactly two people
# --------------------------------------------------------------------------


def test_both_parties_can_write_and_read_once_a_contract_exists(client, world):
    _sign_contract(client, world)

    assert _send(client, world, world["biz"], world["inf"], "Shot list attached").status_code == 201
    assert _send(client, world, world["inf"], world["biz"], "Filming Thursday").status_code == 201

    for reader, other in ((world["biz"], world["inf"]), (world["inf"], world["biz"])):
        thread = _read(client, world, reader, other)
        assert thread.status_code == 200
        assert [m["body"] for m in thread.json()] == ["Shot list attached", "Filming Thursday"]


def test_a_third_party_is_refused_even_with_a_contract_on_the_campaign(client, world):
    """The gate is per pair, not per campaign — and there is no admin path into
    this module, so an administrator is a third party here like anyone else."""
    _sign_contract(client, world)
    _send(client, world, world["biz"], world["inf"], "Shot list attached")

    assert _send(client, world, world["third"], world["biz"], "Me too?").status_code == 403
    assert _send(client, world, world["biz"], world["third"], "You are next").status_code == 403
    assert _read(client, world, world["third"], world["biz"]).status_code == 403
    # And it never shows up in their inbox.
    assert client.get("/messaging/threads", headers=_headers(world["third"])).json() == []
    assert len(_rows(client, Message)) == 1


# --------------------------------------------------------------------------
# The inbox
# --------------------------------------------------------------------------


def test_the_thread_list_names_the_counterparty_and_counts_the_unread(client, world):
    contract_id = _sign_contract(client, world)
    _send(client, world, world["biz"], world["inf"], "Shot list attached")
    _send(client, world, world["biz"], world["inf"], "And the deadline moved")

    # The creator's inbox names the BUSINESS, by its company name.
    creator_inbox = client.get("/messaging/threads", headers=_headers(world["inf"])).json()
    assert len(creator_inbox) == 1
    row = creator_inbox[0]
    assert row["campaign_id"] == world["campaign"]
    assert row["campaign_title"] == "Launch push"
    assert row["contract_id"] == contract_id
    assert row["counterparty_user_id"] == world["biz"]
    assert row["counterparty_name"] == "Maison Kola"
    assert row["last_message"] == "And the deadline moved"
    assert row["last_message_at"] is not None
    assert row["unread_count"] == 2

    # The brand's inbox names the CREATOR, the same way a proposal row does,
    # and counts nothing unread: it sent both messages.
    brand_inbox = client.get("/messaging/threads", headers=_headers(world["biz"])).json()
    assert brand_inbox[0]["counterparty_user_id"] == world["inf"]
    assert brand_inbox[0]["counterparty_name"] == "Ama K."
    assert brand_inbox[0]["counterparty_avatar_url"] == "/profiles/media/media-abc"
    assert brand_inbox[0]["unread_count"] == 0


def test_a_signed_contract_with_no_messages_still_shows_a_thread(client, world):
    """An empty thread is exactly the one somebody needs to start."""
    _sign_contract(client, world)
    row = client.get("/messaging/threads", headers=_headers(world["biz"])).json()[0]
    assert row["last_message"] is None
    assert row["last_message_at"] is None
    assert row["unread_count"] == 0


def test_reading_a_thread_clears_the_unread_count(client, world):
    _sign_contract(client, world)
    _send(client, world, world["biz"], world["inf"], "Shot list attached")
    _send(client, world, world["biz"], world["inf"], "And the deadline moved")

    read = _read(client, world, world["inf"], world["biz"]).json()
    # Opening the thread IS reading it, so the response already carries the
    # stamp rather than making the client ask again.
    assert all(m["read_at"] is not None for m in read)

    assert client.get("/messaging/threads", headers=_headers(world["inf"])).json()[0]["unread_count"] == 0

    # A new message afterwards is unread again.
    _send(client, world, world["biz"], world["inf"], "One more thing")
    assert client.get("/messaging/threads", headers=_headers(world["inf"])).json()[0]["unread_count"] == 1


def test_reading_never_marks_your_own_messages_read(client, world):
    """read_at answers "when did the OTHER person see this". Stamping your own
    outgoing messages would make it useless in a dispute."""
    _sign_contract(client, world)
    _send(client, world, world["biz"], world["inf"], "Shot list attached")

    thread = _read(client, world, world["biz"], world["inf"]).json()
    assert thread[0]["sender_user_id"] == world["biz"]
    assert thread[0]["read_at"] is None

    # Until the creator opens it.
    _read(client, world, world["inf"], world["biz"])
    assert _rows(client, Message)[0].read_at is not None

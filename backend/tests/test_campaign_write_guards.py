"""Who may write to a campaign, and when a campaign stops taking writes.

Four gaps of the same shape, and the shape is worth naming: every one of these
paths asked whether the CALLER owned the row, and none of them asked whether
the ROW was still in a state that takes the write. So a stranger holding a
campaign id could bid on somebody else's private order, a buyer could counter
on a brief it had already called off, a cancelled brief could be quietly
brought back to life, and one creator could be invited to the same campaign
twice and told about it twice.

EVERY REFUSAL HERE IS ASSERTED TWICE: the status and the code the caller gets
back, and the fact that nothing was written. A guard that answers 400 and
writes the row anyway reads as green in a test that only checks the status,
and it is the worse of the two bugs — the caller is told no while the database
says yes.

The codes are asserted rather than the English sentences. A code names the
rule, and both clients key their translated sentence off it; the sentence
itself is free to be reworded without touching this file.
"""
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.errors import AppError, app_error_handler
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.campaigns import models as campaigns
from app.modules.campaigns.router import router as campaigns_router
from app.modules.notifications.models import Notification
from app.modules.profiles.models import Package


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
    # The REAL handler, registered from app.core.errors rather than re-declared
    # here: without it FastAPI renders {"detail": ...} alone and every
    # assertion below would be reading a key that is not there. Same
    # registration and same reasoning as test_error_codes.py's fixture.
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(campaigns_router, prefix="/campaigns")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


# --------------------------------------------------------------------------
# Fixtures and helpers
# --------------------------------------------------------------------------


def _user(client, phone, role, verified=True):
    db = client.session_factory()
    try:
        u = User(phone=phone, password_hash="x", country_code="BJ", role=role, is_verified=verified)
        db.add(u); db.commit(); db.refresh(u)
        return u.id, {"Authorization": f"Bearer {create_access_token(u.id)}"}
    finally:
        db.close()


def _brief(client, headers, is_open=False, publish=True):
    """A complete brief, published or not, open to the board or not.

    is_open defaults to FALSE because that is the column's own default and the
    state these guards are about: a brief the brand keeps to the creators it
    invited. The open-board case passes is_open=True explicitly, so every test
    below says out loud which of the two briefs it is talking about.
    """
    r = client.post("/campaigns/", json={
        "title": "Launch push",
        "budget_amount": 50000,
        "budget_currency": "XOF",
        "deliverables": [{"platform": "instagram", "type": "post", "quantity": 2}],
        "deadline": "2026-12-01",
        "publish": publish,
        "is_open": is_open,
    }, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _invite(client, cid, headers, influencer_id):
    return client.post(
        f"/campaigns/{cid}/invitations", json={"influencer_id": influencer_id}, headers=headers
    )


def _submit(client, cid, headers, rate=10000, days=7):
    return client.post(
        f"/campaigns/{cid}/proposals",
        json={"rate_amount": rate, "rate_currency": "XOF", "timeline_days": days},
        headers=headers,
    )


def _reply(client, cid, pid, headers, note="Noted.", rate=None, days=None):
    payload = {"note": note}
    if rate is not None:
        payload["rate_amount"] = rate
    if days is not None:
        payload["timeline_days"] = days
    return client.post(f"/campaigns/{cid}/proposals/{pid}/reply", json=payload, headers=headers)


def _package(client, creator_id, price=25000):
    """A published package on a creator's profile, which an order is placed on."""
    db = client.session_factory()
    try:
        pkg = Package(
            user_id=creator_id,
            platform="instagram",
            deliverable_type="reel",
            title="Two reels, shot and edited",
            price_amount=price,
            currency="XOF",
            quantity=2,
            is_active=True,
        )
        db.add(pkg); db.commit(); db.refresh(pkg)
        return pkg.id
    finally:
        db.close()


def _direct_order(client, buyer_headers, package_id):
    """An order placed THROUGH THE REAL ENDPOINT, not assembled by hand.

    The whole point of the exemption these tests pin is that a direct order
    carries exactly one invitation, written by service._place_order beside the
    single offer the creator is answering. A test that seeded the campaign and
    the proposal itself and forgot the invitation would prove the guard
    refuses a creator it is meant to let through, and would prove it against
    an order that cannot exist in production.
    """
    r = client.post("/campaigns/orders", json={"package_id": package_id}, headers=buyer_headers)
    assert r.status_code == 201, r.text
    return r.json()


def _rows(client, model, **filters):
    db = client.session_factory()
    try:
        query = db.query(model)
        for field, value in filters.items():
            query = query.filter(getattr(model, field) == value)
        return query.all()
    finally:
        db.close()


def _force_status(client, cid, status):
    """Set a campaign's status on the row.

    Used for `completed` only. How a campaign BECOMES completed is
    campaigns.completion's rule — every contract ended and at least one of
    those endings moved money — and test_cancellations.py owns it. What these
    tests are about is what the write paths do once the row says `completed`,
    so the row is what they set.
    """
    db = client.session_factory()
    try:
        c = db.query(campaigns.Campaign).filter(campaigns.Campaign.id == cid).first()
        c.status = status
        db.commit()
    finally:
        db.close()


def _age_out(client, proposal_id):
    """Push an order's acceptance window into the past, as 48 real hours would."""
    db = client.session_factory()
    try:
        p = db.query(campaigns.Proposal).filter(campaigns.Proposal.id == proposal_id).first()
        p.expires_at = campaigns.utcnow() - timedelta(hours=1)
        db.commit()
    finally:
        db.close()


# --------------------------------------------------------------------------
# A1 — who may bid on a campaign at all
#
# The invitation is what separates a stranger from a legitimate bidder. An
# OPEN brief takes bids from anybody; everything else has to have been
# addressed to this creator.
# --------------------------------------------------------------------------


def test_an_uninvited_creator_cannot_bid_on_a_closed_brief(client):
    """A published brief that is not on the open board is invite-only.

    Before the guard, `published` was the only question asked, so any signed-in
    creator could bid on any brief the brand had deliberately kept closed —
    applications arriving from people the brand had never heard of, against a
    brief it thought was private.
    """
    _, biz = _user(client, "+22990005001", "business")
    _, stranger = _user(client, "+22990005002", "influencer")
    cid = _brief(client, biz, is_open=False)

    r = _submit(client, cid, stranger)
    assert r.status_code == 400
    assert r.json()["code"] == "board_not_open"
    # And the refusal wrote nothing: no chain was opened on the brand's page.
    assert _rows(client, campaigns.Proposal, campaign_id=cid) == []


def test_an_invited_creator_can_bid_on_the_same_closed_brief(client):
    """The other edge of the same guard, on the same shape of brief: the
    invitation is the whole difference between these two tests."""
    _, biz = _user(client, "+22990005003", "business")
    inf_id, inf = _user(client, "+22990005004", "influencer")
    cid = _brief(client, biz, is_open=False)
    assert _invite(client, cid, biz, inf_id).status_code == 201

    r = _submit(client, cid, inf)
    assert r.status_code == 201
    assert r.json()["version"] == 1
    assert len(_rows(client, campaigns.Proposal, campaign_id=cid)) == 1


def test_a_stranger_cannot_bid_on_somebody_elses_direct_order(client):
    """A direct order is a private transaction between two named parties.

    This was an AUTHORISATION HOLE and not merely noise on a list:
    orders._load_order authorises a decline by the PROPOSAL's creator, so a
    stranger who opened a chain on somebody else's order could then decline it
    and cancel the order out from under both parties.
    """
    _, biz = _user(client, "+22990005005", "business")
    creator_id, _creator = _user(client, "+22990005006", "influencer")
    stranger_id, stranger = _user(client, "+22990005007", "influencer")
    order = _direct_order(client, biz, _package(client, creator_id))

    r = _submit(client, order["campaign_id"], stranger)
    assert r.status_code == 400
    # Not board_not_open: a direct order is never open, so "this brief is not
    # open" would be a true sentence that explains nothing about what the
    # caller found.
    assert r.json()["code"] == "board_direct_order"
    # Nothing written for the stranger, and the order's own offer is still the
    # only row in the campaign.
    assert _rows(client, campaigns.Proposal, campaign_id=order["campaign_id"],
                 influencer_user_id=stranger_id) == []
    assert len(_rows(client, campaigns.Proposal, campaign_id=order["campaign_id"])) == 1


def test_the_creator_a_direct_order_was_addressed_to_can_still_counter(client):
    """THE EXEMPTION, and the reason the guard is written on the invitation
    rather than on is_direct.

    There is no creator-side counter endpoint: the next version in the chain
    IS the counter, and it comes through the same submit path a stranger was
    just refused on. What lets one through and not the other is the single
    invitation _place_order writes beside the offer. A guard that simply
    refused every direct order would have closed the only way a creator can
    negotiate an order instead of taking it or leaving it.
    """
    _, biz = _user(client, "+22990005008", "business")
    creator_id, creator = _user(client, "+22990005009", "influencer")
    order = _direct_order(client, biz, _package(client, creator_id))

    r = _submit(client, order["campaign_id"], creator, rate=30000, days=10)
    assert r.status_code == 201
    counter = r.json()
    assert counter["version"] == 2
    assert counter["author_role"] == "influencer"
    assert counter["rate_amount"] == 30000

    chain = _rows(client, campaigns.Proposal, campaign_id=order["campaign_id"])
    assert sorted(p.version for p in chain) == [1, 2]
    # The buyer's opening offer was superseded by the answer to it, exactly as
    # it would be on a brief.
    opening = [p for p in chain if p.version == 1][0]
    assert opening.status == campaigns.SUPERSEDED


def test_any_creator_can_still_bid_on_an_open_brief(client):
    """The happy path the board depends on, untouched: an open brief takes
    bids from a creator nobody invited, which is what `open` means."""
    _, biz = _user(client, "+22990005010", "business")
    _, inf = _user(client, "+22990005011", "influencer")
    cid = _brief(client, biz, is_open=True)

    r = _submit(client, cid, inf)
    assert r.status_code == 201
    assert r.json()["version"] == 1


# --------------------------------------------------------------------------
# A2 — the business reply, on a dead or lapsed chain
# --------------------------------------------------------------------------


def test_the_business_cannot_counter_on_a_campaign_it_cancelled(client):
    """Calling a brief off told every invited creator it was over. Countering
    on it afterwards writes a fresh live offer, and notifies the creator of it,
    on a campaign that no longer exists as far as they were told."""
    _, biz = _user(client, "+22990005012", "business")
    _, inf = _user(client, "+22990005013", "influencer")
    cid = _brief(client, biz, is_open=True)
    first = _submit(client, cid, inf).json()
    assert client.post(f"/campaigns/{cid}/cancel", headers=biz).status_code == 200

    r = _reply(client, cid, first["id"], biz, note="Can you do 8000?", rate=8000)
    assert r.status_code == 400
    # submit_proposal's code, reused: the same rule — this campaign is not in a
    # state that takes new proposal versions — and a reply IS a version.
    assert r.json()["code"] == "campaign_not_open"
    assert len(_rows(client, campaigns.Proposal, campaign_id=cid)) == 1


def test_the_business_cannot_counter_on_a_completed_campaign(client):
    """The same hole with worse consequences: the brief is filled and paid,
    and completion.close_open_offers has already closed the chains under it."""
    _, biz = _user(client, "+22990005014", "business")
    _, inf = _user(client, "+22990005015", "influencer")
    cid = _brief(client, biz, is_open=True)
    first = _submit(client, cid, inf).json()
    _force_status(client, cid, campaigns.COMPLETED)

    r = _reply(client, cid, first["id"], biz, note="One more round?", rate=8000)
    assert r.status_code == 400
    assert r.json()["code"] == "campaign_not_open"
    assert len(_rows(client, campaigns.Proposal, campaign_id=cid)) == 1


def test_the_business_cannot_counter_after_the_order_window_closed(client):
    """A counter written after the order lapsed puts a live-looking offer in
    front of a creator who can no longer accept it — accept_direct_order
    refuses with this same code — and leaves a dead order reading as a running
    negotiation on both screens."""
    _, biz = _user(client, "+22990005016", "business")
    creator_id, _creator = _user(client, "+22990005017", "influencer")
    order = _direct_order(client, biz, _package(client, creator_id))
    _age_out(client, order["proposal_id"])

    r = _reply(client, order["campaign_id"], order["proposal_id"], biz,
               note="Meet me at 20000?", rate=20000)
    assert r.status_code == 400
    assert r.json()["code"] == "order_expired"
    assert len(_rows(client, campaigns.Proposal, campaign_id=order["campaign_id"])) == 1


def test_the_business_can_still_counter_on_a_live_brief(client):
    """The happy path: none of the three guards above touches an ordinary
    negotiation on a published campaign."""
    _, biz = _user(client, "+22990005018", "business")
    _, inf = _user(client, "+22990005019", "influencer")
    cid = _brief(client, biz, is_open=True)
    first = _submit(client, cid, inf).json()

    r = _reply(client, cid, first["id"], biz, note="8000 is our ceiling.", rate=8000)
    assert r.status_code == 201
    assert r.json()["version"] == 2
    assert r.json()["author_role"] == "business"
    assert len(_rows(client, campaigns.Proposal, campaign_id=cid)) == 2


# --------------------------------------------------------------------------
# Publishing is a draft's one transition
# --------------------------------------------------------------------------


def test_a_cancelled_campaign_cannot_be_republished(client):
    """Nothing here read the current status, so `cancelled` -> `published` was
    a single call: a brief every invited creator had been told was off came
    back live with none of them told, and campaigns.editing's
    campaign_cancelled_immutable became a lock the buyer opens by republishing
    first and editing afterwards."""
    _, biz = _user(client, "+22990005020", "business")
    cid = _brief(client, biz, is_open=True)
    assert client.post(f"/campaigns/{cid}/cancel", headers=biz).status_code == 200

    r = client.post(f"/campaigns/{cid}/publish", headers=biz)
    assert r.status_code == 400
    assert r.json()["code"] == "campaign_publish_not_draft"
    assert _rows(client, campaigns.Campaign, id=cid)[0].status == campaigns.CANCELLED


def test_a_completed_campaign_cannot_be_republished(client):
    """The same call on a brief already delivered and paid for. COMPLETED is
    reached only from PUBLISHED and is never left."""
    _, biz = _user(client, "+22990005021", "business")
    cid = _brief(client, biz, is_open=True)
    _force_status(client, cid, campaigns.COMPLETED)

    r = client.post(f"/campaigns/{cid}/publish", headers=biz)
    assert r.status_code == 400
    assert r.json()["code"] == "campaign_publish_not_draft"
    assert _rows(client, campaigns.Campaign, id=cid)[0].status == campaigns.COMPLETED


def test_a_draft_can_still_be_published(client):
    """The transition the guard exists to leave alone. Written as "must be
    DRAFT" rather than "must not be cancelled" precisely so that this stays
    the only status that passes."""
    _, biz = _user(client, "+22990005022", "business")
    cid = _brief(client, biz, is_open=True, publish=False)
    assert _rows(client, campaigns.Campaign, id=cid)[0].status == campaigns.DRAFT

    r = client.post(f"/campaigns/{cid}/publish", headers=biz)
    assert r.status_code == 200
    assert r.json()["status"] == campaigns.PUBLISHED


# --------------------------------------------------------------------------
# One invitation per creator per campaign
# --------------------------------------------------------------------------


def test_inviting_the_same_creator_twice_is_refused_and_sends_no_second_notice(client):
    """A buyer double-tapping the button — or working a favourites list twice
    — wrote a second row and sent a second "you were invited to X", and the
    creator's list then showed the same brief twice with one proposal chain
    between them.

    THE DUPLICATE NOTIFICATION IS HALF THE BUG, so it is asserted here rather
    than left to be noticed in production: the row can be reasoned about, but
    the push has already gone out.
    """
    _, biz = _user(client, "+22990005023", "business")
    inf_id, _inf = _user(client, "+22990005024", "influencer")
    cid = _brief(client, biz, is_open=False)
    assert _invite(client, cid, biz, inf_id).status_code == 201

    r = _invite(client, cid, biz, inf_id)
    # 409 and not 400: the request was well formed and the caller may well have
    # meant it — it collides with a row that already exists.
    assert r.status_code == 409
    assert r.json()["code"] == "invitation_already_sent"
    assert len(_rows(client, campaigns.CampaignInvitation, campaign_id=cid)) == 1
    notices = _rows(client, Notification, user_id=inf_id, type="campaign_invitation")
    assert len(notices) == 1


def test_a_creator_cannot_be_invited_to_a_direct_order(client):
    """An order carries exactly one creator, and a second invitation would put
    somebody on an order with no proposal to answer and no way to answer it —
    /orders/{id}/accept takes a proposal id, and theirs does not exist."""
    _, biz = _user(client, "+22990005025", "business")
    creator_id, _creator = _user(client, "+22990005026", "influencer")
    other_id, _other = _user(client, "+22990005027", "influencer")
    order = _direct_order(client, biz, _package(client, creator_id))

    r = _invite(client, order["campaign_id"], biz, other_id)
    assert r.status_code == 400
    # campaigns.editing's code, not board's. Both name the same fact, but this
    # is the BUYER being told a direct order is not administered like a brief,
    # where board_direct_order tells a CREATOR they cannot bid.
    assert r.json()["code"] == "campaign_is_direct_order"
    # The order's own invitation, and nothing beside it.
    invitations = _rows(client, campaigns.CampaignInvitation, campaign_id=order["campaign_id"])
    assert len(invitations) == 1
    assert invitations[0].influencer_user_id == creator_id


def test_a_first_invitation_on_a_normal_brief_still_succeeds(client):
    """The happy path: the duplicate guard costs the ordinary invite nothing."""
    _, biz = _user(client, "+22990005028", "business")
    inf_id, _inf = _user(client, "+22990005029", "influencer")
    cid = _brief(client, biz, is_open=False)

    r = _invite(client, cid, biz, inf_id)
    assert r.status_code == 201
    assert r.json()["influencer_user_id"] == inf_id
    assert len(_rows(client, campaigns.CampaignInvitation, campaign_id=cid)) == 1
    assert len(_rows(client, Notification, user_id=inf_id, type="campaign_invitation")) == 1

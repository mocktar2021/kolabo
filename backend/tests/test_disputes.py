"""Disputes (KOL-37): raising one, answering it, and how it reaches an admin."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.contracts import models as contracts
from app.modules.notifications.models import Notification
from app.modules.payments import models as pay_models
from app.modules.payments import provider as provider_module
from app.modules.payments import service as pay_service
from app.modules.payments.router import router as payments_router
from app.modules.profiles import models as profiles


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    pay_service.payment_provider = provider_module.MockProvider()

    app = FastAPI()
    app.include_router(payments_router, prefix="/payments")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


ADMIN = {"X-Admin-Id": "admin-1"}

STATEMENT = "The reel was never posted and the agreed date passed four days ago."


def _body(**overrides):
    body = {"reason": "not_delivered", "statement": STATEMENT, "media_ids": []}
    body.update(overrides)
    return body


def _user(db, phone, role):
    u = User(phone=phone, password_hash="x", country_code="BJ", role=role, is_verified=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _funded(client, amount=10000, suffix="1"):
    """A held escrow between a business and a creator, plus a bystander."""
    db = client.session_factory()
    try:
        biz = _user(db, f"+2299000{suffix}001", "business")
        inf = _user(db, f"+2299000{suffix}002", "influencer")
        stranger = _user(db, f"+2299000{suffix}003", "influencer")
        c = contracts.Contract(
            campaign_id=f"camp-{suffix}", proposal_id=f"prop-{suffix}", business_user_id=biz.id,
            influencer_user_id=inf.id, language="fr", body="body", rate_amount=amount,
            rate_currency="XOF", timeline_days=7, status=contracts.SIGNED,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        ids = (biz.id, inf.id, stranger.id, c.id)
    finally:
        db.close()
    biz_id, inf_id, stranger_id, contract_id = ids
    escrow = client.post(
        "/payments/escrow/fund", json={"contract_id": contract_id}, headers=_headers(biz_id)
    ).json()
    return biz_id, inf_id, stranger_id, escrow


def _disputed(client, amount=10000, suffix="1"):
    """A funded escrow with an open dispute raised by the creator."""
    biz, inf, stranger, escrow = _funded(client, amount=amount, suffix=suffix)
    dispute = client.post(
        f"/payments/escrow/{escrow['id']}/dispute", json=_body(), headers=_headers(inf)
    ).json()
    return biz, inf, stranger, escrow, dispute


def _media(client, owner_id):
    db = client.session_factory()
    try:
        asset = profiles.MediaAsset(owner_user_id=owner_id, content_type="image/png", data=b"fake")
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset.id
    finally:
        db.close()


def _notices(client, user_id, type="dispute"):
    db = client.session_factory()
    try:
        return [
            n.message
            for n in db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.type == type)
            .all()
        ]
    finally:
        db.close()


def _age_window(client, dispute_id):
    """Force a dispute's response window into the past."""
    db = client.session_factory()
    try:
        d = db.query(pay_models.Dispute).filter(pay_models.Dispute.id == dispute_id).first()
        d.respond_by = pay_models.utcnow().replace(year=2020)
        db.commit()
    finally:
        db.close()


def _escrow_row(client, escrow_id):
    db = client.session_factory()
    try:
        return db.query(pay_models.Escrow).filter(pay_models.Escrow.id == escrow_id).first()
    finally:
        db.close()


# --- Raising one --------------------------------------------------------


def test_raising_a_dispute_freezes_the_escrow_and_starts_the_window(client):
    """The escrow freezes, the reason and statement are on record, and the
    evidence points at the image the creator already uploaded."""
    biz, inf, _, escrow = _funded(client)
    media_id = _media(client, inf)
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute",
        json=_body(reason="payment_issue", media_ids=[media_id]),
        headers=_headers(inf),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "awaiting_response"
    assert body["reason"] == "payment_issue"
    assert body["opened_by_user_id"] == inf
    assert body["attachments"] == [f"/profiles/media/{media_id}"]
    # The escrow itself is frozen, which is the whole point of raising one.
    assert body["escrow"]["status"] == "disputed"
    assert client.get(f"/payments/escrow/{escrow['id']}", headers=_headers(biz)).json()["status"] == "disputed"
    # respond_by is in the future: the window is open, nobody is queued yet.
    assert body["respond_by"] > pay_models.utcnow().isoformat()


def test_a_reason_outside_the_closed_set_is_refused(client):
    """The reason drives the admin queue and later the fraud counts. Free text
    would make both unreadable."""
    _, inf, _, escrow = _funded(client)
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute",
        json=_body(reason="i_just_do_not_like_it"),
        headers=_headers(inf),
    )
    assert r.status_code in (400, 422)


def test_a_statement_too_short_to_act_on_is_refused(client):
    _, inf, _, escrow = _funded(client)
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute",
        json=_body(statement="bad"),
        headers=_headers(inf),
    )
    assert r.status_code in (400, 422)


def test_someone_elses_image_cannot_be_attached(client):
    """Attaching an image you do not own would leak it into the dispute: the
    other party and every admin who reads the case would see it."""
    _, inf, stranger, escrow = _funded(client)
    theirs = _media(client, stranger)
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute",
        json=_body(media_ids=[theirs]),
        headers=_headers(inf),
    )
    assert r.status_code == 403
    # Nothing was written: the escrow is still held.
    assert client.get(f"/payments/escrow/{escrow['id']}", headers=_headers(inf)).json()["status"] == "held"


def test_a_third_party_cannot_raise_a_dispute(client):
    _, _, stranger, escrow = _funded(client)
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute", json=_body(), headers=_headers(stranger)
    )
    assert r.status_code == 403


def test_a_released_escrow_has_nothing_left_to_freeze(client):
    """The payout has already been made at the provider. Answering 200 would
    tell a creator their money was stopped when it was not."""
    biz, inf, _, escrow = _funded(client)
    assert client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz)).status_code == 200
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute", json=_body(), headers=_headers(inf)
    )
    assert r.status_code == 400


def test_a_second_open_dispute_on_the_same_escrow_is_a_conflict(client):
    """Two live cases over the same money would fork the thread and give an
    admin two half-cases. A party with more to say posts a message."""
    biz, inf, _, escrow = _funded(client)
    assert client.post(
        f"/payments/escrow/{escrow['id']}/dispute", json=_body(), headers=_headers(inf)
    ).status_code == 201
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute", json=_body(), headers=_headers(biz)
    )
    assert r.status_code == 409


def test_the_other_party_is_notified_and_told_about_the_window(client):
    """That message, not an admin, is what usually ends the dispute."""
    biz, inf, _, escrow = _funded(client)
    client.post(f"/payments/escrow/{escrow['id']}/dispute", json=_body(), headers=_headers(inf))
    told = _notices(client, biz)
    assert len(told) == 1
    assert "72 hours" in told[0]
    # The opener is told too, so both sides know the money is frozen.
    assert len(_notices(client, inf)) == 1


# --- The thread ---------------------------------------------------------


def test_both_parties_can_post_to_the_thread(client):
    biz, inf, _, escrow, dispute = _disputed(client)
    image = _media(client, biz)
    r = client.post(
        f"/payments/disputes/{dispute['id']}/messages",
        json={"body": "I never received the draft. Here is the empty folder.", "media_ids": [image]},
        headers=_headers(biz),
    )
    assert r.status_code == 201
    assert r.json()["attachments"] == [f"/profiles/media/{image}"]
    r2 = client.post(
        f"/payments/disputes/{dispute['id']}/messages",
        json={"body": "It was sent on the 4th, resending now."},
        headers=_headers(inf),
    )
    assert r2.status_code == 201


def test_a_third_party_cannot_post_to_the_thread(client):
    _, _, stranger, escrow, dispute = _disputed(client)
    r = client.post(
        f"/payments/disputes/{dispute['id']}/messages",
        json={"body": "Let me weigh in on this contract I am not party to."},
        headers=_headers(stranger),
    )
    assert r.status_code == 403


def test_both_parties_having_spoken_escalates_immediately(client):
    """The window exists to let them settle it. Once both have spoken and the
    money is still frozen, waiting out the clock only delays the queue."""
    biz, inf, _, escrow, dispute = _disputed(client)
    # The other party's first reply does NOT escalate: that reply is usually
    # the thing that ends the dispute.
    client.post(
        f"/payments/disputes/{dispute['id']}/messages",
        json={"body": "I posted it, check the tagged tab."},
        headers=_headers(biz),
    )
    detail = client.get(f"/payments/disputes/{dispute['id']}", headers=_headers(biz)).json()
    assert detail["status"] == "awaiting_response"
    # The opener answering back is both sides having spoken.
    r = client.post(
        f"/payments/disputes/{dispute['id']}/messages",
        json={"body": "That is a different brand's post."},
        headers=_headers(inf),
    )
    assert r.json()["dispute_status"] == "awaiting_admin"


def test_the_thread_stays_open_once_it_reaches_the_admin_queue(client):
    """An admin reading the case benefits from both sides still explaining."""
    biz, inf, _, escrow, dispute = _disputed(client)
    _age_window(client, dispute["id"])
    assert client.post("/payments/disputes/escalate", headers=ADMIN).json()["escalated"] == 1
    r = client.post(
        f"/payments/disputes/{dispute['id']}/messages",
        json={"body": "Adding the delivery receipt for the reviewer."},
        headers=_headers(biz),
    )
    assert r.status_code == 201
    assert r.json()["dispute_status"] == "awaiting_admin"


# --- Withdrawal ---------------------------------------------------------


def test_withdrawing_puts_the_escrow_back_to_held(client):
    biz, inf, _, escrow, dispute = _disputed(client)
    r = client.post(f"/payments/disputes/{dispute['id']}/withdraw", headers=_headers(inf))
    assert r.status_code == 200
    assert r.json()["status"] == "withdrawn"
    assert r.json()["escrow"]["status"] == "held"
    assert client.get(f"/payments/escrow/{escrow['id']}", headers=_headers(biz)).json()["status"] == "held"


def test_only_the_party_who_raised_it_may_withdraw(client):
    """The accused dismissing the accusation is not the claimant dropping it."""
    biz, inf, _, escrow, dispute = _disputed(client)
    assert client.post(
        f"/payments/disputes/{dispute['id']}/withdraw", headers=_headers(biz)
    ).status_code == 403


def test_withdrawing_lets_the_escrow_be_disputed_again(client):
    """Settling a first misunderstanding amicably must not spend the escrow's
    only claim. escrow_id was UNIQUE once, which meant a withdrawal left the
    brand with no recourse when the creator later failed to deliver — the two
    parties were punished for doing the right thing the first time."""
    biz, inf, _, escrow, first = _disputed(client)
    assert client.post(
        f"/payments/disputes/{first['id']}/withdraw", headers=_headers(inf)
    ).status_code == 200

    # The other side of the contract now raises a real one, on the same money.
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute",
        json=_body(reason="not_delivered"),
        headers=_headers(biz),
    )
    assert r.status_code == 201
    second = r.json()
    assert second["id"] != first["id"]
    assert second["status"] == "awaiting_response"
    assert second["opened_by_user_id"] == biz
    # The escrow is frozen again, and both rows survive: the withdrawn case is
    # a closed record, not something the new one overwrote.
    assert second["escrow"]["status"] == "disputed"
    mine = client.get("/payments/disputes/mine", headers=_headers(biz)).json()
    assert {d["id"] for d in mine} == {first["id"], second["id"]}
    assert {d["status"] for d in mine} == {"withdrawn", "awaiting_response"}


def test_the_open_dispute_still_blocks_a_second_one_after_a_withdrawal(client):
    """Reopening is allowed; running two live cases over the same money is
    not, and the second raise has to hit the same 409 as ever."""
    biz, inf, _, escrow, first = _disputed(client)
    client.post(f"/payments/disputes/{first['id']}/withdraw", headers=_headers(inf))
    assert client.post(
        f"/payments/escrow/{escrow['id']}/dispute", json=_body(), headers=_headers(biz)
    ).status_code == 201
    r = client.post(
        f"/payments/escrow/{escrow['id']}/dispute", json=_body(), headers=_headers(inf)
    )
    assert r.status_code == 409


def test_an_admin_settles_the_open_case_not_the_withdrawn_one(client):
    """With several rows per escrow, resolution has to name which dispute it
    is closing or it writes the split onto a case that ended weeks ago."""
    biz, inf, _, escrow, first = _disputed(client)
    client.post(f"/payments/disputes/{first['id']}/withdraw", headers=_headers(inf))
    second = client.post(
        f"/payments/escrow/{escrow['id']}/dispute", json=_body(), headers=_headers(biz)
    ).json()

    r = client.post(
        f"/payments/escrow/{escrow['id']}/resolve",
        json={"released_amount": 4000, "refunded_amount": 6000, "note": "Half delivered."},
        headers=ADMIN,
    )
    assert r.status_code == 200
    assert r.json()["id"] == second["id"]
    assert r.json()["released_amount"] == 4000
    # The withdrawn case is untouched: no split was written onto it.
    closed = client.get(f"/payments/disputes/{first['id']}", headers=ADMIN).json()
    assert closed["status"] == "withdrawn"
    assert closed["released_amount"] is None


def test_a_withdrawal_gives_back_review_time_the_freeze_ate(client):
    """A party should not lose their review window to a dispute that was
    withdrawn: a deadline that passed while frozen is pushed out by exactly
    how long the money was held."""
    biz, inf, _, escrow, dispute = _disputed(client)
    before = pay_models.utcnow().replace(year=2020)
    db = client.session_factory()
    e = db.query(pay_models.Escrow).filter(pay_models.Escrow.id == escrow["id"]).first()
    e.due_release_at = before
    db.commit()
    db.close()

    client.post(f"/payments/disputes/{dispute['id']}/withdraw", headers=_headers(inf))
    assert _escrow_row(client, escrow["id"]).due_release_at > before


def test_a_deadline_still_in_the_future_is_left_alone(client):
    """Nothing was taken from anybody, and moving it would quietly extend the
    creator's wait for their payout."""
    biz, inf, _, escrow, dispute = _disputed(client)
    before = _escrow_row(client, escrow["id"]).due_release_at
    client.post(f"/payments/disputes/{dispute['id']}/withdraw", headers=_headers(inf))
    assert _escrow_row(client, escrow["id"]).due_release_at == before


# --- The sweep ----------------------------------------------------------


def test_the_sweep_escalates_a_stale_dispute_and_leaves_a_fresh_one(client):
    biz, inf, _, escrow, stale = _disputed(client, suffix="1")
    _, _, _, _, fresh = _disputed(client, suffix="2")
    _age_window(client, stale["id"])

    assert client.post("/payments/disputes/escalate", headers=ADMIN).json()["escalated"] == 1
    assert client.get(f"/payments/disputes/{stale['id']}", headers=ADMIN).json()["status"] == "awaiting_admin"
    assert client.get(f"/payments/disputes/{fresh['id']}", headers=ADMIN).json()["status"] == "awaiting_response"
    # Both parties are told the window closed.
    assert any("window" in m for m in _notices(client, biz))


def test_the_sweep_needs_an_admin(client):
    assert client.post("/payments/disputes/escalate").status_code == 401


def test_escalating_twice_moves_nothing_the_second_time(client):
    _, _, _, _, dispute = _disputed(client)
    _age_window(client, dispute["id"])
    assert client.post("/payments/disputes/escalate", headers=ADMIN).json()["escalated"] == 1
    assert client.post("/payments/disputes/escalate", headers=ADMIN).json()["escalated"] == 0


# --- Reading the case ---------------------------------------------------


def test_the_detail_is_readable_by_both_parties_and_refused_to_a_stranger(client):
    """A dispute is two people's account of a private commercial agreement."""
    biz, inf, stranger, escrow, dispute = _disputed(client)
    client.post(
        f"/payments/disputes/{dispute['id']}/messages",
        json={"body": "Sending the receipt."},
        headers=_headers(biz),
    )
    for party in (biz, inf):
        r = client.get(f"/payments/disputes/{dispute['id']}", headers=_headers(party))
        assert r.status_code == 200
        assert len(r.json()["messages"]) == 1
        assert r.json()["escrow"]["amount"] == 10000
    assert client.get(
        f"/payments/disputes/{dispute['id']}", headers=_headers(stranger)
    ).status_code == 403


def test_mine_lists_only_the_callers_disputes(client):
    biz, inf, stranger, escrow, dispute = _disputed(client)
    mine = client.get("/payments/disputes/mine", headers=_headers(inf)).json()
    assert [d["id"] for d in mine] == [dispute["id"]]
    # The buyer is a party to the same one.
    assert [d["id"] for d in client.get("/payments/disputes/mine", headers=_headers(biz)).json()] == [dispute["id"]]
    assert client.get("/payments/disputes/mine", headers=_headers(stranger)).json() == []

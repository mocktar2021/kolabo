"""Handing in the work, and the brand's answer to it.

The escrow tests cover money moving. These cover the thing that was missing
underneath it: a record of WHAT was delivered, and an approval that is the same
act as the payment rather than a separate button that happened to be pressed
afterwards.

The clock cases at the bottom are the ones worth reading twice. Auto-release
used to be anchored to funding, so an escrow paid itself out seven days after
the brand funded it whether or not the creator had delivered anything at all.
It is now anchored to a submission, and the sweep only counts escrows with an
open one — which is what makes "nothing submitted" and "changes requested"
stop the clock instead of quietly paying.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.db import Base, get_db
from app.core.errors import AppError
from app.core.security import create_access_token
from app.core.urls import MAX_URL_CHARS
from app.modules.auth.models import User
from app.modules.campaigns import models as campaigns
from app.modules.contracts import models as contracts
from app.modules.deliverables import models as deliverables  # noqa: F401  (registers tables)
from app.modules.deliverables import service as deliverables_service
from app.modules.deliverables.router import router as deliverables_router
from app.modules.deliverables.schemas import SubmissionIn
from app.modules.notifications.models import Notification
from app.modules.payments import models as pay_models
from app.modules.payments import provider as provider_module
from app.modules.payments import service as pay_service
from app.modules.payments.router import router as payments_router
from app.modules.profiles import models as profiles

LINK = "https://instagram.com/p/abc123"


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
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
    app.include_router(deliverables_router, prefix="/deliverables")
    app.include_router(payments_router, prefix="/payments")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _user(db, phone, role):
    u = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x", country_code="BJ", role=role, is_verified=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _funded(client, amount=10000, suffix="1"):
    """A held escrow between a business and a creator, plus a bystander."""
    db = client.session_factory()
    try:
        biz = _user(db, f"+2299100{suffix}001", "business")
        inf = _user(db, f"+2299100{suffix}002", "influencer")
        stranger = _user(db, f"+2299100{suffix}003", "influencer")
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
    return biz_id, inf_id, stranger_id, contract_id, escrow


def _signed_unfunded(client, suffix="9"):
    """A signed contract with no escrow behind it yet."""
    db = client.session_factory()
    try:
        biz = _user(db, f"+2299100{suffix}001", "business")
        inf = _user(db, f"+2299100{suffix}002", "influencer")
        c = contracts.Contract(
            campaign_id=f"camp-{suffix}", proposal_id=f"prop-{suffix}", business_user_id=biz.id,
            influencer_user_id=inf.id, language="fr", body="body", rate_amount=5000,
            rate_currency="XOF", timeline_days=7, status=contracts.SIGNED,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        return biz.id, inf.id, c.id
    finally:
        db.close()


def _submit(client, actor, contract_id, **overrides):
    body = {"contract_id": contract_id, "link_url": LINK, "note": "Posted this morning."}
    body.update(overrides)
    return client.post("/deliverables", json=body, headers=_headers(actor))


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


def _notices(client, user_id, type="deliverable"):
    db = client.session_factory()
    try:
        return [
            {"message": n.message, "link": n.link, "params": n.params}
            for n in db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.type == type)
            .all()
        ]
    finally:
        db.close()


def _escrow_row(client, escrow_id):
    db = client.session_factory()
    try:
        return db.query(pay_models.Escrow).filter(pay_models.Escrow.id == escrow_id).first()
    finally:
        db.close()


def _age_release_deadline(client, escrow_id):
    """Force an escrow's release deadline into the past."""
    db = client.session_factory()
    try:
        e = db.query(pay_models.Escrow).filter(pay_models.Escrow.id == escrow_id).first()
        e.due_release_at = pay_models.utcnow().replace(year=2020)
        db.commit()
    finally:
        db.close()


# --- Submitting ---------------------------------------------------------


def test_submitting_work_records_it_and_tells_the_brand(client):
    """The record is the point: what was delivered, by whom, when — and a
    notification that deep-links to the contract rather than to a list."""
    biz, inf, _, cid, escrow = _funded(client)
    image = _media(client, inf)
    r = _submit(client, inf, cid, media_ids=[image])
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "submitted"
    assert body["link_url"] == LINK
    assert body["submitted_by_user_id"] == inf
    assert body["attachments"] == [f"/profiles/media/{image}"]
    assert body["reviewed_at"] is None

    told = _notices(client, biz)
    assert len(told) == 1
    assert told[0]["link"] == f"/contracts/{cid}"
    # No Campaign row behind this fixture's campaign_id, so the generic body
    # key is the honest one. The titled variant is the same call with a title.
    assert told[0]["params"] == {"key": "deliverable_submitted_generic"}
    # The creator is not notified about their own act.
    assert _notices(client, inf) == []


def test_submitting_starts_the_review_window(client):
    """The clock used to start at FUNDING, which meant the brand's review
    window ran before there was anything to review. It starts here now, and it
    is shorter than the funding-anchored deadline it replaces."""
    biz, inf, _, cid, escrow = _funded(client)
    funded_deadline = _escrow_row(client, escrow["id"]).due_release_at
    assert _submit(client, inf, cid).status_code == 201
    reviewed_deadline = _escrow_row(client, escrow["id"]).due_release_at
    assert reviewed_deadline != funded_deadline
    assert settings.review_window_days < settings.auto_release_days
    assert reviewed_deadline < funded_deadline


def test_only_the_creator_can_submit(client):
    """The brand is the buyer, not the supplier. 403 rather than 400: they are
    a party, they simply have no standing to deliver."""
    biz, inf, stranger, cid, escrow = _funded(client)
    assert _submit(client, biz, cid).status_code == 403
    assert _submit(client, stranger, cid).status_code == 403


def test_a_submission_pointing_at_nothing_is_refused(client):
    """The brand's next action on it releases money. An empty one is not a
    submission."""
    _, inf, _, cid, _ = _funded(client)
    r = _submit(client, inf, cid, link_url=None, note="   ", media_ids=[])
    assert r.status_code == 400


def test_work_cannot_be_submitted_before_the_brand_funds(client):
    """Delivering into an unfunded contract is the creator doing the work
    before the money reaches the provider — the position escrow exists to keep
    them out of."""
    _, inf, cid = _signed_unfunded(client)
    assert _submit(client, inf, cid).status_code == 400


def test_someone_elses_file_cannot_be_attached(client):
    """Attaching a file you do not own would show a private image to the other
    party and to any admin who later reads the case."""
    _, inf, stranger, cid, _ = _funded(client)
    theirs = _media(client, stranger)
    assert _submit(client, inf, cid, media_ids=[theirs]).status_code == 403
    # Nothing was written.
    assert client.get(f"/deliverables?contract_id={cid}", headers=_headers(inf)).json() == []


def test_a_second_submission_while_one_is_open_is_a_conflict(client):
    """Two unanswered hand-ins would give the brand two things to approve and
    no way to say which one it paid for."""
    _, inf, _, cid, _ = _funded(client)
    assert _submit(client, inf, cid).status_code == 201
    assert _submit(client, inf, cid).status_code == 409


# --- The link, which is the field somebody else's browser follows -------
#
# link_url was a bare string: stripped, stored, and rendered as a live anchor
# by both clients. So a creator could store `javascript:...` and wait for the
# brand to click it, on the contract page, where that brand is signed in and
# one button away from releasing this escrow. That is what separates this
# field from `note`, which is only ever read. app/core/urls.py holds the rule
# and the argument for it; these are the cases at this end of it.


def test_a_link_a_browser_would_run_is_refused_and_nothing_is_written(client):
    """Refused rather than blanked. A submission stored with the link silently
    removed would leave the creator believing they sent something they did
    not, which is the same objection contact_guard makes to redacting."""
    _, inf, _, cid, _ = _funded(client)
    assert _submit(client, inf, cid, link_url="javascript:alert(1)").status_code == 400
    assert client.get(f"/deliverables?contract_id={cid}", headers=_headers(inf)).json() == []
    # And the door is still open for the same creator to send a real one.
    assert _submit(client, inf, cid).status_code == 201


def test_a_link_nobody_typed_is_refused_by_length(client):
    """Measured before it is parsed, so a pasted blob costs a len() rather
    than a parse."""
    _, inf, _, cid, _ = _funded(client)
    giant = "https://example.com/" + ("a" * 3000)
    assert len(giant) > MAX_URL_CHARS
    assert _submit(client, inf, cid, link_url=giant).status_code == 400
    assert client.get(f"/deliverables?contract_id={cid}", headers=_headers(inf)).json() == []


def test_the_link_refusals_name_themselves(client):
    """The status is what a client acts on; the CODE is what it translates.

    Read at the service rather than off the response, because the app this
    file builds does not register the AppError handler (the same note the D2
    gate below carries), so `code` never reaches the body here. These two
    names are the contract with errorMessages.ts and are worth asserting by
    name rather than by status alone.
    """
    _, inf, _, cid, _ = _funded(client)
    db = client.session_factory()
    try:
        with pytest.raises(AppError) as refused:
            deliverables_service.submit(
                db, inf, SubmissionIn(contract_id=cid, link_url="javascript:alert(1)")
            )
        assert refused.value.code == "deliverable_link_invalid"
        assert refused.value.status_code == 400

        with pytest.raises(AppError) as too_long:
            deliverables_service.submit(
                db,
                inf,
                SubmissionIn(contract_id=cid, link_url="https://example.com/" + ("a" * 3000)),
            )
        assert too_long.value.code == "deliverable_link_too_long"
        assert too_long.value.status_code == 400
        # The ceiling travels as a number, so the French sentence can put it
        # where French puts it instead of baking a 2048 into two strings.
        assert too_long.value.values == {"max": MAX_URL_CHARS}
    finally:
        db.close()


def test_a_link_pasted_without_a_scheme_is_stored_with_one(client):
    """The commonest real input. A creator copies what the app showed them,
    which has no https:// on the front, and refusing that would teach them
    nothing except that the field is fussy. What is STORED is what the guard
    parsed, because that is the string a browser will follow."""
    _, inf, _, cid, _ = _funded(client)
    r = _submit(client, inf, cid, link_url="instagram.com/p/abc")
    assert r.status_code == 201
    assert r.json()["link_url"] == "https://instagram.com/p/abc"


def test_a_submission_with_only_a_bad_link_is_not_called_empty(client):
    """Two rules could refuse this and only one of them is useful. "A
    submission needs a link or a file" would send a creator who DID paste a
    link looking for a file to attach; the link refusal tells them the truth."""
    _, inf, _, cid, _ = _funded(client)
    db = client.session_factory()
    try:
        with pytest.raises(AppError) as refused:
            deliverables_service.submit(
                db, inf, SubmissionIn(contract_id=cid, link_url="file:///etc/passwd")
            )
        assert refused.value.code == "deliverable_link_invalid"
    finally:
        db.close()


# --- Approving ----------------------------------------------------------


def test_approving_releases_the_escrow_in_the_same_act(client):
    """There is no state in which the work is accepted and the money is not on
    its way."""
    biz, inf, _, cid, escrow = _funded(client)
    sub = _submit(client, inf, cid).json()
    r = client.post(f"/deliverables/{sub['id']}/approve", headers=_headers(biz))
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert r.json()["reviewed_by_user_id"] == biz

    settled = client.get(f"/payments/escrow/{escrow['id']}", headers=_headers(biz)).json()
    assert settled["status"] == "released"
    # Commission came off through the one definition of it.
    assert settled["commission_amount"] == 10000 * settings.commission_bps // 10000
    # The release path notified both sides; no duplicate "approved" notice.
    assert len(_notices(client, inf, type="payment")) >= 1
    assert len(_notices(client, biz, type="payment")) >= 1


def test_approving_the_last_hand_in_finishes_the_campaign(client):
    """Approval releases the escrow, and the release is what finishes the brief
    behind it — through the same hook the standalone confirm-delivery button
    and the sweep use, called after the commit rather than beside it.

    The campaign row is written here because the contracts in this file only
    ever name one by id. Its absence everywhere else is the point: the hook is
    silent about a brief that was never written rather than turning an approved
    deliverable into a 500."""
    biz, inf, _, cid, escrow = _funded(client)
    db = client.session_factory()
    try:
        db.add(campaigns.Campaign(
            id="camp-1", business_user_id=biz, title="Launch push", budget_amount=500000,
            budget_currency="XOF",
            deliverables=[{"platform": "instagram", "type": "post", "quantity": 1}],
            status=campaigns.PUBLISHED,
        ))
        db.commit()
    finally:
        db.close()

    sub = _submit(client, inf, cid).json()
    assert client.post(f"/deliverables/{sub['id']}/approve", headers=_headers(biz)).status_code == 200

    db = client.session_factory()
    try:
        assert db.query(campaigns.Campaign).filter(
            campaigns.Campaign.id == "camp-1"
        ).first().status == campaigns.COMPLETED
    finally:
        db.close()


def test_only_the_business_can_review(client):
    biz, inf, stranger, cid, escrow = _funded(client)
    sub = _submit(client, inf, cid).json()
    assert client.post(f"/deliverables/{sub['id']}/approve", headers=_headers(inf)).status_code == 403
    assert client.post(
        f"/deliverables/{sub['id']}/approve", headers=_headers(stranger)
    ).status_code == 403
    assert client.post(
        f"/deliverables/{sub['id']}/request-changes",
        json={"note": "Wrong handle."},
        headers=_headers(inf),
    ).status_code == 403
    # And the money did not move.
    assert client.get(f"/payments/escrow/{escrow['id']}", headers=_headers(biz)).json()["status"] == "held"


def test_a_submission_cannot_be_answered_twice(client):
    """The first answer released the money; a second would try to release it
    again."""
    biz, inf, _, cid, escrow = _funded(client)
    sub = _submit(client, inf, cid).json()
    assert client.post(f"/deliverables/{sub['id']}/approve", headers=_headers(biz)).status_code == 200
    assert client.post(f"/deliverables/{sub['id']}/approve", headers=_headers(biz)).status_code == 400


# --- Requesting changes -------------------------------------------------


def test_requesting_changes_keeps_the_money_held_and_reopens_the_door(client):
    """"Do it again" is not a dispute: nobody is accused of anything and the
    escrow does not freeze. The creator submits again as a new attempt."""
    biz, inf, _, cid, escrow = _funded(client)
    first = _submit(client, inf, cid).json()
    r = client.post(
        f"/deliverables/{first['id']}/request-changes",
        json={"note": "Posted to the wrong handle — please repost from @brand."},
        headers=_headers(biz),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "changes_requested"
    assert "wrong handle" in r.json()["review_note"]
    assert client.get(f"/payments/escrow/{escrow['id']}", headers=_headers(biz)).json()["status"] == "held"

    told = _notices(client, inf)
    assert [n["params"]["key"] for n in told] == ["deliverable_changes_requested"]

    # The closed attempt no longer blocks a new one.
    second = _submit(client, inf, cid)
    assert second.status_code == 201
    assert second.json()["id"] != first["id"]
    # Both rows survive: the history is what an admin would read.
    history = client.get(f"/deliverables?contract_id={cid}", headers=_headers(biz)).json()
    assert [h["status"] for h in history] == ["submitted", "changes_requested"]


def test_requesting_changes_needs_a_reason(client):
    """"Rejected" with no reason comes back the same and is the fastest route
    to the dispute this path exists to avoid."""
    biz, inf, _, cid, _ = _funded(client)
    sub = _submit(client, inf, cid).json()
    r = client.post(
        f"/deliverables/{sub['id']}/request-changes", json={"note": "   "}, headers=_headers(biz)
    )
    assert r.status_code == 400


# --- Withdrawing --------------------------------------------------------


def test_the_creator_can_withdraw_an_unanswered_submission(client):
    """For the creator who posted the wrong link and should not have to wait
    for a rejection to fix it."""
    biz, inf, _, cid, _ = _funded(client)
    sub = _submit(client, inf, cid).json()
    assert client.post(
        f"/deliverables/{sub['id']}/withdraw", headers=_headers(biz)
    ).status_code == 403
    r = client.post(f"/deliverables/{sub['id']}/withdraw", headers=_headers(inf))
    assert r.status_code == 200
    assert r.json()["status"] == "withdrawn"
    # And the door is open again.
    assert _submit(client, inf, cid).status_code == 201


# --- Reading ------------------------------------------------------------


def test_a_third_party_cannot_read_the_history(client):
    _, inf, stranger, cid, _ = _funded(client)
    _submit(client, inf, cid)
    assert client.get(
        f"/deliverables?contract_id={cid}", headers=_headers(stranger)
    ).status_code == 403


# --- The auto-release sweep --------------------------------------------


def test_the_sweep_ignores_an_escrow_with_nothing_submitted(client, admin_headers):
    """THE HOLE THIS PR CLOSES. A funded contract nobody delivered on used to
    pay itself out once the funding-anchored deadline passed."""
    biz, inf, _, cid, escrow = _funded(client)
    _age_release_deadline(client, escrow["id"])
    assert client.post("/payments/escrow/auto-release", headers=admin_headers).json()["released"] == 0
    assert _escrow_row(client, escrow["id"]).status == pay_models.HELD


def test_the_sweep_releases_work_the_brand_never_reviewed(client, admin_headers):
    """A creator who delivered is not held hostage by a brand that never
    clicks anything."""
    biz, inf, _, cid, escrow = _funded(client)
    _submit(client, inf, cid)
    _age_release_deadline(client, escrow["id"])
    assert client.post("/payments/escrow/auto-release", headers=admin_headers).json()["released"] == 1
    assert _escrow_row(client, escrow["id"]).status == pay_models.RELEASED


def test_the_sweep_stops_for_work_the_brand_sent_back(client, admin_headers):
    """Work the brand rejected must not quietly auto-pay while the creator is
    redoing it."""
    biz, inf, _, cid, escrow = _funded(client)
    sub = _submit(client, inf, cid).json()
    client.post(
        f"/deliverables/{sub['id']}/request-changes",
        json={"note": "Please reshoot in landscape."},
        headers=_headers(biz),
    )
    _age_release_deadline(client, escrow["id"])
    assert client.post("/payments/escrow/auto-release", headers=admin_headers).json()["released"] == 0
    assert _escrow_row(client, escrow["id"]).status == pay_models.HELD

    # Resubmitting opens a fresh window, and the sweep counts it again.
    _submit(client, inf, cid)
    _age_release_deadline(client, escrow["id"])
    assert client.post("/payments/escrow/auto-release", headers=admin_headers).json()["released"] == 1


def test_the_sweep_stops_for_a_withdrawn_submission(client, admin_headers):
    """Nothing is in front of the brand to review."""
    biz, inf, _, cid, escrow = _funded(client)
    sub = _submit(client, inf, cid).json()
    client.post(f"/deliverables/{sub['id']}/withdraw", headers=_headers(inf))
    _age_release_deadline(client, escrow["id"])
    assert client.post("/payments/escrow/auto-release", headers=admin_headers).json()["released"] == 0
    assert _escrow_row(client, escrow["id"]).status == pay_models.HELD


# --- The standalone confirm-delivery button (Deliverables D2) -----------
#
# POST /payments/escrow/{id}/release used to release the money and record
# nothing about what it paid for, so escrow state and deliverable state could
# diverge. It is now the same act as approving the open submission, reached
# from the money side.


def test_standalone_release_approves_the_open_submission(client):
    """Confirming delivery from the escrow side closes the open hand-in as
    approved and releases the money in one step: the two states cannot diverge."""
    biz, inf, _, cid, escrow = _funded(client)
    sub = _submit(client, inf, cid).json()
    r = client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz))
    assert r.status_code == 200
    assert r.json()["status"] == "released"
    # The open attempt is now approved, by the business, without a second click.
    history = client.get(f"/deliverables?contract_id={cid}", headers=_headers(biz)).json()
    assert [h["status"] for h in history] == ["approved"]
    assert history[0]["id"] == sub["id"]
    assert history[0]["reviewed_by_user_id"] == biz
    # Both sides were told by the release path (escrow_released_*).
    assert len(_notices(client, inf, type="payment")) >= 1
    assert len(_notices(client, biz, type="payment")) >= 1
    # The only deliverable-type notice the brand got was the submission itself —
    # the release path does not add a second "approved" one.
    assert [n["params"]["key"] for n in _notices(client, biz)] == ["deliverable_submitted_generic"]


def test_standalone_release_is_refused_with_nothing_submitted(client):
    """A funded escrow nobody has delivered against cannot be released by the
    button any more: there is nothing to confirm. It waits for the creator, or
    resolves through auto-release, non-delivery or a dispute."""
    biz, inf, _, cid, escrow = _funded(client)
    r = client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz))
    # A 400 on a freshly funded, undisputed escrow is the D2 gate; the coded
    # refusal and its translations are guarded in test_error_codes.py /
    # errorMessages.test.ts. This app does not register the AppError handler.
    assert r.status_code == 400
    assert _escrow_row(client, escrow["id"]).status == pay_models.HELD


def test_standalone_release_is_refused_when_the_only_attempt_is_closed(client):
    """Changes-requested is not an open hand-in: the brand asked for a redo, so
    there is nothing in front of it to confirm until the creator resubmits."""
    biz, inf, _, cid, escrow = _funded(client)
    sub = _submit(client, inf, cid).json()
    client.post(
        f"/deliverables/{sub['id']}/request-changes",
        json={"note": "Please reshoot in landscape."},
        headers=_headers(biz),
    )
    r = client.post(f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz))
    assert r.status_code == 400
    assert _escrow_row(client, escrow["id"]).status == pay_models.HELD

    # Once the creator resubmits, the button works again and approves the new one.
    resub = _submit(client, inf, cid).json()
    assert client.post(
        f"/payments/escrow/{escrow['id']}/release", headers=_headers(biz)
    ).status_code == 200
    history = client.get(f"/deliverables?contract_id={cid}", headers=_headers(biz)).json()
    # Newest first: the approved resubmission, then the earlier changes_requested.
    assert [h["status"] for h in history] == ["approved", "changes_requested"]
    assert history[0]["id"] == resub["id"]

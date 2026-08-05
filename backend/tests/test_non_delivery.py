"""Money that nobody delivered against has to end somewhere.

Anchoring auto-release to a submission (see payments.service.run_due_auto_
releases) was right, and it left the opposite case with no ending at all: a
brand funds an escrow, the creator never submits anything, and the money sits
held forever with neither party told a thing. This file pins the way out.

The rules under test, in the order they matter:

  * the deadline is the creator's OWN promise — held_at + timeline_days;
  * the first pass WARNS and moves no money;
  * only after the grace period does the escrow refund, in full, with no
    commission taken;
  * ANY submission, in any status, takes the escrow out of this path for
    good — that is the boundary against the auto-release sweep, and against
    refunding a creator's work out from under them;
  * a disputed escrow is never touched.
"""
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.contracts import models as contracts
from app.modules.deliverables import models as deliverables
from app.modules.notifications import models as notifications
from app.modules.payments import models as pay_models
from app.modules.payments import provider as provider_module
from app.modules.payments import service as pay_service
from app.modules.payments.router import router as payments_router

TIMELINE_DAYS = 7


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
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

    pay_service.payment_provider = provider_module.MockProvider()

    app = FastAPI()
    app.include_router(payments_router, prefix="/payments")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _headers(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _funded(client, amount=10000):
    """A signed contract with money held against it and nothing delivered."""
    db = client.session_factory()
    try:
        biz = User(phone="+22990000001", password_hash="x", country_code="BJ", role="business", is_verified=True)
        inf = User(phone="+22990000002", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add_all([biz, inf]); db.commit(); db.refresh(biz); db.refresh(inf)
        c = contracts.Contract(
            campaign_id="camp-1", proposal_id="prop-1", business_user_id=biz.id,
            influencer_user_id=inf.id, language="fr", body="body", rate_amount=amount,
            rate_currency="XOF", timeline_days=TIMELINE_DAYS, status=contracts.SIGNED,
        )
        db.add(c); db.commit(); db.refresh(c)
        biz_id, inf_id, contract_id = biz.id, inf.id, c.id
    finally:
        db.close()
    escrow = client.post(
        "/payments/escrow/fund", json={"contract_id": contract_id}, headers=_headers(biz_id)
    ).json()
    return biz_id, inf_id, contract_id, escrow["id"]


def _escrow(client, escrow_id):
    db = client.session_factory()
    try:
        return db.query(pay_models.Escrow).filter(pay_models.Escrow.id == escrow_id).first()
    finally:
        db.close()


def _submission(client, contract_id, creator_id, status=deliverables.SUBMITTED):
    db = client.session_factory()
    try:
        db.add(
            deliverables.DeliverableSubmission(
                contract_id=contract_id, submitted_by_user_id=creator_id,
                link_url="https://instagram.com/p/abc123", status=status,
            )
        )
        db.commit()
    finally:
        db.close()


def _run(client, days_after_funding):
    """The sweep, as if it were running `days_after_funding` days later.

    Time is passed in rather than the rows being aged, because the deadline is
    DERIVED from held_at and the contract — there is no due-date column to
    move. Passing `now` is also how the two existing sweeps are tested, and it
    keeps the arithmetic the test is asserting about visible in the test.
    """
    db = client.session_factory()
    try:
        held = db.query(pay_models.Escrow).first().held_at
        return pay_service.run_non_delivery_refunds(db, now=held + timedelta(days=days_after_funding))
    finally:
        db.close()


def _notice_keys(client, user_id):
    db = client.session_factory()
    try:
        rows = (
            db.query(notifications.Notification)
            .filter(notifications.Notification.user_id == user_id)
            .all()
        )
        return [r.params.get("key") for r in rows if r.params]
    finally:
        db.close()


# --------------------------------------------------------------------------
# The clock
# --------------------------------------------------------------------------


def test_nothing_happens_before_the_promised_delivery_date(client):
    """The creator has until the day they quoted. Not a day less."""
    _, _, _, escrow_id = _funded(client)
    assert _run(client, TIMELINE_DAYS - 1) == {"warned": 0, "refunded": 0}
    assert _escrow(client, escrow_id).status == pay_models.HELD
    assert _escrow(client, escrow_id).non_delivery_warned_at is None


def test_the_deadline_warns_and_moves_no_money(client):
    """A refund ends the job, so it is never the first thing that happens."""
    biz, inf, _, escrow_id = _funded(client)
    assert _run(client, TIMELINE_DAYS) == {"warned": 1, "refunded": 0}

    escrow = _escrow(client, escrow_id)
    assert escrow.status == pay_models.HELD
    assert escrow.non_delivery_warned_at is not None
    # BOTH parties, because the brand's money and the creator's job are both
    # about to end and neither of them chose it.
    assert "delivery_overdue_creator" in _notice_keys(client, inf)
    assert "delivery_overdue_brand" in _notice_keys(client, biz)


def test_the_warning_is_sent_once(client):
    """A sweep somebody runs twice a day must not send a daily reminder."""
    _, inf, _, _ = _funded(client)
    _run(client, TIMELINE_DAYS)
    assert _run(client, TIMELINE_DAYS + 1) == {"warned": 0, "refunded": 0}
    assert _notice_keys(client, inf).count("delivery_overdue_creator") == 1


def test_the_grace_period_is_time_somebody_could_have_used(client):
    """Warn and refund cannot both happen in one run, however late it runs.

    Otherwise a sweep first pressed a month after the deadline would warn and
    refund in the same breath, and the warning would be a receipt rather than
    a chance.
    """
    _, _, _, escrow_id = _funded(client)
    result = _run(client, TIMELINE_DAYS + settings.non_delivery_grace_days + 30)
    assert result == {"warned": 1, "refunded": 0}
    assert _escrow(client, escrow_id).status == pay_models.HELD


def test_the_escrow_refunds_after_the_grace_period(client):
    biz, inf, _, escrow_id = _funded(client)
    _run(client, TIMELINE_DAYS)
    result = _run(client, TIMELINE_DAYS + settings.non_delivery_grace_days)

    assert result == {"warned": 0, "refunded": 1}
    escrow = _escrow(client, escrow_id)
    assert escrow.status == pay_models.REFUNDED
    assert escrow.resolved_at is not None
    assert "escrow_refunded_brand" in _notice_keys(client, biz)
    assert "escrow_refunded_creator" in _notice_keys(client, inf)


def test_the_refund_is_the_whole_amount_and_takes_no_commission(client):
    """The fee is a share of a collaboration. There wasn't one."""
    biz, _, _, escrow_id = _funded(client, amount=10000)
    _run(client, TIMELINE_DAYS)
    _run(client, TIMELINE_DAYS + settings.non_delivery_grace_days)

    escrow = _escrow(client, escrow_id)
    assert escrow.commission_amount is None
    payouts = pay_service.payment_provider.payouts
    assert len(payouts) == 1
    # Paid back to the BUYER, in full.
    assert payouts[0][1] == 10000


def test_a_refunded_escrow_is_not_swept_again(client):
    _, _, _, _ = _funded(client)
    _run(client, TIMELINE_DAYS)
    _run(client, TIMELINE_DAYS + settings.non_delivery_grace_days)
    assert _run(client, TIMELINE_DAYS + 60) == {"warned": 0, "refunded": 0}


# --------------------------------------------------------------------------
# The boundary: anything submitted leaves this path for good
# --------------------------------------------------------------------------


def test_work_submitted_before_the_deadline_stops_the_clock(client):
    _, inf, contract_id, escrow_id = _funded(client)
    _submission(client, contract_id, inf)
    assert _run(client, TIMELINE_DAYS + 90) == {"warned": 0, "refunded": 0}
    assert _escrow(client, escrow_id).status == pay_models.HELD


def test_work_submitted_during_the_grace_period_stops_the_refund(client):
    """The warning did its job. Nothing else should happen."""
    _, inf, contract_id, escrow_id = _funded(client)
    _run(client, TIMELINE_DAYS)
    _submission(client, contract_id, inf)
    assert _run(client, TIMELINE_DAYS + settings.non_delivery_grace_days) == {"warned": 0, "refunded": 0}
    assert _escrow(client, escrow_id).status == pay_models.HELD


@pytest.mark.parametrize(
    "status",
    [deliverables.SUBMITTED, deliverables.APPROVED, deliverables.CHANGES_REQUESTED, deliverables.WITHDRAWN],
)
def test_any_submission_in_any_status_takes_it_out_of_this_path(client, status):
    """ANY submission, not just an open one — and the two ends of that are
    what the boundary is for.

    APPROVED and CHANGES_REQUESTED are obvious: work exists and the brand has
    answered it. WITHDRAWN is the one worth pinning. A creator who handed
    something in and pulled it back has still delivered into this contract,
    and refunding their escrow on a clock would take the job away from them
    for an act the product explicitly allows. What happens next is a dispute
    if it needs to be one, which is a judgement, not a sweep.
    """
    _, inf, contract_id, escrow_id = _funded(client)
    _submission(client, contract_id, inf, status=status)
    assert _run(client, TIMELINE_DAYS + settings.non_delivery_grace_days + 30) == {"warned": 0, "refunded": 0}
    assert _escrow(client, escrow_id).status == pay_models.HELD


def test_a_disputed_escrow_is_never_touched(client):
    """A frozen escrow belongs to the dispute path from the moment it freezes,
    and an admin's decision must not be pre-empted by a clock."""
    _, _, _, escrow_id = _funded(client)
    db = client.session_factory()
    try:
        e = db.query(pay_models.Escrow).filter(pay_models.Escrow.id == escrow_id).first()
        e.status = pay_models.DISPUTED
        db.commit()
    finally:
        db.close()
    assert _run(client, TIMELINE_DAYS + settings.non_delivery_grace_days + 30) == {"warned": 0, "refunded": 0}
    assert _escrow(client, escrow_id).status == pay_models.DISPUTED


def test_the_two_sweeps_never_touch_the_same_escrow(client):
    """The disjointness is by construction, and this is the proof.

    run_due_auto_releases takes escrows WITH an open submission; this one
    takes escrows with NO submission ever. Run both against both kinds and
    each does its own and nothing else — no ordering rule, no shared flag, no
    way for one to undo the other.
    """
    _, inf, contract_id, delivered = _funded(client)
    _submission(client, contract_id, inf)

    db = client.session_factory()
    try:
        # A second contract for the same pair, funded and never delivered.
        c = contracts.Contract(
            campaign_id="camp-2", proposal_id="prop-2",
            business_user_id=_escrow(client, delivered).business_user_id,
            influencer_user_id=inf, language="fr", body="body", rate_amount=10000,
            rate_currency="XOF", timeline_days=TIMELINE_DAYS, status=contracts.SIGNED,
        )
        db.add(c); db.commit(); db.refresh(c)
        second = c.id
        biz_id = _escrow(client, delivered).business_user_id
    finally:
        db.close()
    silent = client.post(
        "/payments/escrow/fund", json={"contract_id": second}, headers=_headers(biz_id)
    ).json()["id"]

    db = client.session_factory()
    try:
        held = db.query(pay_models.Escrow).first().held_at
        later = held + timedelta(days=TIMELINE_DAYS + settings.non_delivery_grace_days + 30)
        # Age the delivered one's review window so the release sweep will act.
        e = db.query(pay_models.Escrow).filter(pay_models.Escrow.id == delivered).first()
        e.due_release_at = held
        db.commit()
        pay_service.run_due_auto_releases(db, now=later)
        pay_service.run_non_delivery_refunds(db, now=later)
        pay_service.run_non_delivery_refunds(db, now=later + timedelta(days=90))
    finally:
        db.close()

    assert _escrow(client, delivered).status == pay_models.RELEASED
    assert _escrow(client, silent).status == pay_models.REFUNDED

"""The one-off backfill picks exactly the campaigns completion.py would.

WHY THIS FILE EXISTS AT ALL for a script that is meant to be deleted. Nothing
in the application imports scripts/backfill_campaign_completion.py, so a rename
inside campaigns.completion — of the predicate or of either read helper the
script leans on — would leave the script broken and this suite green. Its first
and only run is against a live database, where that surfaces as an
AttributeError part way through a job that has already committed some of its
work. Importing it here the same way the container does turns that into a test
failure instead.

What it pins is the seam, not the completion rule: campaigns.completion owns
the rule and has its own tests. This checks that the script asks it rather than
answering for itself, that the status filter keeps cancelled and draft briefs
out, and that the numbers the dry run prints are the numbers the apply run
writes — because those numbers are what somebody approves the run on.

Delete this with the script.
"""
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, import_all_models
from app.modules.campaigns import completion
from app.modules.campaigns import models
from app.modules.contracts import models as contracts
from app.modules.notifications.models import Notification
from app.modules.payments import models as payments

# The script is not part of the app package and is run as a file, not imported
# as a module — `python scripts/backfill_campaign_completion.py` puts scripts/
# on sys.path and nothing else. Loading it the same way is what makes this a
# test of the thing that will actually run, including its own path bootstrap.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import backfill_campaign_completion as backfill  # noqa: E402


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    # Every table, not just the campaign ones: completing a brief writes
    # notifications, and reads contracts and escrows.
    import_all_models()
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
    try:
        yield session
    finally:
        session.close()


def _campaign(db, title, status, is_direct=False):
    row = models.Campaign(
        business_user_id="biz-1", title=title, status=status, is_direct=is_direct
    )
    db.add(row)
    db.flush()
    return row


def _contract(db, campaign_id, escrow_status, status=contracts.SIGNED):
    """A contract, optionally with an escrow in a given state.

    User ids are strings that match no row, as in test_contract_lifecycle.py:
    SQLite does not enforce the foreign keys, and what is under test is which
    campaigns get chosen, not who the parties are. It also keeps notify() off
    the email path, since it only mails a user it can find.
    """
    row = contracts.Contract(
        campaign_id=campaign_id,
        proposal_id="prop-x",
        business_user_id="biz-1",
        influencer_user_id="inf-1",
        language="fr",
        body="body",
        rate_amount=10000,
        rate_currency="XOF",
        timeline_days=7,
        status=status,
    )
    db.add(row)
    db.flush()
    if escrow_status is not None:
        now = payments.utcnow()
        db.add(
            payments.Escrow(
                contract_id=row.id,
                campaign_id=campaign_id,
                business_user_id="biz-1",
                influencer_user_id="inf-1",
                amount=10000,
                currency="XOF",
                provider="mock",
                provider_fund_ref="ref",
                status=escrow_status,
                held_at=now,
                due_release_at=now,
            )
        )
    return row


def _chain(db, campaign_id, creator, versions=1, status=models.SUBMITTED):
    """A negotiation: older versions superseded, the live one carrying status."""
    for version in range(1, versions):
        db.add(
            models.Proposal(
                campaign_id=campaign_id, influencer_user_id=creator, version=version,
                rate_amount=1000, rate_currency="XOF", timeline_days=5,
                status=models.SUPERSEDED,
            )
        )
    db.add(
        models.Proposal(
            campaign_id=campaign_id, influencer_user_id=creator, version=versions,
            rate_amount=1000, rate_currency="XOF", timeline_days=5, status=status,
        )
    )


def _invite(db, campaign_id, creator, status=models.INVITED):
    db.add(
        models.CampaignInvitation(
            campaign_id=campaign_id, influencer_user_id=creator, status=status
        )
    )


@pytest.fixture()
def seeded(db):
    """Two finished briefs, and five that must not be touched.

    Shaped after the rows this was written for: one open brief with two
    released contracts and creators still waiting on it, and one direct order
    with a single released contract.
    """
    finished = _campaign(db, "Finished brief", models.PUBLISHED)
    _contract(db, finished.id, payments.RELEASED)
    _contract(db, finished.id, payments.RELEASED)
    # Four live chains, one of them several versions deep so that only the
    # live version counts, plus a chain that was already rejected.
    _chain(db, finished.id, "creator-1")
    _chain(db, finished.id, "creator-2", versions=3)
    _chain(db, finished.id, "creator-3")
    _chain(db, finished.id, "creator-4")
    _chain(db, finished.id, "creator-5", status=models.PROPOSAL_REJECTED)
    _invite(db, finished.id, "creator-6")
    _invite(db, finished.id, "creator-7")
    _invite(db, finished.id, "creator-8")
    # Answered, so not open, so not withdrawn.
    _invite(db, finished.id, "creator-9", status=models.ACCEPTED)

    order = _campaign(db, "Finished direct order", models.PUBLISHED, is_direct=True)
    _contract(db, order.id, payments.RELEASED)
    _invite(db, order.id, "creator-10")

    # Called off, and the predicate HOLDS for it — money settled under an
    # ended contract. Only the status filter keeps it out, which is the point.
    cancelled = _campaign(db, "Called off", models.CANCELLED)
    _contract(db, cancelled.id, payments.RELEASED)
    draft = _campaign(db, "Draft", models.DRAFT)
    _contract(db, draft.id, payments.RELEASED)

    # Money still held: a job running.
    running = _campaign(db, "Still running", models.PUBLISHED)
    _contract(db, running.id, payments.HELD)
    _chain(db, running.id, "creator-11")
    _invite(db, running.id, "creator-12")
    # One contract settled, one still held: not every contract has ended.
    half = _campaign(db, "Half finished", models.PUBLISHED)
    _contract(db, half.id, payments.RELEASED)
    _contract(db, half.id, payments.HELD)
    # A deal that fell through before anyone funded it. An ended contract, no
    # money ending — an open brief, not a finished one.
    abandoned = _campaign(db, "Fell through", models.PUBLISHED)
    _contract(db, abandoned.id, None, status=contracts.CANCELLED)

    db.commit()
    return {
        "finished": finished.id, "order": order.id, "cancelled": cancelled.id,
        "draft": draft.id, "running": running.id, "half": half.id,
        "abandoned": abandoned.id,
    }


def _counts(db):
    return {
        "completed": db.query(models.Campaign)
        .filter(models.Campaign.status == models.COMPLETED).count(),
        "rejected": db.query(models.Proposal)
        .filter(models.Proposal.status == models.PROPOSAL_REJECTED).count(),
        "withdrawn": db.query(models.CampaignInvitation)
        .filter(models.CampaignInvitation.status == models.WITHDRAWN).count(),
        "notifications": db.query(Notification).count(),
    }


def _surveys(db):
    return [backfill.survey(db, campaign_id) for campaign_id in backfill.published_ids(db)]


def test_the_script_asks_completion_rather_than_deciding_for_itself(db, seeded):
    """Every campaign it surveys gets the same answer completion.py gives.

    The assertion is deliberately against the predicate itself rather than
    against a list of expected ids: if the rule changes, this must follow it
    rather than pin the old behaviour.
    """
    surveys = _surveys(db)
    assert surveys
    for item in surveys:
        assert item.completed == completion.campaign_is_completed(db, item.id)
    chosen = {item.id for item in surveys if item.completed}
    assert chosen == {seeded["finished"], seeded["order"]}


def test_a_cancelled_brief_is_never_a_candidate(db, seeded):
    """Cancelled satisfies the predicate and must still be left alone.

    #123 kept cancelled distinct from completed on purpose — called off is not
    finished — so the status filter, not the rule, is what protects it.
    """
    assert completion.campaign_is_completed(db, seeded["cancelled"]) is True
    published = backfill.published_ids(db)
    assert seeded["cancelled"] not in published
    assert seeded["draft"] not in published


def test_a_dry_run_writes_nothing(db, seeded):
    before = _counts(db)
    assert backfill.run(db, apply=False) == 0
    db.expire_all()
    assert _counts(db) == before
    assert before["completed"] == 0


def test_apply_writes_exactly_what_it_reported(db, seeded):
    """The printed blast radius is the one somebody approves the run on."""
    candidates = [item for item in _surveys(db) if item.completed]
    chains = sum(item.live_chains for item in candidates)
    invitations = sum(item.open_invitations for item in candidates)
    notifications = sum(item.notifications for item in candidates)
    assert (chains, invitations, notifications) == (4, 4, 4)

    assert backfill.run(db, apply=True) == 0

    db.expire_all()
    after = _counts(db)
    assert after["completed"] == len(candidates)
    # One chain in the seed was already rejected before the run, so the
    # difference is what this closed rather than the total.
    assert after["rejected"] == chains + 1
    assert after["withdrawn"] == invitations
    assert after["notifications"] == notifications
    assert {n.type for n in db.query(Notification).all()} == {"proposal_closed"}
    # The brief that is still running keeps its live chain and its invitation.
    running = backfill.survey(db, seeded["running"])
    assert (running.live_chains, running.open_invitations) == (1, 1)


def test_a_second_apply_finds_nothing(db, seeded):
    assert backfill.run(db, apply=True) == 0
    db.expire_all()
    settled = _counts(db)

    assert backfill.run(db, apply=True) == 0
    db.expire_all()
    assert _counts(db) == settled
    assert [item for item in _surveys(db) if item.completed] == []

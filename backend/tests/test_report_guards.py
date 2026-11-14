"""The three things create_report did not check, and now does.

WHAT WAS WRONG. The endpoint validated the shape of a report and nothing about
its substance: the target type and the reason code had to be known values, and
that was all. So a report could name a target that did not exist, which
produced an open admin case pointing at nothing; it could name the reporter
themselves, which produced a case no moderator can act on; and there was no
ceiling at all, so one account could fill the queue faster than anybody could
read it.

Each of those costs a person's attention rather than a row in a table, which
is why they are worth refusing rather than tolerating. Reporting is the only
signal this platform gets about behaviour that never touches a contract, and a
queue nobody can keep up with is a signal nobody reads.

THE ORDER OF THE CHECKS IS ASSERTED, not just their existence. Each refusal is
reachable on strictly less information than the one after it, and two tests
here exist only to pin that down: an over quota caller gets 429 whatever they
send, and an unknown target type is refused before anything is read. An order
that drifted would turn one of these refusals into something only some callers
could learn, which is a disclosure nobody chose.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, import_all_models
from app.core.errors import AppError
from app.modules.auth.models import User
from app.modules.campaigns import models as cmodels
from app.modules.messaging.models import Message
from app.modules.trust_safety import models as tmodels
from app.modules.trust_safety import service as trust_safety_service


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    import_all_models()
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
    try:
        yield session
    finally:
        session.close()


def _user(db, suffix, role="business"):
    user = User(
        phone=f"+2299007{suffix}",
        email=f"rp{suffix}@kolabo.test",
        password_hash="x",
        country_code="BJ",
        role=role,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user.id


def _campaign(db, business_user_id):
    campaign = cmodels.Campaign(
        business_user_id=business_user_id,
        title="A brief",
        budget_amount=100000,
        budget_currency="XOF",
        deliverables=[{"platform": "instagram", "type": "post", "quantity": 1}],
        deadline=None,
        status=cmodels.PUBLISHED,
        is_direct=False,
        is_open=True,
        target_categories=[],
        target_countries=[],
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def _message(db, campaign_id, sender, recipient):
    message = Message(
        campaign_id=campaign_id,
        sender_user_id=sender,
        recipient_user_id=recipient,
        body="Hello",
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def _report(db, reporter, target_type, target_id, reason="spam"):
    return trust_safety_service.create_report(db, reporter, target_type, target_id, reason, None)


def _refusal(excinfo):
    return excinfo.value.status_code, excinfo.value.code


# ---- the control: reporting still works, for all three target types ----

def test_a_report_about_another_account_is_created(db):
    reporter, target = _user(db, "30001"), _user(db, "30002")
    report = _report(db, reporter, "user", target)
    assert report["status"] == tmodels.OPEN
    assert report["target_id"] == target


def test_a_report_about_a_real_campaign_is_created(db):
    reporter, owner = _user(db, "30011"), _user(db, "30012")
    campaign = _campaign(db, owner)
    assert _report(db, reporter, "campaign", campaign.id)["target_id"] == campaign.id


def test_a_report_about_a_real_message_is_created(db):
    reporter, other = _user(db, "30021"), _user(db, "30022")
    campaign = _campaign(db, other)
    message = _message(db, campaign.id, other, reporter)
    assert _report(db, reporter, "message", message.id)["target_id"] == message.id


# ---- reporting yourself ----

def test_you_cannot_report_yourself(db):
    """A misclick at worst and queue noise at best: a case naming the person
    who filed it is one no moderator can act on."""
    reporter = _user(db, "30101")
    with pytest.raises(AppError) as excinfo:
        _report(db, reporter, "user", reporter)
    assert _refusal(excinfo) == (400, "report_self")


def test_nothing_is_written_when_you_report_yourself(db):
    reporter = _user(db, "30111")
    with pytest.raises(AppError):
        _report(db, reporter, "user", reporter)
    assert db.query(tmodels.Report).count() == 0


def test_the_self_check_does_not_catch_somebody_else(db):
    """The control for the two above: the same call about a different account
    goes through, so the refusal is about identity and not about user targets
    in general."""
    reporter, target = _user(db, "30121"), _user(db, "30122")
    assert _report(db, reporter, "user", target)["target_id"] == target


# ---- a target that is not there ----

def test_reporting_an_account_that_does_not_exist_is_refused(db):
    reporter = _user(db, "30201")
    with pytest.raises(AppError) as excinfo:
        _report(db, reporter, "user", "no-such-user")
    assert _refusal(excinfo) == (404, "report_target_not_found")


def test_reporting_a_campaign_that_does_not_exist_is_refused(db):
    reporter = _user(db, "30211")
    with pytest.raises(AppError) as excinfo:
        _report(db, reporter, "campaign", "no-such-campaign")
    assert _refusal(excinfo) == (404, "report_target_not_found")


def test_reporting_a_message_that_does_not_exist_is_refused(db):
    reporter = _user(db, "30221")
    with pytest.raises(AppError) as excinfo:
        _report(db, reporter, "message", "no-such-message")
    assert _refusal(excinfo) == (404, "report_target_not_found")


def test_all_three_target_types_are_covered_by_the_existence_check(db):
    """TARGET_TYPES is derived from the model map rather than written beside
    it, so a fourth reportable thing cannot be accepted by the validator and
    then skip this check because nobody added it. This asserts the two have
    not drifted apart, which is the failure that shipped the first time."""
    assert set(trust_safety_service.TARGET_TYPES) == set(trust_safety_service._TARGET_MODELS)


def test_the_same_code_answers_for_every_missing_target(db):
    """One code and one sentence for all three, because the sentence says
    "item" rather than naming a type: "user" and "campaign" are database
    values, and keying the message on one would put an English word in the
    middle of a French sentence."""
    reporter = _user(db, "30231")
    codes = set()
    for target_type in ("user", "campaign", "message"):
        with pytest.raises(AppError) as excinfo:
            _report(db, reporter, target_type, "nothing-here")
        codes.add(excinfo.value.code)
    assert codes == {"report_target_not_found"}


# ---- the ceiling ----

def test_the_eleventh_report_in_an_hour_is_refused(db):
    reporter, target = _user(db, "30301"), _user(db, "30302")
    for _ in range(trust_safety_service.REPORTS_PER_WINDOW):
        _report(db, reporter, "user", target)

    with pytest.raises(AppError) as excinfo:
        _report(db, reporter, "user", target)
    assert _refusal(excinfo) == (429, "report_rate_limited")


def test_the_report_at_the_ceiling_still_goes_through(db):
    """An off by one here is the difference between a limit of ten and a limit
    of nine, and nobody would notice which it was from the refusal alone."""
    reporter, target = _user(db, "30311"), _user(db, "30312")
    for _ in range(trust_safety_service.REPORTS_PER_WINDOW - 1):
        _report(db, reporter, "user", target)
    assert _report(db, reporter, "user", target)["status"] == tmodels.OPEN


def test_reports_from_before_the_window_do_not_count(db):
    """The window slides. A person who reported ten accounts yesterday is not
    locked out today, which a plain lifetime counter would have done."""
    reporter, target = _user(db, "30321"), _user(db, "30322")
    stale = tmodels.utcnow() - (trust_safety_service.REPORT_WINDOW * 2)
    for index in range(trust_safety_service.REPORTS_PER_WINDOW + 5):
        db.add(
            tmodels.Report(
                reporter_user_id=reporter,
                target_type="user",
                target_id=f"old-{index}",
                reason_code="spam",
                details=None,
                status=tmodels.OPEN,
                created_at=stale,
            )
        )
    db.commit()

    assert _report(db, reporter, "user", target)["status"] == tmodels.OPEN


def test_the_ceiling_is_per_account(db):
    """PER ACCOUNT RATHER THAN PER IP, which is the opposite of
    app/core/ratelimit.py and deliberate: that module exists for endpoints a
    stranger reaches with no account, and these markets put whole cities
    behind one carrier NAT. An IP ceiling here would let one abuser silence
    the reporting tool for every other subscriber on their network."""
    noisy, quiet = _user(db, "30331"), _user(db, "30332")
    target = _user(db, "30333")
    for _ in range(trust_safety_service.REPORTS_PER_WINDOW):
        _report(db, noisy, "user", target)

    with pytest.raises(AppError):
        _report(db, noisy, "user", target)
    assert _report(db, quiet, "user", target)["status"] == tmodels.OPEN


# ---- the order, which is part of the contract ----

def test_an_over_quota_caller_gets_the_same_answer_whatever_they_send(db):
    """The ceiling is checked BEFORE the target is looked up, so the refusal
    does not depend on whether the target happens to exist. The other order
    would make report_target_not_found a thing only an over quota caller could
    learn, which is a strange property to have built."""
    reporter, target = _user(db, "30401"), _user(db, "30402")
    for _ in range(trust_safety_service.REPORTS_PER_WINDOW):
        _report(db, reporter, "user", target)

    with pytest.raises(AppError) as excinfo:
        _report(db, reporter, "user", "no-such-user")
    assert _refusal(excinfo) == (429, "report_rate_limited")


def test_the_shape_of_the_request_is_refused_before_anything_is_read(db):
    """An unknown target type or reason code is wrong on its own terms, so it
    is answered first and the ceiling is never consulted. Checked by sending
    both while over quota: the shape refusal still wins."""
    reporter, target = _user(db, "30411"), _user(db, "30412")
    for _ in range(trust_safety_service.REPORTS_PER_WINDOW):
        _report(db, reporter, "user", target)

    with pytest.raises(AppError) as excinfo:
        _report(db, reporter, "planet", target)
    assert _refusal(excinfo) == (400, "report_target_type_unknown")

    with pytest.raises(AppError) as excinfo:
        _report(db, reporter, "user", target, reason="because")
    assert _refusal(excinfo) == (400, "report_reason_unknown")


def test_reporting_yourself_is_refused_before_the_ceiling(db):
    """Self is about the caller and the body alone, so it comes above the
    ceiling: somebody who misclicks their own name should be told that, not
    told to come back in an hour."""
    reporter = _user(db, "30421")
    for index in range(trust_safety_service.REPORTS_PER_WINDOW):
        db.add(
            tmodels.Report(
                reporter_user_id=reporter,
                target_type="user",
                target_id=f"somebody-{index}",
                reason_code="spam",
                details=None,
                status=tmodels.OPEN,
            )
        )
    db.commit()

    with pytest.raises(AppError) as excinfo:
        _report(db, reporter, "user", reporter)
    assert _refusal(excinfo) == (400, "report_self")

"""Tests for the KOL-53 criterion 6 watcher.

The two that matter most are the _interesting() pair. Everything else here
checks a branch; those two check the contract between this job and the runner
that calls it, which is the thing that would have broken quietly: a healthy
pass returning a truthy age would promote every quiet sweep pass to INFO and
bury the pass that actually moved money. They assert against the real
sweeps._interesting rather than restating the rule in a comment.
"""
import logging
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.jobs import backup_freshness, sweeps

# NOT a .test address. email_validator refuses special-use domains, so
# normalized_email() answers None for them and admin_emails() drops the
# entry. Worth knowing: conftest.ADMIN_EMAIL is "conftest-admin@kolabo.test",
# which means that seeded admin could never be granted through ADMIN_EMAILS.
# It does not need to be, because it is seeded with is_admin directly, but a
# test that borrowed it here would have failed for a reason nothing stated.
ADMIN = "ops@example.com"
NOW = datetime(2026, 10, 28, 12, 0, 0, tzinfo=timezone.utc)


class Recorder:
    """A Sender that keeps what it was handed instead of posting it."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, target: str, type: str, message: str) -> None:
        self.sent.append({"target": target, "type": type, "message": message})


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """No leaked rate-limit state and no inherited environment between tests."""
    backup_freshness.reset_alert_state()
    for name in ("BACKUP_DIR", "BACKUP_MAX_AGE_HOURS", "BACKUP_ALERT_INTERVAL_HOURS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(settings, "admin_emails", ADMIN, raising=False)
    yield
    backup_freshness.reset_alert_state()


@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    directory = tmp_path / "backups"
    directory.mkdir()
    monkeypatch.setenv("BACKUP_DIR", str(directory))
    return directory


def write_marker(directory, when: datetime) -> None:
    """Write exactly what deploy/backup.sh writes: date -u +%Y-%m-%dT%H:%M:%SZ."""
    (directory / "last-success").write_text(when.strftime("%Y-%m-%dT%H:%M:%SZ"))


# --------------------------------------------------------------------------
# The contract with the runner
# --------------------------------------------------------------------------


def test_the_job_is_registered_in_the_runner():
    names = [name for name, _ in sweeps.JOBS]
    assert "backup_freshness" in names
    registered = dict(sweeps.JOBS)["backup_freshness"]
    assert registered is backup_freshness.check_backup_freshness


def test_a_healthy_result_leaves_the_pass_quiet(backup_dir):
    write_marker(backup_dir, NOW - timedelta(hours=3))
    result = backup_freshness.check_backup_freshness(now=NOW, sender=Recorder())
    # The whole reason the healthy return is {} and not the age.
    assert not sweeps._interesting({"backup_freshness": result})


def test_a_stale_result_makes_the_pass_interesting(backup_dir):
    write_marker(backup_dir, NOW - timedelta(hours=50))
    result = backup_freshness.check_backup_freshness(now=NOW, sender=Recorder())
    assert sweeps._interesting({"backup_freshness": result})


def test_a_barely_stale_result_is_still_truthy(backup_dir, monkeypatch):
    """An age that rounds toward zero must not come back falsy."""
    monkeypatch.setenv("BACKUP_MAX_AGE_HOURS", "1")
    write_marker(backup_dir, NOW - timedelta(hours=1, minutes=1))
    result = backup_freshness.check_backup_freshness(now=NOW, sender=Recorder())
    assert result
    assert sweeps._interesting({"backup_freshness": result})


def test_the_job_accepts_a_positional_session_it_ignores(backup_dir):
    """sweeps.run_once calls job(db). It must not care what db is."""
    write_marker(backup_dir, NOW - timedelta(hours=3))
    assert backup_freshness.check_backup_freshness(object(), now=NOW, sender=Recorder()) == {}


# --------------------------------------------------------------------------
# Branches
# --------------------------------------------------------------------------


def test_fresh_backup_sends_nothing(backup_dir):
    write_marker(backup_dir, NOW - timedelta(hours=3))
    sender = Recorder()
    assert backup_freshness.check_backup_freshness(now=NOW, sender=sender) == {}
    assert sender.sent == []


def test_stale_backup_logs_an_error_and_emails_the_admins(backup_dir, caplog):
    write_marker(backup_dir, NOW - timedelta(hours=50))
    sender = Recorder()
    with caplog.at_level(logging.ERROR, logger="kolabo.sweeps.backup"):
        result = backup_freshness.check_backup_freshness(now=NOW, sender=sender)

    assert result == {"stale_hours": 50}
    assert any("BACKUP STALE" in r.getMessage() for r in caplog.records)
    assert [m["target"] for m in sender.sent] == [ADMIN]
    assert sender.sent[0]["type"] == "backup_stale"
    # The first line becomes the mail subject, so it has to carry the point.
    first_line = sender.sent[0]["message"].splitlines()[0]
    assert "50 hours ago" in first_line


def test_a_mounted_directory_with_no_marker_means_never(backup_dir, caplog):
    sender = Recorder()
    with caplog.at_level(logging.ERROR, logger="kolabo.sweeps.backup"):
        result = backup_freshness.check_backup_freshness(now=NOW, sender=sender)

    assert result == {"never": 1}
    assert any("BACKUP NEVER" in r.getMessage() for r in caplog.records)
    assert len(sender.sent) == 1


def test_an_absent_directory_is_not_a_failure(tmp_path, monkeypatch, caplog):
    """A laptop on the dev compose file has no mount. That is not an alarm."""
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "nothing-here"))
    sender = Recorder()
    with caplog.at_level(logging.WARNING, logger="kolabo.sweeps.backup"):
        assert backup_freshness.check_backup_freshness(now=NOW, sender=sender) == {}
    assert sender.sent == []
    assert caplog.records == []


def test_a_marker_that_is_not_a_timestamp_is_reported(backup_dir):
    (backup_dir / "last-success").write_text("not a date at all\n")
    sender = Recorder()
    result = backup_freshness.check_backup_freshness(now=NOW, sender=sender)
    assert result == {"unreadable": 1}
    assert len(sender.sent) == 1


def test_an_empty_marker_is_reported(backup_dir):
    (backup_dir / "last-success").write_text("")
    sender = Recorder()
    assert backup_freshness.check_backup_freshness(now=NOW, sender=sender) == {"unreadable": 1}
    assert len(sender.sent) == 1


def test_a_marker_in_the_future_warns_but_does_not_alarm(backup_dir, caplog):
    write_marker(backup_dir, NOW + timedelta(hours=5))
    sender = Recorder()
    with caplog.at_level(logging.WARNING, logger="kolabo.sweeps.backup"):
        assert backup_freshness.check_backup_freshness(now=NOW, sender=sender) == {}
    assert sender.sent == []
    assert any("in the future" in r.getMessage() for r in caplog.records)


# --------------------------------------------------------------------------
# The rate limit, which is what keeps this out of a mailbox 288 times a day
# --------------------------------------------------------------------------


def test_a_second_stale_pass_does_not_send_a_second_email(backup_dir, caplog):
    write_marker(backup_dir, NOW - timedelta(hours=50))
    sender = Recorder()

    with caplog.at_level(logging.ERROR, logger="kolabo.sweeps.backup"):
        backup_freshness.check_backup_freshness(now=NOW, sender=sender)
        backup_freshness.check_backup_freshness(now=NOW + timedelta(minutes=5), sender=sender)

    assert len(sender.sent) == 1
    # But the log still says it on every pass, which is the point of the split.
    assert len([r for r in caplog.records if "BACKUP STALE" in r.getMessage()]) == 2


def test_the_email_goes_out_again_after_the_interval(backup_dir):
    write_marker(backup_dir, NOW - timedelta(hours=50))
    sender = Recorder()
    backup_freshness.check_backup_freshness(now=NOW, sender=sender)
    backup_freshness.check_backup_freshness(now=NOW + timedelta(hours=25), sender=sender)
    assert len(sender.sent) == 2


def test_the_alert_interval_is_configurable(backup_dir, monkeypatch):
    monkeypatch.setenv("BACKUP_ALERT_INTERVAL_HOURS", "1")
    write_marker(backup_dir, NOW - timedelta(hours=50))
    sender = Recorder()
    backup_freshness.check_backup_freshness(now=NOW, sender=sender)
    backup_freshness.check_backup_freshness(now=NOW + timedelta(minutes=90), sender=sender)
    assert len(sender.sent) == 2


def test_a_zero_alert_interval_silences_the_email_but_not_the_log(backup_dir, caplog, monkeypatch):
    monkeypatch.setenv("BACKUP_ALERT_INTERVAL_HOURS", "0")
    write_marker(backup_dir, NOW - timedelta(hours=50))
    sender = Recorder()
    with caplog.at_level(logging.ERROR, logger="kolabo.sweeps.backup"):
        backup_freshness.check_backup_freshness(now=NOW, sender=sender)
    assert sender.sent == []
    assert any("BACKUP STALE" in r.getMessage() for r in caplog.records)


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


def test_the_threshold_is_configurable(backup_dir, monkeypatch):
    monkeypatch.setenv("BACKUP_MAX_AGE_HOURS", "72")
    write_marker(backup_dir, NOW - timedelta(hours=50))
    sender = Recorder()
    assert backup_freshness.check_backup_freshness(now=NOW, sender=sender) == {}
    assert sender.sent == []


def test_a_zero_threshold_switches_the_check_off(backup_dir, monkeypatch):
    monkeypatch.setenv("BACKUP_MAX_AGE_HOURS", "0")
    sender = Recorder()
    # No marker at all, which would otherwise be the loudest branch there is.
    assert backup_freshness.check_backup_freshness(now=NOW, sender=sender) == {}
    assert sender.sent == []


def test_a_nonsense_threshold_falls_back_loudly(backup_dir, caplog, monkeypatch):
    monkeypatch.setenv("BACKUP_MAX_AGE_HOURS", "thirty-six")
    write_marker(backup_dir, NOW - timedelta(hours=50))
    sender = Recorder()
    with caplog.at_level(logging.WARNING, logger="kolabo.sweeps.backup"):
        result = backup_freshness.check_backup_freshness(now=NOW, sender=sender)
    # Behaves as if unset, rather than as if switched off.
    assert result == {"stale_hours": 50}
    assert any("not a whole number" in r.getMessage() for r in caplog.records)


def test_no_admin_emails_still_logs_rather_than_crashing(backup_dir, caplog, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "", raising=False)
    write_marker(backup_dir, NOW - timedelta(hours=50))
    sender = Recorder()
    with caplog.at_level(logging.ERROR, logger="kolabo.sweeps.backup"):
        assert backup_freshness.check_backup_freshness(now=NOW, sender=sender)
    assert sender.sent == []
    assert any("reached nobody" in r.getMessage() for r in caplog.records)


def test_the_default_directory_matches_backup_sh(monkeypatch):
    """One setting, one meaning. backup.sh defaults to the same path."""
    monkeypatch.delenv("BACKUP_DIR", raising=False)
    assert str(backup_freshness.marker_path()) == "/var/backups/kolabo/last-success"


# --------------------------------------------------------------------------
# Parsing what backup.sh actually writes
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-10-28T02:17:00Z", datetime(2026, 10, 28, 2, 17, tzinfo=timezone.utc)),
        ("2026-10-28T02:17:00Z\n", datetime(2026, 10, 28, 2, 17, tzinfo=timezone.utc)),
        ("  2026-10-28T02:17:00z  ", datetime(2026, 10, 28, 2, 17, tzinfo=timezone.utc)),
        ("2026-10-28T02:17:00", datetime(2026, 10, 28, 2, 17, tzinfo=timezone.utc)),
        ("2026-10-28T04:17:00+02:00", datetime(2026, 10, 28, 2, 17, tzinfo=timezone.utc)),
    ],
)
def test_parse_marker_accepts_what_date_u_writes(raw, expected):
    assert backup_freshness.parse_marker(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "\n", "today", "2026-13-45T99:99:99Z", None])
def test_parse_marker_refuses_everything_else(raw):
    assert backup_freshness.parse_marker(raw) is None

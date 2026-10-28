"""Is the nightly backup still happening? KOL-53 criterion 6.

WHY THIS EXISTS. deploy/backup.sh dumps the database, verifies the dump and
uploads it off the box, and a systemd timer runs it nightly. All of that is only
as good as the assumption that the timer still fires. Scheduled backups do not
usually fail loudly. They fail as a unit somebody disabled, a symlink that broke
after a git pull with no daemon-reload, or a script that started exiting
non-zero into a journal nobody reads. Weeks later somebody needs a restore and
finds the newest dump is from last month. That is the failure this watches for,
and it is the one KOL-53 names: "a silent cron that stopped weeks ago is the
common way this fails".

WHAT IT READS. backup.sh writes BACKUP_DIR/last-success as its final act, and
only after the dump has passed every verification. So that file's timestamp
means "a verified dump completed", not "the script started". Reading one file is
the whole check, which is deliberate: a watcher with its own moving parts is a
second thing that can break quietly.

WHY IT LIVES IN THE SWEEPS CONTAINER rather than in a second systemd timer. A
watcher that shares a mechanism with the thing it watches is not a watcher: if
the timer system is what stopped, a watching timer stopped with it. The sweeps
container is a different process under a different supervisor with its own
restart policy, and it is already waking up every five minutes for reasons of
its own. That independence is the entire value.

WHAT "VISIBLE" MEANS HERE, stated honestly. There is no log aggregation and no
alerting on these boxes; deploy/README.md section 11 says so. So this does two
things. It logs at ERROR on every pass, which makes the failure detectable by
anyone who looks. And it emails ADMIN_EMAILS at most once a day, which makes it
visible without anyone looking. The email path swallows its own delivery
failures by design, see notifications/email.py, so a provider outage means the
alert exists only in the log. That is a real limit of today's stack rather than
something this module can fix, and it is written down here so nobody concludes
from silence that the backup is fine.

CONFIGURED WITH os.getenv, exactly like SWEEP_INTERVAL_SECONDS beside it,
rather than through core.config.settings. These are knobs for one container.
The API process has no business knowing how old a backup may be, and putting
them in settings would add three operational values to the surface every other
module imports.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.modules.auth.admins import admin_emails
from app.modules.notifications.email import Sender, default_email_sender

logger = logging.getLogger("kolabo.sweeps.backup")

# Must match deploy/backup.sh's own default, and the path the sweeps service
# mounts in docker-compose.prod.yml. All three read BACKUP_DIR from deploy/.env,
# and the mount deliberately uses the same path inside the container as outside
# so that one setting means one thing everywhere.
DEFAULT_BACKUP_DIR = "/var/backups/kolabo"
MARKER_NAME = "last-success"

# The timer fires once a night, so a healthy gap is about 24 hours. 36 gives a
# single missed run roughly half a day before it is called a problem, which is
# late enough not to cry over a slow night and early enough to hear about it the
# same day.
DEFAULT_MAX_AGE_HOURS = 36

# An ERROR line goes out every pass. An email does not, because a pass is five
# minutes and nobody needs 288 of these a day.
DEFAULT_ALERT_INTERVAL_HOURS = 24

# When the last alert email was attempted, for the rate limit above. Process
# state on purpose, with no row and no file behind it: this container is
# long-lived, and the cost of being wrong is one extra email after a restart.
# A table would mean a migration, and a file would mean somewhere writable,
# for a value whose only job is to stop a mailbox filling up.
_last_alert_at: datetime | None = None


def reset_alert_state() -> None:
    """Forget when the last alert was sent. For tests, and only for tests."""
    global _last_alert_at
    _last_alert_at = None


def _int_env(name: str, default: int) -> int:
    """Read an integer knob, and fall back loudly rather than silently.

    A typo in a number is the kind of thing that turns a check off without
    anybody meaning to, so an unparseable value says so and then behaves as if
    it had not been set. Zero and negatives are returned as given, because both
    callers treat "not positive" as "switched off" and that is a legitimate
    thing to want.
    """
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        logger.warning("%s is not a whole number (%r); using %s", name, raw, default)
        return default


def marker_path() -> Path:
    return Path(os.getenv("BACKUP_DIR") or DEFAULT_BACKUP_DIR) / MARKER_NAME


def parse_marker(raw: str) -> datetime | None:
    """Read what backup.sh wrote: date -u +%Y-%m-%dT%H:%M:%SZ.

    Tolerant of the trailing Z being absent and of an explicit offset, because
    the cost of being strict here is a false alarm about a backup that ran
    perfectly well. Anything with no timezone at all is read as UTC, which is
    what backup.sh writes and what a human editing the file by hand would mean.
    """
    text = (raw or "").strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1]
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _alert(kind: str, message: str, now: datetime, sender: Sender | None) -> None:
    """Say it in the log every time, and in a mailbox at most once a day."""
    global _last_alert_at

    logger.error("BACKUP %s: %s", kind.upper(), message)

    interval = _int_env("BACKUP_ALERT_INTERVAL_HOURS", DEFAULT_ALERT_INTERVAL_HOURS)
    if interval <= 0:
        return
    if _last_alert_at is not None and now - _last_alert_at < timedelta(hours=interval):
        return

    # Set before sending, not after. If a send raises despite email.py's own
    # swallowing, the next pass is five minutes away and a loop that retries a
    # throwing sender 288 times a day is worse than a missed alert.
    _last_alert_at = now

    targets = sorted(admin_emails())
    if not targets:
        logger.error(
            "ADMIN_EMAILS is empty, so that warning reached nobody. "
            "Set it in deploy/.env or this check can only talk to this log."
        )
        return

    active = sender if sender is not None else default_email_sender
    for target in targets:
        active.send(target, "backup_stale", message)
    logger.info("Backup warning emailed to %s admin address(es)", len(targets))


def check_backup_freshness(
    db=None,
    *,
    now: datetime | None = None,
    sender: Sender | None = None,
) -> dict:
    """One file, one comparison. Returns {} when there is nothing to say.

    `db` is accepted and never used. Every entry in sweeps.JOBS is called as
    job(db) so that adding a job stays one line in one list, and paying for an
    unused session every five minutes is a better trade than a second calling
    convention in the runner.

    THE RETURN VALUE HAS TO BE FALSY WHEN HEALTHY, and that is not cosmetic.
    sweeps._interesting() treats any truthy integer in a result dict as "this
    pass did something", so returning the age on a healthy pass would promote
    every quiet pass to INFO and bury the pass that actually moved money under
    288 a day. test_backup_freshness.py asserts this against the real
    _interesting rather than restating the rule.
    """
    now = now or datetime.now(timezone.utc)

    max_age_hours = _int_env("BACKUP_MAX_AGE_HOURS", DEFAULT_MAX_AGE_HOURS)
    if max_age_hours <= 0:
        logger.debug("BACKUP_MAX_AGE_HOURS is not positive; freshness check is off")
        return {}

    marker = marker_path()
    directory = marker.parent

    # NOT MOUNTED IS NOT A FAILURE. The backup directory is bind mounted into
    # this container by docker-compose.prod.yml only. A laptop running the
    # development compose file, or any box that never set this up, has no such
    # path, and shouting about a backup nobody asked for would be noise that
    # teaches an operator to ignore this logger. A box that DOES mount it and
    # has no marker is a different story, handled below.
    if not directory.is_dir():
        logger.debug("%s is not present here; backup freshness not checked", directory)
        return {}

    if not marker.exists():
        _alert(
            "never",
            f"No verified Kolabo backup has ever completed on this box. "
            f"{directory} is mounted but holds no {MARKER_NAME} file. "
            f"Check the timer with: systemctl list-timers kolabo-backup.timer "
            f"and see deploy/RESTORE.md section 3.2.",
            now,
            sender,
        )
        return {"never": 1}

    try:
        raw = marker.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        # Reported rather than raised. A traceback every five minutes says less
        # than one sentence naming the file and the reason.
        _alert("unreadable", f"Cannot read {marker}: {exc}", now, sender)
        return {"unreadable": 1}

    stamp = parse_marker(raw)
    if stamp is None:
        _alert(
            "unreadable",
            f"{marker} does not contain a timestamp this can read. "
            f"backup.sh writes one line of the form 2026-10-28T02:17:00Z.",
            now,
            sender,
        )
        return {"unreadable": 1}

    age = now - stamp
    if age < timedelta(0):
        # A marker in the future means a clock moved, not that a backup ran.
        # Treated as fresh on purpose: alerting here would turn one wrong clock
        # into a daily email about a backup that is very probably fine, and the
        # warning says enough for somebody to go and look.
        logger.warning(
            "%s is dated %s, which is in the future. Check the clock on this box "
            "with timedatectl. Treating the backup as fresh.",
            marker,
            stamp.isoformat(),
        )
        return {}

    age_hours = age.total_seconds() / 3600
    if age_hours > max_age_hours:
        _alert(
            "stale",
            f"The last verified Kolabo backup completed {age_hours:.0f} hours ago, "
            f"on {stamp.isoformat()}. Anything longer than {max_age_hours} hours "
            f"means the nightly job has stopped. Start with: "
            f"systemctl list-timers kolabo-backup.timer and "
            f"journalctl -u kolabo-backup.service -n 50.",
            now,
            sender,
        )
        # Rounded up so a check that just tripped never reports zero, which
        # would be falsy and therefore invisible to _interesting().
        return {"stale_hours": max(1, int(age_hours))}

    logger.debug("Last verified backup was %.1f hours ago", age_hours)
    return {}

"""The jobs that move money on a clock.

WHY THIS MODULE EXISTS. Four things in this codebase have to happen on time and
had no clock behind them — only an admin-authenticated HTTP endpoint somebody
had to remember to call:

    run_due_auto_releases     pay a creator whose review window closed in silence
    run_non_delivery_refunds  warn, then refund, a contract nobody delivered on
    escalate_stale_disputes   move a dispute nobody answered into the admin queue
    run_pending_payouts       RETRY A PAYOUT THAT FAILED

The last one is the one that makes this urgent. payments/payouts.py is built so
that a network failure cannot fail a release: the escrow releases, the creator
is owed the money, and a Payout row is left FAILED for a sweep to retry. With no
sweep, "for a sweep to retry" is a promise nothing keeps, and the creator stays
owed forever with no error anywhere to notice. The design only works if
something runs this.

WHY IN-PROCESS RATHER THAN cron + curl. Those endpoints are admin-authenticated,
so a cron would need a long-lived admin bearer token sitting in a crontab or an
env file — a credential that can also resolve disputes and read every case file,
created solely so a timer can call four functions. Calling the service functions
directly needs no token at all, because it never goes through the API.

WHY ITS OWN CONTAINER rather than a thread in the API process. A sweep that
wedges — a gateway call with no timeout, a lock held on a big table — must not
take request handling down with it, and its logs are much easier to read alone.

FAILURE POLICY: every sweep is wrapped, and one blowing up neither stops the
others in that pass nor kills the loop. A crashed sweeps container is silent
money not moving, which is the exact failure this module exists to prevent, so
it is built to keep running through bad passes and say so loudly instead.
"""
import logging
import os
import signal
import sys
import time

from app.core.db import SessionLocal, import_all_models
from app.modules.payments import disputes, payouts
from app.modules.payments import service as payments_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("kolabo.sweeps")

DEFAULT_INTERVAL_SECONDS = 300

# Name -> callable(db). Adding a job is one line here.
#
# NOT INCLUDED, deliberately: the campaigns order-expiry job behind
# POST /campaigns/orders/expire. It belongs in this list, but its service
# function was not verified when this was written and a guessed import would
# crash the container on boot — taking the four money sweeps down with it to
# add a fifth. Add it here once the callable is confirmed.
JOBS = (
    ("auto_release", payments_service.run_due_auto_releases),
    ("non_delivery_refunds", payments_service.run_non_delivery_refunds),
    ("escalate_disputes", disputes.escalate_stale_disputes),
    ("pending_payouts", payouts.run_pending_payouts),
)

_running = True


def _stop(signum, _frame):
    """Finish the pass in flight, then exit. NEVER mid-sweep.

    `docker compose down` sends SIGTERM. Dying instantly in the middle of a
    payout pass would leave the gateway called and our row unwritten — the one
    state that is genuinely hard to reconcile, because only the gateway knows
    the money moved. The loop checks this flag between passes.
    """
    global _running
    logger.info("Received signal %s; finishing the current pass then exiting", signum)
    _running = False


def run_once() -> dict:
    """One pass over every job. Returns what each did, for the log.

    A SESSION PER JOB, not one for the whole pass. These functions commit, and
    a failure in the third job must not roll back or poison the session the
    first two already committed through. It also means a single wedged job
    cannot hold one connection open across all four.
    """
    results: dict[str, object] = {}
    for name, job in JOBS:
        db = SessionLocal()
        try:
            results[name] = job(db)
        except Exception:  # noqa: BLE001 - one bad job must not stop the rest
            logger.exception("Sweep %s failed", name)
            results[name] = "error"
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                logger.exception("Rollback failed after %s", name)
        finally:
            db.close()
    return results


def _interesting(results: dict) -> bool:
    """Did anything actually happen?

    Most passes do nothing at all, and logging four zeroes every five minutes
    buries the pass that mattered under a hundred that did not. So a quiet pass
    logs at DEBUG and a pass that moved something logs at INFO.
    """
    for value in results.values():
        if value == "error":
            return True
        if isinstance(value, int) and value:
            return True
        if isinstance(value, dict) and any(value.values()):
            return True
    return False


def main() -> int:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    interval = int(os.getenv("SWEEP_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS))
    # The API process normally does this at startup; this container never
    # imports app.main, so the model registry has to be populated here or
    # SQLAlchemy does not know about half the tables it is asked to query.
    import_all_models()

    logger.info("Sweeps starting: %s jobs every %ss", len(JOBS), interval)
    while _running:
        started = time.monotonic()
        results = run_once()
        if _interesting(results):
            logger.info("Sweep pass: %s", results)
        else:
            logger.debug("Sweep pass: nothing to do")

        # Sleep the REMAINDER of the interval, not the whole thing, so a slow
        # pass does not make the effective period drift outwards over days.
        # Sliced into one-second naps so a SIGTERM is honoured in about a
        # second rather than after five minutes.
        remaining = max(0.0, interval - (time.monotonic() - started))
        while _running and remaining > 0:
            nap = min(1.0, remaining)
            time.sleep(nap)
            remaining -= nap

    logger.info("Sweeps stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())

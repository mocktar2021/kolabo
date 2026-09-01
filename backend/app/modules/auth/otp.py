"""OTP and reset code delivery.

The SMS provider is not selected yet (see docs/ARCHITECTURE.md open items).
Delivery sits behind the Sender interface so a real provider (for example
Africa's Talking or Termii) can be dropped in later without touching auth logic.
The logging sender prints the code so local and pilot testing can proceed.
TODO: replace LoggingSender with a real SMS provider before production.
"""
import logging
import secrets
from typing import Protocol

from app.core.config import settings

_log = logging.getLogger("kolabo.auth.otp")

# HOW MANY WRONG GUESSES AN ACCOUNT'S LIVE CODES ABSORB BEFORE THEY ALL DIE.
#
# Six digits is a million values and the codes last ten minutes, which sounds
# safe until you notice nothing was counting. Before this constant existed a
# wrong guess neither incremented anything nor consumed the challenge, and
# there is no rate limiting anywhere in the application — main.py adds exactly
# one middleware and it is CORS. So a script could spend the full ten minutes
# of a code's life guessing it, in parallel, for free. The same machinery
# backs password reset, which makes it account takeover rather than merely a
# nuisance.
#
# Five rather than three: a real person mistypes a code read off a lock screen
# more often than you would like, and the cost of a sixth guess to an attacker
# facing a spent challenge is the same as the cost of the first.
MAX_ATTEMPTS = 5


class Sender(Protocol):
    def send(self, phone: str, message: str) -> None:
        ...


class LoggingSender:
    def send(self, phone: str, message: str) -> None:
        _log.info("send to %s: %s", phone, message)
        # In development, also print to stdout so the code is visible in the
        # container logs without querying the database. Uvicorn's default
        # logging does not surface app INFO logs, and this is never enabled in
        # production (guarded on env).
        if settings.env == "development":
            print(f"[DEV OTP] to {phone}: {message}", flush=True)


def generate_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def spend_attempt(live_codes: list, failed) -> bool:
    """Count one wrong guess against EVERY live code for the account.

    Returns True when the allowance is gone, in which case the caller must
    consume all of them.

    THE COUNT IS PER ACCOUNT, NOT PER ROW, and that is the whole subtlety.
    Both verification paths resolve a guess against whichever code is current
    — verify_otp takes the newest unconsumed challenge, confirm_password_reset
    scans the live tokens — so counting only the row that was tried would hand
    an attacker a fresh allowance each time an older code became current
    again. Three codes in flight, which the per-hour issuance caps positively
    allow, would mean three times the guesses. Charging every live row for one
    wrong guess is what makes MAX_ATTEMPTS mean what it says.

    `failed` is included even if the caller's live query somehow missed it, so
    a guess is never free.
    """
    charged = list(live_codes)
    if failed is not None and failed not in charged:
        charged.append(failed)
    for row in charged:
        row.attempts = (row.attempts or 0) + 1
    return any(row.attempts >= MAX_ATTEMPTS for row in charged)


default_sender: Sender = LoggingSender()

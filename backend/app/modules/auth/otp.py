"""OTP and reset code delivery.

No SMS provider is contracted yet. Delivery sits behind the Sender protocol so
one can be dropped in without touching auth logic, and the LoggingSender prints
the code so local and pilot testing can proceed.

WHAT A SEND ANSWERS, AND WHY IT HAS TO ANSWER. Until this module grew
SendResult, Sender.send returned None, both call sites committed the challenge
row and then sent, and whatever happened next was thrown away. A provider that
failed still left the client reading "code sent" for a code that never left the
server, and a provider that raised turned a registration whose row was already
committed into a 500. Both were cheap to fix against the logging sender and
would have been a debugging session against a live gateway, which is why the
shape is settled here, before a provider exists to fill it.

So every send comes back with a SendResult, `deliver` guarantees that even when
the provider raises, and the two call sites decide what an unsent code means
for the person waiting on it: registration refuses out loud, password reset
keeps its generic answer for the reason written beside it in account.py.

THE HOUSE SHAPES, REUSED RATHER THAN REINVENTED. CompositeSender is
profiles.enrichment.CompositeEnricher with a result instead of a dict: try
each in order, first success wins. RoutingSender is payments.gateways.registry
keyed by dialling prefix instead of by country code, because an SMS route,
its coverage and its price follow the number being dialled, not the country
somebody selected at signup. Neither is built by default, because there is
nothing to route between; build_default_sender is where that changes.
"""
import logging
import secrets
from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings

_log = logging.getLogger("kolabo.auth.otp")

# HOW MANY WRONG GUESSES AN ACCOUNT'S LIVE CODES ABSORB BEFORE THEY ALL DIE.
#
# Six digits is a million values and the codes last ten minutes, which sounds
# safe until you notice nothing was counting. Before this constant existed a
# wrong guess neither incremented anything nor consumed the challenge, and
# there is no rate limiting anywhere in the application (main.py adds exactly
# one middleware and it is CORS). So a script could spend the full ten minutes
# of a code's life guessing it, in parallel, for free. The same machinery
# backs password reset, which makes it account takeover rather than merely a
# nuisance.
#
# Five rather than three: a real person mistypes a code read off a lock screen
# more often than you would like, and the cost of a sixth guess to an attacker
# facing a spent challenge is the same as the cost of the first.
MAX_ATTEMPTS = 5


@dataclass(frozen=True)
class SendResult:
    """What became of one message.

    ok: the provider ACCEPTED the message. Accepted is the strongest claim an
    SMS API makes synchronously; arrival on the handset is reported later, if
    at all, by a delivery receipt nothing here consumes yet. A true value
    therefore means "it left us", not "they have it".
    provider: the name of the sender that answered, so a log line or a support
    ticket can say which one. For a chain it is the child that succeeded, or
    the chain itself when nothing did.
    error: the provider's own words when ok is False, and None otherwise.
    """

    ok: bool
    provider: str
    error: str | None = None


class Sender(Protocol):
    name: str

    def send(self, phone: str, message: str) -> SendResult: ...


class LoggingSender:
    """The stand-in for a provider: logs the message and reports success."""

    name = "logging"

    def send(self, phone: str, message: str) -> SendResult:
        _log.info("send to %s: %s", phone, message)
        # In development, also print to stdout so the code is visible in the
        # container logs without querying the database. Uvicorn's default
        # logging does not surface app INFO logs, and this is never enabled in
        # production (guarded on env).
        if settings.env == "development":
            print(f"[DEV OTP] to {phone}: {message}", flush=True)
        return SendResult(ok=True, provider=self.name)


def deliver(sender: Sender, phone: str, message: str) -> SendResult:
    """Send through `sender` and come back with a result, whatever happens.

    THE ONE PLACE A PROVIDER'S EXCEPTION IS CAUGHT. Every call site goes
    through here rather than calling sender.send directly, so a gateway that
    raises (a timeout, a 500 from the vendor, a malformed response, a bug in
    the adapter) becomes a SendResult the caller can act on instead of a 500
    on a request whose database row is already committed. The chain classes
    below go through it too, one child at a time, which is what lets a chain
    survive a child that raises rather than only one that says no.

    A sender that returns anything but a SendResult is reported as a failure,
    not tolerated as a success. The old protocol returned None and every
    caller ignored it; a provider adapter that forgot to return would look
    exactly like one that worked, which is the silent failure this whole
    change exists to end.

    The phone is logged and the message is not: the message carries the code.
    """
    name = getattr(sender, "name", type(sender).__name__)
    try:
        result = sender.send(phone, message)
    except Exception as exc:  # noqa: BLE001, deliberately every exception
        _log.exception("sender %s raised while sending to %s", name, phone)
        return SendResult(ok=False, provider=name, error=f"{type(exc).__name__}: {exc}")
    if not isinstance(result, SendResult):
        _log.error("sender %s returned %r instead of a SendResult", name, result)
        return SendResult(ok=False, provider=name, error="sender returned no SendResult")
    return result


class CompositeSender:
    """Tries each sender in order and answers with the first that accepts.

    The house shape for a fallback chain, taken from
    profiles.enrichment.CompositeEnricher: a list, a loop, first success wins.
    A child that raises is a child that failed (see deliver), so one bad
    adapter cannot take the chain down with it.

    The result names the child that succeeded, and when none did, the error
    is every child's error in order, so the log line for a total outage says
    what each provider said rather than only that all of them said no.
    """

    name = "composite"

    def __init__(self, senders: list[Sender]):
        self.senders = list(senders)

    def send(self, phone: str, message: str) -> SendResult:
        errors: list[str] = []
        for sender in self.senders:
            result = deliver(sender, phone, message)
            if result.ok:
                if errors:
                    # Worth a warning even on success: a primary that is
                    # failing is a bill and a latency somebody should know
                    # about before the secondary fails too.
                    _log.warning(
                        "sender %s accepted %s after: %s", result.provider, phone, "; ".join(errors)
                    )
                return result
            errors.append(f"{result.provider}: {result.error}")
        return SendResult(
            ok=False,
            provider=self.name,
            error="; ".join(errors) if errors else "no senders configured",
        )


class RoutingSender:
    """One sender per dialling prefix, with an optional default for the rest.

    payments.gateways.registry keyed by prefix rather than by country code,
    and for a reason the payments registry does not have: an SMS route is a
    property of the number being dialled. Coverage, price and sender-ID rules
    differ per operator and per country, one provider for all five launch
    markets is unlikely, and the number tells us where the message is going
    more reliably than the country somebody picked from a list at signup.

    Prefixes are the international form ("+229"). The longest matching prefix
    wins, so a route for one operator range can sit beside the route for its
    country. A number nothing matches goes to `default`, and with no default
    it is a refusal that names the prefix rather than a message sent nowhere.
    """

    name = "routing"

    def __init__(self, by_prefix: dict[str, Sender], default: Sender | None = None):
        self.by_prefix = dict(by_prefix)
        self.default = default

    def route(self, phone: str) -> Sender | None:
        best_prefix: str | None = None
        best_sender: Sender | None = None
        for prefix, sender in self.by_prefix.items():
            if phone.startswith(prefix) and (best_prefix is None or len(prefix) > len(best_prefix)):
                best_prefix, best_sender = prefix, sender
        return best_sender if best_sender is not None else self.default

    def send(self, phone: str, message: str) -> SendResult:
        sender = self.route(phone)
        if sender is None:
            return SendResult(
                ok=False,
                provider=self.name,
                error=f"no sender is configured for numbers starting {phone[:4]}",
            )
        return deliver(sender, phone, message)


def build_default_sender() -> Sender:
    """Wire up whatever this deployment has credentials for.

    Nothing, today: no SMS provider is contracted, so every deployment gets
    the LoggingSender. The same rule the payments registry and the enrichers
    follow, that an unconfigured provider is absent rather than present and
    broken, applies here the day one exists. Adding it is a class with a
    `name` and a `send`, and one line in this function. Adding a second for
    a market the first does not cover is a RoutingSender by prefix, with a
    CompositeSender as the default so every number has a fallback.
    """
    return LoggingSender()


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
    (verify_otp takes the newest unconsumed challenge, confirm_password_reset
    scans the live tokens), so counting only the row that was tried would hand
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


default_sender: Sender = build_default_sender()

"""OTP and reset code delivery.

THE CODE GOES TO A MAILBOX NOW, NOT TO A HANDSET. The email address is the
login identity, so the one place a six digit code can be sent that proves the
person asking is the person the account belongs to is that address. No SMS
provider was ever contracted, which is what made the move cheap: there was no
live channel to migrate off, only a LoggingSender standing in for one.

Delivery still sits behind the Sender protocol below, and the protocol is
deliberately unchanged in shape — one target, one message, one SendResult —
because what a code is sent OVER is not something auth logic should know. What
changed is the word: the parameter is `target`, and a target is an address.
The LoggingSender still prints the code so local and pilot testing can proceed
with no mail credentials at all.

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
each in order, first success wins. RoutingSender routed by dialling prefix and
is dead for this path now; it is kept, unbuilt, with its own note saying so.

WHAT IS IN THE MESSAGE, and why it is composed here. A code that arrives by
email needs a subject line as well as a body, and both of them need to be in
the reader's language: five of the seven configured countries default to
French. Both call sites need exactly the same treatment, so the templates live
here rather than being written twice and drifting. See verification_message.
"""
import logging
import secrets
from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings
from app.core.country_config import DEFAULT_LANGUAGE, default_language
from app.modules.notifications import email as email_module

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

    ok: the provider ACCEPTED the message. Accepted is the strongest claim a
    mail API makes synchronously; arrival in the mailbox is reported later, if
    at all, by a webhook nothing here consumes yet, and a spam folder is not
    reported at all. A true value therefore means "it left us", not "they have
    it".
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

    # `target` rather than `phone`, because it is an email address now. The
    # protocol stays two arguments wide on purpose: a sender's job is to put a
    # string somewhere a person will read it, and which kind of somewhere is
    # the deployment's business rather than auth's.
    def send(self, target: str, message: str) -> SendResult: ...


class LoggingSender:
    """The stand-in for a provider: logs the message and reports success."""

    name = "logging"

    def send(self, target: str, message: str) -> SendResult:
        # THIS LINE CARRIES THE CODE AND IS NOT GUARDED ON ANYTHING, which is
        # the point of a sender whose whole job is to stand in for a provider:
        # printing the message is how a code is read on a laptop with no mail
        # credentials. It is also why this class must never be the sender on a
        # production box, and why the comment below is about the print and not
        # about this. What keeps it off production is
        # deploy/checks/preflight-env.sh, which refuses to deploy with
        # ENV=production and no mail credentials, plus the ERROR that
        # build_default_sender logs if one ever starts anyway. Note that
        # deliver() below states the opposite rule for every OTHER sender,
        # "the target is logged and the message is not", and means it.
        _log.info("send to %s: %s", target, message)
        # THE PRINT, specifically, and only in development. The log line above
        # goes wherever the application log goes; this one puts the code on
        # stdout so it is visible in `docker compose logs` without querying
        # the database, because uvicorn's default logging does not surface app
        # INFO records. Guarded on env, so it really is never enabled in
        # production.
        if settings.env == "development":
            print(f"[DEV OTP] to {target}: {message}", flush=True)
        return SendResult(ok=True, provider=self.name)


def deliver(sender: Sender, target: str, message: str) -> SendResult:
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

    The target is logged and the message is not: the message carries the code.
    """
    name = getattr(sender, "name", type(sender).__name__)
    try:
        result = sender.send(target, message)
    except Exception as exc:  # noqa: BLE001, deliberately every exception
        _log.exception("sender %s raised while sending to %s", name, target)
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

    def send(self, target: str, message: str) -> SendResult:
        errors: list[str] = []
        for sender in self.senders:
            result = deliver(sender, target, message)
            if result.ok:
                if errors:
                    # Worth a warning even on success: a primary that is
                    # failing is a bill and a latency somebody should know
                    # about before the secondary fails too.
                    _log.warning(
                        "sender %s accepted %s after: %s",
                        result.provider,
                        target,
                        "; ".join(errors),
                    )
                return result
            errors.append(f"{result.provider}: {result.error}")
        return SendResult(
            ok=False,
            provider=self.name,
            error="; ".join(errors) if errors else "no senders configured",
        )


class RoutingSender:
    """One sender per dialling prefix. UNUSED, AND UNUSED UNTIL SMS COMES BACK.

    NOTHING BUILDS THIS AND NOTHING ROUTES THROUGH IT. It routes on the
    international dialling prefix of a phone number, and codes are sent to
    email addresses now, so every target this class could be handed is a
    string with no dialling prefix in it: `route` would match nothing, fall to
    `default`, and the whole apparatus would be an expensive way of calling one
    sender. It is live code in the sense that it imports and its tests pass;
    it is not live in the sense of being on any path a user reaches.

    It is kept rather than deleted because it is the shape the day an SMS
    channel returns, which is a real possibility in these markets rather than a
    hypothetical: prefix routing is how you get coverage across five countries
    when no single provider has it. Deleting it would mean rewriting it from
    memory later, and this note costs less than that.

    Read no further than that, though. In particular DO NOT read a RoutingSender
    in a stack trace or a config as evidence that messages are being routed by
    country, because nothing is.

    Prefixes are the international form ("+229"). The longest matching prefix
    wins, so a route for one operator range can sit beside the route for its
    country. A number nothing matches goes to `default`, and with no default
    it is a refusal that names the prefix rather than a message sent nowhere.
    """

    name = "routing"

    def __init__(self, by_prefix: dict[str, Sender], default: Sender | None = None):
        self.by_prefix = dict(by_prefix)
        self.default = default

    def route(self, target: str) -> Sender | None:
        best_prefix: str | None = None
        best_sender: Sender | None = None
        for prefix, sender in self.by_prefix.items():
            if target.startswith(prefix) and (
                best_prefix is None or len(prefix) > len(best_prefix)
            ):
                best_prefix, best_sender = prefix, sender
        return best_sender if best_sender is not None else self.default

    def send(self, target: str, message: str) -> SendResult:
        sender = self.route(target)
        if sender is None:
            return SendResult(
                ok=False,
                provider=self.name,
                error=f"no sender is configured for numbers starting {target[:4]}",
            )
        return deliver(sender, target, message)


class EmailSender:
    """Put the code in a mailbox, through the notifications mail provider.

    ONE PROVIDER FOR THE WHOLE PRODUCT, not two. notifications/email.py already
    holds an account with Resend, a verified from address and the decision about
    when a deployment counts as configured; a second mail client here would be a
    second set of credentials to rotate and a second thing to be misconfigured
    on a Friday. This class is an adapter and nothing more: it turns the
    notification Sender's shape into this module's.

    THE TYPE TOKEN IS "security" and is not a per-message decision. It is what
    notifications use for anything about credentials, and it is the honest
    label for a sign-in code. It travels no further than the provider's log
    line today.

    WHAT THIS CANNOT REPORT, and it matters enough to say out loud here rather
    than only in the module it comes from. notifications.email.Sender.send
    returns None and ResendSender swallows every HTTP failure by design, for
    the reason written beside it: its callers are mid-request with money
    moving. So a mail provider that REFUSES a message is invisible to this
    adapter and comes back as ok=True, and _issue_otp will tell the user their
    code is on its way. The provider that RAISES is still caught, by deliver,
    and still becomes a 503 that says so.

    That is a real hole and it is smaller than it looks: the loud failure modes
    (no credentials, a network that is down, a bug in the adapter) all raise.
    It closes properly the day that Protocol grows a result, which its own
    docstring already anticipates. Reported as ok rather than guessed at,
    because a sender that invented a failure would be worse than one that
    cannot see it.
    """

    name = "email"

    TYPE = "security"

    def __init__(self, mail: email_module.Sender):
        self.mail = mail

    def send(self, target: str, message: str) -> SendResult:
        self.mail.send(target, self.TYPE, message)
        return SendResult(ok=True, provider=self.name)


def build_default_sender() -> Sender:
    """Wire up whatever this deployment has credentials for.

    THE CONFIGURED-OR-NOT DECISION IS NOT MADE HERE. It is made once, in
    notifications.email.build_default_email_sender, which returns a real
    provider when it has both a key and a from address and the logging stand-in
    otherwise. Asking it and then looking at what came back keeps that rule in
    one place; restating the condition here would be a second copy to keep in
    step, and the copy that went stale would be the one that silently stopped
    sending.

    AN UNCONFIGURED DEPLOYMENT GETS THE LOGGING SENDER, exactly as before, and
    that is the whole point of the branch. A laptop and the test suite have no
    mail credentials, and they must keep printing the code to the log rather
    than acquiring a mail client that fails on every send. This module's own
    LoggingSender is returned rather than the notification one because it is
    the one that prints [DEV OTP], which is how anybody working locally reads a
    code without opening the database.
    """
    mail = email_module.build_default_email_sender()
    if isinstance(mail, email_module.LoggingEmailSender):
        # A PRODUCTION DEPLOYMENT MUST NEVER REACH THIS BRANCH, and if one
        # does it says so at ERROR rather than carrying on quietly. The
        # failure it would otherwise produce is silent in the worst way:
        # every registration answers "your code is on its way", the code goes
        # to the log instead of a mailbox, and no account can be verified,
        # which looks like a working signup until somebody tries to use one.
        #
        # LOGGED RATHER THAN RAISED, deliberately. app/core/config.py keeps
        # RESEND_API_KEY out of its production validator on the stated grounds
        # that a deployment without mail should not refuse to boot, and
        # overturning that is a decision for whoever owns the deployment
        # rather than a side effect of this function. So the refusal lives in
        # deploy/checks/preflight-env.sh, which runs before anything starts,
        # and this line is what catches a container started some other way.
        if settings.env == "production":
            _log.error(
                "ENV=production with no mail credentials: verification codes will be "
                "written to this log and reported to the user as sent, and no account "
                "can be verified. Set RESEND_API_KEY and MAIL_FROM in deploy/.env and "
                "restart. deploy/checks/preflight-env.sh refuses this, so something "
                "started without running it."
            )
        return LoggingSender()
    return EmailSender(mail)


# ---------------------------------------------------------------------------
# What the email actually says
# ---------------------------------------------------------------------------
#
# A SUBJECT AND A BODY, BOTH IN TWO LANGUAGES, and both composed here because
# registration and password reset need exactly the same treatment. Written
# twice they would drift, and the copy that drifted would be the reset one,
# which is the one somebody reads while already locked out.
#
# THE FIRST LINE IS THE SUBJECT. That is not a coincidence, it is the contract
# notifications/email.py already implements: _subject() there takes the first
# line of the message, strips control characters and caps it, which is why the
# blank line below matters and why no template may begin with the code. The
# subject then appears again as the opening of the body, which is normal and
# deliberate for a one line transactional email and is what that module's own
# docstring says about it.
#
# WHICH LANGUAGE, decided from the country on the account through
# country_config.default_language. Five of the seven configured countries
# default to French, so an English-only code is the wrong default for most of
# the people who will read one. It is a default rather than a preference
# because nothing on the users row records a chosen language yet; the day one
# exists, this is the single place that has to start reading it.
#
# NOTHING ELSE IS IN THESE MESSAGES. No marketing, no unsubscribe link, no
# tracking pixel, no HTML. A credential email that carries any of those is
# harder to tell from a phishing attempt, which is the one thing it must never
# be, and an unsubscribe link on a message somebody needs in order to sign in
# would be a footgun with a button on it.
#
# The plural "minutes" is hardcoded in both languages. Every TTL this system
# configures is comfortably above one, and a singular branch would be a line of
# grammar nobody will ever see run.

_VERIFICATION_TEMPLATES = {
    "en": (
        "Your Kolabo verification code\n"
        "\n"
        "Your Kolabo verification code is {code}.\n"
        "It expires in {minutes} minutes.\n"
        "If you did not try to create a Kolabo account, you can ignore this email."
    ),
    "fr": (
        "Votre code de vérification Kolabo\n"
        "\n"
        "Votre code de vérification Kolabo est {code}.\n"
        "Il expire dans {minutes} minutes.\n"
        "Si vous n'avez pas demandé la création d'un compte Kolabo, "
        "vous pouvez ignorer cet e-mail."
    ),
}

_PASSWORD_RESET_TEMPLATES = {
    "en": (
        "Your Kolabo password reset code\n"
        "\n"
        "Your Kolabo password reset code is {code}.\n"
        "It expires in {minutes} minutes.\n"
        "If you did not ask to reset your password, you can ignore this email "
        "and your password stays as it is."
    ),
    "fr": (
        "Votre code de réinitialisation Kolabo\n"
        "\n"
        "Votre code de réinitialisation de mot de passe Kolabo est {code}.\n"
        "Il expire dans {minutes} minutes.\n"
        "Si vous n'avez pas demandé cette réinitialisation, vous pouvez "
        "ignorer cet e-mail et votre mot de passe reste inchangé."
    ),
}


def _render(templates: dict[str, str], country_code: str | None, code: str, minutes: int) -> str:
    """Pick the language from the country, then fill in the two values.

    Falls back to DEFAULT_LANGUAGE rather than raising on a language token
    neither template has. default_language already answers "fr" or "en" for
    every configured country and falls back itself for an unknown one, so the
    only way to arrive here with something else is a COUNTRY_CONFIG entry that
    was edited wrongly — and the right behaviour then is a code somebody can
    still read, not a 500 on their signup.
    """
    language = default_language(country_code)
    template = templates.get(language) or templates[DEFAULT_LANGUAGE]
    return template.format(code=code, minutes=minutes)


def verification_message(country_code: str | None, code: str, minutes: int) -> str:
    """The registration email, subject on the first line. See the note above."""
    return _render(_VERIFICATION_TEMPLATES, country_code, code, minutes)


def password_reset_message(country_code: str | None, code: str, minutes: int) -> str:
    """The reset email, subject on the first line. See the note above."""
    return _render(_PASSWORD_RESET_TEMPLATES, country_code, code, minutes)


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

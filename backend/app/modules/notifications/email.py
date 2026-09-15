"""Notification delivery, and the provider that carries it.

Delivery sits behind the Sender interface so notification logic never has to
know which provider is holding a message, and so a deployment with no
credentials still works. Two implementations live here. LoggingEmailSender
records every delivery in an in memory outbox, which is what the pilot reads
and what the tests assert on. ResendSender posts to Resend's HTTP API, which is
the provider this project settled on (docs/ARCHITECTURE.md said the choice was
open; it is not open any more).

WHICH ONE A DEPLOYMENT GETS is build_default_email_sender's decision, and it
follows the rule the payments registry, the profile enrichers and the OTP
senders all follow: AN UNCONFIGURED PROVIDER IS ABSENT RATHER THAN PRESENT AND
BROKEN. A half-configured ResendSender would accept every send, fail every one
of them, and look from the outside exactly like a working install, which is the
expensive kind of silence. Both a key and a from address, or the logging sender.

THE TARGET IS STILL WHATEVER service.notify HANDS OVER, which today is
`user.email or user.phone` — so on this platform most targets are still phone
numbers, because the phone is the login identity and an email is optional. That
is deliberately untouched by this module: it can now HOLD and SEND to an
address, and which of the two a notification is addressed to is the identity
question, decided in the PR that flips it. Until then ResendSender declines a
target that is not an address rather than posting a phone number to a mail API
and collecting a rejection per notification.

WHAT A SEND CANNOT TELL ANYONE. Sender.send returns None, so a provider that
refuses a message has nowhere to report it except the log, and the caller
commits the notification row either way. That is a real gap and it is named
here rather than left to be discovered: auth/otp.py solved the same problem
with a SendResult, and the day an email failure has to change what a caller
does, this Protocol grows one too. It is not needed yet, because no caller
currently has a different answer available.
"""
import logging
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.emails import normalized_email

_log = logging.getLogger("kolabo.notifications.email")

# How long one send may wait before it is given up on. There is no queue and no
# retry anywhere in this application: notify() calls send() INSIDE THE HTTP
# REQUEST that raised the notification, so every second spent here is a second
# somebody watches a spinner after releasing an escrow. Ten is generous for a
# small JSON POST and short enough that a provider outage costs each request ten
# seconds rather than however long the client is willing to wait.
#
# An explicit number rather than httpx's default, which is five seconds for the
# whole operation and is a number nobody here chose.
TIMEOUT_SECONDS = 10.0

# The cap on the subject line built out of the message below.
MAX_SUBJECT_CHARS = 120

# For a notification with no prose in it at all. Not expected, and not worth a
# crash: an email with a dull subject beats an exception on the request that
# was releasing somebody's money.
DEFAULT_SUBJECT = "Kolabo"


class Sender(Protocol):
    def send(self, target: str, type: str, message: str) -> None:
        ...


class LoggingEmailSender:
    def __init__(self) -> None:
        self.outbox: list[dict] = []

    def send(self, target: str, type: str, message: str) -> None:
        _log.info("email to %s [%s]: %s", target, type, message)
        self.outbox.append({"target": target, "type": type, "message": message})


def _subject(message: str) -> str:
    """A subject line taken from the message, not invented beside it.

    notify() is called with one short sentence written for the reader ("Escrow
    released, your payout is on the way"), which is already a better subject
    line than anything this module could compose from the `type` token, and it
    means the subject cannot drift away from the body it belongs to. The same
    sentence appearing twice is normal for a one line transactional email.

    THE FIRST LINE ONLY, AND NO CONTROL CHARACTERS. A subject is a MAIL HEADER
    and a header ends at a newline, so a message carrying one would otherwise
    be an invitation to write a second header. No call site composes a message
    out of user input today, and the check costs a splitlines(), which is
    cheaper than needing to be sure of that forever.
    """
    body = message.strip() if message else ""
    if not body:
        return DEFAULT_SUBJECT
    line = body.splitlines()[0]
    line = "".join(ch for ch in line if ord(ch) >= 0x20 and ord(ch) != 0x7F).strip()
    return line[:MAX_SUBJECT_CHARS].strip() or DEFAULT_SUBJECT


class ResendSender:
    """Deliver through Resend's HTTP API.

    One POST, one JSON body, one bearer token, verified against Resend's own
    API reference rather than written from memory:
    https://resend.com/docs/api-reference/emails/send-email

    `to` is a list because the API takes one or many and a list is the shape
    that does not change when a second recipient ever appears. reply_to is sent
    only when there is one configured: an empty string is not a mailbox, and a
    provider is entitled to refuse the whole message over it.
    """

    name = "resend"

    API_URL = "https://api.resend.com/emails"

    def __init__(self) -> None:
        # Read once, at construction, because build_default_email_sender has
        # already decided this deployment is configured. Re-reading settings on
        # every send would let a half-edited environment change what happens
        # mid-process, which is not a behaviour anybody wants to debug.
        self.api_key = settings.resend_api_key
        self.mail_from = settings.mail_from
        self.reply_to = settings.mail_reply_to

    def send(self, target: str, type: str, message: str) -> None:
        if normalized_email(target) is None:
            # Not an address. service.notify addresses to `user.email or
            # user.phone`, so until the identity flips this is the ORDINARY
            # case rather than a fault: most accounts have no email on file and
            # their target is a phone number. Posting one to a mail API buys a
            # 422 and an ERROR line per notification, which would bury the
            # failures actually worth reading. Declined here, at debug level,
            # because it is the expected state of the world.
            _log.debug("no email on file for this notification [%s], nothing sent", type)
            return

        payload: dict = {
            "from": self.mail_from,
            "to": [target],
            "subject": _subject(message),
            # Plain text only. Every notification body in this system is one
            # sentence, an HTML part would be the same sentence in a wrapper,
            # and text is what survives every client, every locale and the
            # low-bandwidth connections these markets actually read mail on.
            "text": message,
        }
        if self.reply_to:
            payload["reply_to"] = self.reply_to

        try:
            response = httpx.post(
                self.API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # EVERY FAILURE IS SWALLOWED, and it has to be. The caller is
            # mid-request with a notification row already added and, at several
            # call sites, an escrow movement beside it; raising here would turn
            # a provider's bad minute into a 500 on a payment. So the message
            # is lost and the loss is logged loudly, which is the honest
            # version of what the Protocol can express today (see the note at
            # the top of this module). The target is logged and the body is
            # not: bodies carry amounts and counterparties.
            _log.error("email to %s [%s] not accepted by %s: %s", target, type, self.name, exc)


def build_default_email_sender() -> Sender:
    """Wire up whatever this deployment has credentials for.

    Both the key and the from address, or nothing. The same rule the payments
    registry and otp.build_default_sender follow, that an unconfigured provider
    is absent rather than present and broken: a ResendSender holding an empty
    key would accept every send and fail every one of them somewhere only the
    logs can see, and a deployment that never set RESEND_API_KEY would look
    identical to one whose key had been revoked.

    The from address counts as configuration and not as a default, deliberately.
    There is no address this code could invent that Resend would accept, because
    a from address has to sit on a domain that has been verified with them; a
    built-in fallback would be a sender that is configured, broken, and certain
    of itself.

    Nothing else is needed to add a second provider later: a class with a `name`
    and a `send`, and one line here.
    """
    if settings.resend_api_key and settings.mail_from:
        return ResendSender()
    return LoggingEmailSender()


default_email_sender: Sender = build_default_email_sender()

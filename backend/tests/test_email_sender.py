"""The email provider: which one a deployment gets, and what it puts on the wire.

Two things are worth pinning here and they are different in kind.

The first is the WIRING RULE, which this codebase applies everywhere and which
is the reason a deployment with no credentials still works: an unconfigured
provider is ABSENT rather than present and broken. Half a configuration is the
dangerous case, because a ResendSender holding an empty key accepts every send,
fails every one of them somewhere only the logs can see, and is indistinguishable
from a working install until somebody asks why nobody got their email.

The second is the REQUEST SHAPE, checked against Resend's own API reference
(https://resend.com/docs/api-reference/emails/send-email) rather than against
memory. httpx is stubbed: what is under test is what this module would send,
not whether the internet is up, and a test that really posted would be a test
that fails on a plane.

Nothing here asserts that a message arrived. Sender.send returns None and has
nowhere to say otherwise, which the module docstring names as the gap it is.
"""
import httpx
import pytest

from app.modules.notifications import email as email_module


@pytest.fixture()
def configured(monkeypatch):
    """A deployment with credentials, for the length of one test."""
    monkeypatch.setattr(email_module.settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(email_module.settings, "mail_from", "Kolabo <no-reply@kolabo.test>")
    monkeypatch.setattr(email_module.settings, "mail_reply_to", "")


@pytest.fixture()
def posted(monkeypatch):
    """Capture what would have gone to Resend, and answer 200."""
    calls = []

    def fake_post(url, *, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return httpx.Response(200, request=httpx.Request("POST", url), json={"id": "msg_1"})

    monkeypatch.setattr(email_module.httpx, "post", fake_post)
    return calls


# --------------------------------------------------------------------------
# Which sender a deployment gets
# --------------------------------------------------------------------------


def test_no_credentials_means_the_logging_sender(monkeypatch):
    monkeypatch.setattr(email_module.settings, "resend_api_key", "")
    monkeypatch.setattr(email_module.settings, "mail_from", "")
    assert isinstance(email_module.build_default_email_sender(), email_module.LoggingEmailSender)


def test_both_halves_of_the_configuration_or_neither(monkeypatch):
    """A key with no from address, or a from address with no key, is a
    deployment somebody half finished. It gets the logging sender, because the
    alternative is a provider that is certain of itself and broken."""
    monkeypatch.setattr(email_module.settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(email_module.settings, "mail_from", "")
    assert isinstance(email_module.build_default_email_sender(), email_module.LoggingEmailSender)

    monkeypatch.setattr(email_module.settings, "resend_api_key", "")
    monkeypatch.setattr(email_module.settings, "mail_from", "no-reply@kolabo.test")
    assert isinstance(email_module.build_default_email_sender(), email_module.LoggingEmailSender)


def test_a_configured_deployment_gets_resend(configured):
    sender = email_module.build_default_email_sender()
    assert isinstance(sender, email_module.ResendSender)
    assert sender.name == "resend"


def test_the_logging_sender_still_records_its_outbox():
    """The pilot and several tests read this list. Adding a provider beside it
    must not disturb it."""
    sender = email_module.LoggingEmailSender()
    sender.send("ama@example.com", "payment", "Escrow released")
    assert sender.outbox == [
        {"target": "ama@example.com", "type": "payment", "message": "Escrow released"}
    ]


# --------------------------------------------------------------------------
# What goes on the wire
# --------------------------------------------------------------------------


def test_the_request_is_the_shape_resend_documents(configured, posted):
    email_module.ResendSender().send("ama@example.com", "payment", "Escrow released.")

    assert len(posted) == 1
    call = posted[0]
    assert call["url"] == "https://api.resend.com/emails"
    assert call["headers"]["Authorization"] == "Bearer re_test_key"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["json"]["from"] == "Kolabo <no-reply@kolabo.test>"
    # A list, because the API takes one or many and a list is the shape that
    # does not change the day a second recipient appears.
    assert call["json"]["to"] == ["ama@example.com"]
    assert call["json"]["text"] == "Escrow released."
    assert call["json"]["subject"] == "Escrow released."
    # An empty reply-to is not a mailbox, and a provider may refuse the whole
    # message over one. Absent rather than blank.
    assert "reply_to" not in call["json"]


def test_a_configured_reply_to_travels_and_an_empty_one_does_not(configured, posted, monkeypatch):
    monkeypatch.setattr(email_module.settings, "mail_reply_to", "support@kolabo.test")
    email_module.ResendSender().send("ama@example.com", "security", "Your password changed.")
    assert posted[0]["json"]["reply_to"] == "support@kolabo.test"


def test_the_call_carries_an_explicit_timeout(configured, posted):
    """There is no queue and no retry: this runs inside the HTTP request that
    raised the notification, so the wait is somebody's spinner. httpx's own
    default is a number nobody here chose."""
    email_module.ResendSender().send("ama@example.com", "payment", "Escrow released.")
    assert posted[0]["timeout"] == email_module.TIMEOUT_SECONDS


def test_a_target_that_is_not_an_address_is_not_posted(configured, posted):
    """service.notify addresses to `user.email or user.phone`, so until the
    identity moves most targets are phone numbers. Posting one to a mail API
    buys a rejection and an error line per notification, which would bury the
    failures worth reading."""
    email_module.ResendSender().send("+22990000001", "payment", "Escrow released.")
    assert posted == []


# --------------------------------------------------------------------------
# The subject line
# --------------------------------------------------------------------------


def test_the_subject_is_the_messages_first_line_only(configured, posted):
    """A subject is a MAIL HEADER and a header ends at a newline, so a message
    carrying one would otherwise be an invitation to write a second header."""
    email_module.ResendSender().send(
        "ama@example.com", "payment", "Escrow released.\nbcc: someone@evil.test"
    )
    assert posted[0]["json"]["subject"] == "Escrow released."
    # The body is untouched: it is prose, not a header.
    assert "\n" in posted[0]["json"]["text"]


def test_a_long_message_gets_a_capped_subject(configured, posted):
    email_module.ResendSender().send("ama@example.com", "dispute", "x" * 500)
    assert len(posted[0]["json"]["subject"]) == email_module.MAX_SUBJECT_CHARS


def test_a_message_with_no_prose_still_gets_a_subject(configured, posted):
    """Not expected, and not worth an exception on a request that was moving
    somebody's money."""
    email_module.ResendSender().send("ama@example.com", "security", "   ")
    assert posted[0]["json"]["subject"] == email_module.DEFAULT_SUBJECT


# --------------------------------------------------------------------------
# When the provider says no
# --------------------------------------------------------------------------


def test_a_provider_failure_is_swallowed_rather_than_raised(configured, monkeypatch):
    """The caller is mid-request with a notification row already added and, at
    several call sites, an escrow movement beside it. Raising here would turn a
    provider's bad minute into a 500 on a payment."""
    def refuse(url, *, json, headers, timeout):
        return httpx.Response(422, request=httpx.Request("POST", url), json={"message": "no"})

    monkeypatch.setattr(email_module.httpx, "post", refuse)
    email_module.ResendSender().send("ama@example.com", "payment", "Escrow released.")


def test_a_transport_error_is_swallowed_too(configured, monkeypatch):
    def explode(url, *, json, headers, timeout):
        raise httpx.ConnectTimeout("nothing answered")

    monkeypatch.setattr(email_module.httpx, "post", explode)
    email_module.ResendSender().send("ama@example.com", "payment", "Escrow released.")

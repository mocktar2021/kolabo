"""Notification delivery interface.

The email provider is not selected yet (see docs/ARCHITECTURE.md). Delivery sits
behind the Sender interface so a real provider (for example SendGrid or Postmark)
can be dropped in later without touching notification logic. The logging sender
records deliveries in an in memory outbox so the pilot and tests can inspect what
would have been sent. Users register with a phone, so if no email is on file the
target falls back to the phone as a placeholder until channel selection is
refined.
"""
import logging
from typing import Protocol

_log = logging.getLogger("kolabo.notifications.email")


class Sender(Protocol):
    def send(self, target: str, type: str, message: str) -> None:
        ...


class LoggingEmailSender:
    def __init__(self) -> None:
        self.outbox: list[dict] = []

    def send(self, target: str, type: str, message: str) -> None:
        _log.info("email to %s [%s]: %s", target, type, message)
        self.outbox.append({"target": target, "type": type, "message": message})


default_email_sender: Sender = LoggingEmailSender()

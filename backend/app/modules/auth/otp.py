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

_log = logging.getLogger("kolabo.auth.otp")


class Sender(Protocol):
    def send(self, phone: str, message: str) -> None:
        ...


class LoggingSender:
    def send(self, phone: str, message: str) -> None:
        _log.info("send to %s: %s", phone, message)


def generate_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def generate_token() -> str:
    return secrets.token_urlsafe(32)


default_sender: Sender = LoggingSender()

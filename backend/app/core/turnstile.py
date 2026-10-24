"""Cloudflare Turnstile: the challenge that stands in front of the three
endpoints a stranger can reach, and the half of the anti-abuse story that
per IP ceilings cannot cover.

WHY BOTH. app/core/ratelimit.py raises the cost of a flood from ONE address.
It does nothing about a thousand addresses, which is what a botnet or a few
dollars of proxy time buys, and raising its numbers to compensate would start
refusing real people behind carrier NAT long before it inconvenienced anybody.
A challenge answers the other question: whether there is a browser there at
all. Neither replaces the other and the limits stay exactly as they are.

HOW IT WORKS, from the documentation rather than from memory. The widget in
the browser produces a token. The token comes to us, we POST it to
challenges.cloudflare.com/turnstile/v0/siteverify with the secret key, and
Cloudflare answers success true or false. The token is SINGLE USE and expires
300 seconds after it is issued: a replay answers `timeout-or-duplicate`. That
is why the widget has to be reset after every submission, successful or not,
and why a form somebody leaves open for ten minutes has to fetch a fresh one
rather than reusing what it had.

TWO SWITCHES, NOT ONE, AND THE SECOND ONE IS ABOUT THE PHONE.

  turnstile_secret_key empty  -> nothing happens at all. Development, CI and
      any box that has not been configured behave exactly as before. This is
      the same shape fedapay_secret_key uses for the same reason.

  turnstile_secret_key set    -> a token that ARRIVES is verified, and a bad
      one is refused. The web app always sends one, so the web is protected.

  turnstile_required true     -> a request with NO token is refused too.

Those are separate because the mobile app sends no token and cannot easily be
made to: Turnstile has no native React Native widget, and KOL-130 exists to
keep this API working with the last store-approved build. Turning the secret
on protects the web without touching the app. Turning `required` on closes the
remaining hole, which is a bot that simply omits the header and looks like a
phone, AND BREAKS EVERY SHIPPED MOBILE BUILD AT THE SAME TIME. That is a
deployment decision with a user-visible consequence, so it is a setting
somebody turns on deliberately rather than something that arrives with a
dependency upgrade.

FAIL OPEN WHEN CLOUDFLARE CANNOT BE REACHED, and this is a real trade rather
than an oversight. A timeout, a DNS failure or a 500 from siteverify means we
do not know whether there was a browser there. Refusing would turn a
Cloudflare incident into "nobody can sign in to Kolabo", which is a worse
outcome than a few unchallenged requests during an outage, especially on a
platform whose users are already on unreliable connections. An explicit
`success: false` is a different thing and is always refused: that is an answer,
not an absence of one. Every fail-open path logs at WARNING so an outage is
visible rather than silent.
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings

_log = logging.getLogger("kolabo.turnstile")

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# The header the token travels in, named after the field the widget writes.
#
# A HEADER RATHER THAN A BODY FIELD, deliberately. A token is not part of the
# thing being created: it says something about the caller, not about the
# account being registered, and putting it in the schema would have meant
# editing RegisterRequest, LoginRequest and PasswordResetRequest and changing
# three documented request bodies. A header leaves every existing client's
# payload byte for byte what it was, which is what KOL-130 asks for.
HEADER = "cf-turnstile-response"

# Five seconds. Long enough for a round trip to Cloudflare from West Africa,
# short enough that an unreachable siteverify does not hold a login open until
# the browser gives up. Enrichment and the mail sender use the same order of
# magnitude for the same reason.
TIMEOUT_SECONDS = 5.0


def configured() -> bool:
    """Whether a secret key is set, which is what turns any of this on."""
    return bool(settings.turnstile_secret_key)


def required() -> bool:
    """Whether a request arriving with NO token should be refused.

    Separate from configured() because of the mobile app. See the module
    docstring: this is the switch that closes the last hole and breaks every
    shipped build, in the same movement.
    """
    return configured() and settings.turnstile_required


def verify(token: str, ip: str | None = None) -> bool:
    """Ask Cloudflare whether this token is good. Fail open on no answer.

    `ip` is optional for Cloudflare and is passed when known, because it lets
    them correlate the solve with the address that solved it. It is the
    address ratelimit.client_ip worked out, which is the rightmost
    X-Forwarded-For entry rather than anything the caller chose.
    """
    payload = {"secret": settings.turnstile_secret_key, "response": token}
    if ip:
        payload["remoteip"] = ip
    try:
        res = httpx.post(VERIFY_URL, data=payload, timeout=TIMEOUT_SECONDS)
        res.raise_for_status()
        body = res.json()
    except (httpx.HTTPError, ValueError) as exc:
        # No answer is not the same as a refusal. See the module docstring.
        _log.warning("Turnstile siteverify unreachable, allowing the request: %s", exc)
        return True

    if body.get("success") is True:
        return True

    # Logged because the codes distinguish a misconfiguration we caused from a
    # challenge the caller failed, and only one of those is worth waking up
    # for. invalid-input-secret means the wrong key is in deploy/.env;
    # timeout-or-duplicate usually means a form was submitted twice with the
    # same token, which is a client bug rather than an attack.
    _log.warning("Turnstile refused a token: %s", body.get("error-codes"))
    return False

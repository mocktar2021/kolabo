"""Turning an Apple identity token into a person we are willing to sign in as.

READ auth/google.py FIRST. This module answers the same question (who is at
the door) and most of the reasoning there applies here unchanged: there is no
client secret and no code exchange on this path, the client gets a token from
Apple and posts it, this module only reads it, and what is DONE with the answer
belongs to auth.service. What follows is only where Apple differs, because
every one of those differences changes a rule rather than a noun.

THE ADDRESS IS NOT THE IDENTITY HERE, AND THAT IS THE WHOLE DESIGN.
Google puts a confirmed mailbox in every token, which is why the Google path
can look an account up by address and why email_verified is load bearing over
there. Apple does neither:

  * THE EMAIL CLAIM ARRIVES ONCE. Apple includes `email` the first time a
    person authorises this app and generally omits it on every sign in after
    that. A flow that needs the address to find the account therefore works on
    the day somebody signs up and fails forever afterwards, which is the single
    most common way this integration is got wrong.
  * THE ADDRESS MAY BE A RELAY. If the person chose Hide My Email, `email` is
    a per-app address at privaterelay.appleid.com that forwards to a mailbox
    we never see, and `is_private_email` says so. It is deliverable, so our
    transactional mail still reaches them, but it is not the address they would
    type into a login form and it will never equal one already on an account.
  * THE ADDRESS CAN CHANGE UNDER US. A person can turn the relay off later, at
    which point the same Apple account starts presenting its real address.

  So the account link is kept on `sub` and nothing else, in users.apple_sub,
  and auth.service looks accounts up by that column before it considers an
  address at all. `sub` is stable for the life of the Apple account for this
  app, which is exactly the property the address does not have.

WHY A HAND ROLLED VERIFIER HERE WHEN google.py ARGUES AGAINST ONE. Because
Apple publishes no library to use instead. The argument in google.py was never
"hand rolling is forbidden", it was that hand rolling is a lot of surface for
something that must never be nearly correct, and that a library was available.
Here it is not, so the surface is taken on deliberately and kept as small as it
can be: python-jose (already a dependency, already doing the crypto for our own
access tokens) performs the RS256 verification, and everything this file adds
is fetching the public keys and comparing claims.

WHAT VERIFICATION HAS TO ESTABLISH:

  * THE SIGNATURE IS APPLE'S, against the key named by the token's own `kid`,
    taken from https://appleid.apple.com/auth/keys. See _signing_key below for
    why an unknown `kid` refetches once rather than refusing.
  * `iss` IS https://appleid.apple.com exactly.
  * `aud` IS ONE OF OURS, and this is the check that is easy to lose here.
    python-jose accepts a SINGLE audience string, not a list, so passing our
    set is not an option and the audience check is turned off in the decode
    call and performed below by hand. An audience check that is written out in
    the open is fine; one that is absent accepts a correctly signed Apple token
    issued to any other application on the App Store as a way into Kolabo.
  * `exp` HAS NOT PASSED. python-jose does this. An Apple identity token is
    short lived, which bounds what a leaked one is worth.

WHAT IS DELIBERATELY NOT CHECKED, AND WHAT THAT COSTS. There is no nonce. The
native flow can carry one and we do not send one, which means a token lifted
off a device inside its lifetime could be replayed by whoever holds it. That is
the same exposure the Google path already accepts, it is bounded by TLS and by
a short `exp`, and closing it means the client minting and remembering a nonce
across two calls of a two step signup. It is written down here rather than
left to be discovered, and it is the one hardening step this module has left.

UNSET MEANS UNAVAILABLE. With no client ids configured there is no audience to
check against and the feature reports itself absent, exactly as Google's does.
"""
import logging
import threading
import time
from dataclasses import dataclass

import httpx
from jose import jwt

from app.core.config import settings
from app.core.emails import normalized_email

_log = logging.getLogger("kolabo.auth.apple")

ISSUER = "https://appleid.apple.com"
KEYS_URL = "https://appleid.apple.com/auth/keys"

# Long enough that a busy server is not refetching on every sign in, short
# enough that a rotated key is picked up without a deploy. Apple rotates
# without announcement, which is also why an unknown `kid` forces a refetch
# rather than waiting for this to expire.
KEYS_TTL_SECONDS = 3600.0

# Apple's key endpoint is on the sign in path, so a hung connection is a hung
# sign in. Same budget as the enrichment fetches in profiles/enrichment.py.
TIMEOUT_SECONDS = 6.0

# The relay domain Hide My Email issues under. Used only to answer "is this a
# real mailbox", and only as a second opinion: the token's own
# `is_private_email` claim is the first.
PRIVATE_RELAY_DOMAIN = "privaterelay.appleid.com"


@dataclass(frozen=True)
class AppleIdentity:
    """Who Apple says this is, reduced to what anything here can use.

    Frozen for the reason GoogleIdentity is frozen: it crosses a trust
    boundary, assembled once from claims that have just been checked.

    `subject` is Apple's `sub` and is the ONLY field that is always present.
    It is what users.apple_sub holds and what auth.service looks an account up
    by. It is stable for this app for the life of the Apple account.

    `email` IS OPTIONAL AND THAT IS NORMAL, not a degraded case. Apple sends it
    on the first authorisation and usually omits it afterwards, so None here
    means "this is a returning person", not "something went wrong". Already
    normalised when present, through the same core.emails function
    registration uses, so callers can look up with it directly.

    `email_verified` is Apple's claim about that address. A relay address is
    always verified, because Apple owns it.

    `is_private_email` is true for a Hide My Email relay address. It matters
    because such an address is deliverable but is NOT evidence that the holder
    controls any mailbox a Kolabo account could already be under, so
    auth.service must never use one to claim an existing account.

    NEITHER subject NOR email TRAVELS ON A RESPONSE. MeOut carries
    apple_linked, a boolean, for the same reason it carries google_linked.
    """

    subject: str
    email: str | None
    email_verified: bool
    is_private_email: bool


def client_ids() -> set[str]:
    """The audiences an Apple identity token may be addressed to.

    COMMA SEPARATED, like google_client_ids, and for a sharper reason here.
    On the native iOS flow Apple stamps the app's BUNDLE ID into `aud`
    (com.kolaboafrica.app), while the web flow stamps a SERVICES ID, which is a
    different string that has to be created separately in the Apple developer
    portal. They are not interchangeable and both are ours, so one value would
    verify one surface and refuse the other.

    Empty means the feature is off everywhere. See the module docstring.
    """
    return {raw.strip() for raw in settings.apple_client_ids.split(",") if raw.strip()}


# The cache, and the lock that stops a thundering herd of first requests all
# fetching the same document. A plain dict guarded by a lock rather than
# anything cleverer: this is read on every Apple sign in and written about
# once an hour.
_keys_lock = threading.Lock()
_keys_cache: list[dict] = []
_keys_fetched_at: float = 0.0


def _fetch_keys() -> list[dict]:
    """Apple's current public keys, or an empty list and a line in the log."""
    try:
        response = httpx.get(KEYS_URL, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        keys = response.json().get("keys")
    except Exception as exc:  # noqa: BLE001
        # Apple being unreachable is not something a caller can act on and not
        # something that should become a 500 on a sign in button. It becomes a
        # refusal, like every other way of failing to establish who this is.
        _log.warning("Could not fetch Apple signing keys: %s: %s", type(exc).__name__, exc)
        return []
    if not isinstance(keys, list) or not keys:
        _log.warning("Apple signing key document had no keys in it")
        return []
    return keys


def _signing_key(kid: str) -> dict | None:
    """The key Apple named in this token's header, refetching once if need be.

    AN UNKNOWN `kid` FORCES A REFETCH, and that is the point of this function.
    Apple rotates signing keys without announcement, so the first token signed
    by a new key arrives while the cache still holds only the old ones. Waiting
    for the hour to run out would mean every sign in failing for up to an hour
    after each rotation, which is an outage nobody would attribute to the right
    cause. Refetching immediately turns it into one extra HTTP call.

    THE REFETCH IS BOUNDED TO ONCE PER CALL. A `kid` Apple genuinely does not
    publish (a forged header, most likely) must not be able to make this
    function fetch in a loop, so a miss after a fresh document is a refusal.
    """
    global _keys_cache, _keys_fetched_at

    with _keys_lock:
        fresh = _keys_cache and (time.monotonic() - _keys_fetched_at) < KEYS_TTL_SECONDS
        if not fresh:
            fetched = _fetch_keys()
            if fetched:
                _keys_cache = fetched
                _keys_fetched_at = time.monotonic()
        keys = list(_keys_cache)

    for key in keys:
        if key.get("kid") == kid:
            return key

    # Not in what we hold. Either the cache is stale through rotation, or the
    # header is naming a key that does not exist.
    with _keys_lock:
        fetched = _fetch_keys()
        if fetched:
            _keys_cache = fetched
            _keys_fetched_at = time.monotonic()
        keys = list(_keys_cache)

    for key in keys:
        if key.get("kid") == kid:
            return key

    _log.warning("Apple identity token names signing key %r, which Apple does not publish", kid)
    return None


def _is_true(claim: object) -> bool:
    """Apple's booleans, which arrive as booleans or as the strings for them.

    Apple has shipped `email_verified` and `is_private_email` as JSON booleans
    and as the quoted strings "true" and "false" at different times and on
    different flows. Anything that is not recognisably true is false, because
    the two places these feed are a takeover check and a "may this address
    claim an account" check, and the safe reading of an unrecognised value in
    both is the restrictive one.
    """
    return claim is True or claim == "true"


def verify(raw_token: str | None) -> AppleIdentity | None:
    """Check a token completely, or answer None and say why in the log.

    ONE FAILURE VALUE FOR EVERY WAY OF FAILING, exactly as auth.google.verify
    does, and for the same reason: the caller turns None into a single refusal,
    so a forged, expired, wrongly addressed or unparseable token are
    indistinguishable from outside while the reason is still written down for
    whoever has to diagnose a button that refuses everybody.

    A MISSING EMAIL IS NOT A FAILURE. It is the normal shape of every sign in
    after the first. See the module docstring, and see auth.service for what it
    does with an identity that carries no address.
    """
    if not raw_token:
        return None

    audiences = client_ids()
    if not audiences:
        # Defensive: the endpoint refuses with auth_apple_unavailable long
        # before this. Repeated for the reason google.py repeats it, because a
        # verifier that checks a signature and then skips the audience is the
        # one mistake in this file that must not be reachable by any path.
        _log.warning("Apple sign in attempted with no APPLE_CLIENT_IDS configured")
        return None

    try:
        header = jwt.get_unverified_header(raw_token)
    except Exception as exc:  # noqa: BLE001
        _log.warning("Apple identity token has no readable header: %s", type(exc).__name__)
        return None

    kid = header.get("kid")
    if not kid:
        _log.warning("Apple identity token header names no signing key")
        return None

    key = _signing_key(str(kid))
    if key is None:
        return None

    try:
        claims = jwt.decode(
            raw_token,
            key,
            algorithms=["RS256"],
            issuer=ISSUER,
            # THE AUDIENCE IS CHECKED BELOW, BY HAND, AND IT IS NOT OPTIONAL.
            # python-jose takes one audience string and we have several, so
            # the library cannot do this one for us. Turning the check off
            # here and then forgetting to do it there would accept a correctly
            # signed Apple token issued to any other app on the App Store.
            options={"verify_aud": False},
        )
    except Exception as exc:  # noqa: BLE001
        # DELIBERATELY BROAD, like the Google one. JWTError for a bad
        # signature, ExpiredSignatureError for an expired token,
        # JWTClaimsError for a wrong issuer, and whatever a malformed payload
        # raises on the way through. All of them mean we cannot say who this
        # is, and none of them should become a 500.
        _log.warning("Apple identity token refused: %s: %s", type(exc).__name__, exc)
        return None

    # THE AUDIENCE CHECK. `aud` is a string on every Apple token seen so far,
    # and the JWT specification allows a list, so both are handled rather than
    # trusting the shape.
    raw_aud = claims.get("aud")
    token_audiences = set(raw_aud) if isinstance(raw_aud, list) else {raw_aud}
    if not token_audiences & audiences:
        _log.warning("Apple identity token has audience %r, which is not ours", raw_aud)
        return None

    subject = claims.get("sub")
    if not subject:
        # Apple always sends one, and without it there is nothing to link an
        # account to, which on this provider means there is no identity at all.
        _log.warning("Apple identity token carries no subject claim")
        return None

    # Absent on most sign ins. Normalised when present so no caller re-derives
    # it, and dropped if it is not a usable address rather than carried as a
    # half value.
    email = normalized_email(claims.get("email")) if claims.get("email") else None

    is_private = _is_true(claims.get("is_private_email"))
    if email and email.endswith("@" + PRIVATE_RELAY_DOMAIN):
        # A second opinion on the claim, and the restrictive one wins. The
        # domain is Apple's own and nothing else is issued under it, so an
        # address at it is a relay whatever the claim says or omits.
        is_private = True

    return AppleIdentity(
        subject=str(subject),
        email=email,
        email_verified=_is_true(claims.get("email_verified")),
        is_private_email=is_private,
    )

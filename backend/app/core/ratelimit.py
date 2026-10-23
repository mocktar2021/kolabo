"""Per IP ceilings on the endpoints a stranger can reach without an account.

WHY THIS EXISTS AT ALL. Until now there was no rate limiting anywhere in the
application: main.py added exactly one middleware and it was CORS. The OTP
module says so in its own comments, and the counters that do exist are all
per account rather than per caller. That leaves two holes a script walks
straight through.

Login had nothing. No attempt counter, no lockout, no delay. A password is
guessable at whatever rate the server answers.

Registration had a ceiling that was worse than none in one specific way. The
global cap in auth.service is a shared fuse: whoever fills it locks out every
honest signup until those codes expire. Its own comment admits this, and sets
the number far above plausible traffic for exactly that reason. But a script
reaches a number like that in minutes, and then nobody can sign up. A per IP
ceiling in front of it means one caller exhausts their own allowance and
nobody else's, which is what a ceiling should do.

WHAT IT IS NOT. This is not bot detection. It raises the cost of a flood from
one address; it does nothing about a thousand addresses, and the honest answer
to that is a challenge at the edge (Turnstile) rather than a bigger number
here. The two are complements and both are needed.

SHARED ADDRESSES ARE THE DESIGN CONSTRAINT, not an afterthought. Kolabo's
markets run large numbers of subscribers behind carrier NAT, so one IP can be
a whole city's mobile users, and an office or a cyber cafe is one address by
construction. Every limit below is therefore set where a script is stopped
and a crowd is not: generous enough that honest sharing never reaches it,
small enough that a flood dies immediately. If one of these ever fires for a
real person, the number is wrong and should be raised, not defended. The
refusal says "this connection" rather than "you" for the same reason.

IN PROCESS, AND THAT IS DELIBERATE. The counters live in this module's memory
rather than in Postgres or Redis.

  - Deployment pins ONE uvicorn worker (deploy/docker-compose.prod.yml says so
    and says why), so there is exactly one copy of these counters and they
    cannot disagree with each other. If that ever becomes several workers,
    each gets its own allowance and the effective limit multiplies by the
    worker count. That is a correctness note for whoever scales it, not a
    reason to reach for Redis today.
  - A deploy resets them. For abuse control that is acceptable: an attacker
    gains one fresh window per deploy, which is not a strategy.
  - No row is written per request. The OTP ceilings already pay a database
    round trip; making every login do the same to count it would be a cost
    on every honest request in order to inconvenience a dishonest one.
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock

from fastapi import Request

# How many entries the table holds before it starts evicting. An attacker
# rotating source addresses creates one entry each, so this is the ceiling on
# what that costs us in memory: roughly a few megabytes at this size. Eviction
# drops the least recently touched entries, which under a rotation flood are
# the attacker's own spent ones.
MAX_KEYS = 50_000

# THE LIMITS. Each is (requests, seconds), per IP, per endpoint.
#
# Read them against the shared address note above: the question each one
# answers is not "how often would a person do this" but "what number is a
# crowd never going to reach and a script always will".
#
# REGISTER is the expensive one, because it sends email and it is also the
# resend path. Fifteen an hour from one address is a busy cyber cafe; a flood
# wants thousands.
REGISTER = (15, 3600)
# PASSWORD RESET sends email too and is a smaller surface: nobody legitimately
# resets ten passwords an hour from one address.
PASSWORD_RESET = (10, 3600)
# LOGIN is the brute force surface and the reason KOL-65 exists. Thirty in a
# quarter of an hour covers an office where several people fumble a password
# at once; it does not cover guessing.
LOGIN = (30, 900)
# VERIFY OTP is guess-the-code. The per account allowance in auth.otp already
# kills every live code after five wrong guesses, so this one is not about a
# single account: it is about walking many accounts from one address.
VERIFY_OTP = (30, 900)

_HITS: dict[tuple[str, str], deque[float]] = {}
_LOCK = Lock()


def client_ip(request: Request) -> str:
    """The address Caddy actually observed, which is the last X-Forwarded-For
    entry and never the first.

    THE FIRST ENTRY IS ATTACKER CONTROLLED. Caddy augments this header rather
    than replacing it, so a caller who sends `X-Forwarded-For: 1.2.3.4`
    produces `1.2.3.4, <their real address>` by the time it reaches us.
    Reading the left hand end would let anybody pick their own rate limit
    bucket, which is the same as having no rate limit. The right hand end is
    the one hop we did not take on trust.

    request.client.host is NOT used as the primary source even though uvicorn
    runs with --proxy-headers --forwarded-allow-ips='*', because that
    combination means uvicorn rewrites the client address from this same
    header according to its own version's rules. Parsing it here makes the
    choice explicit and stops a uvicorn upgrade quietly changing which end is
    read. The fallback below still uses it, for the case where there is no
    proxy at all: local development, and the test suite.

    WHAT THIS RESTS ON: nothing but Caddy can reach the backend. The service
    publishes no port in deploy/docker-compose.prod.yml and is reachable only
    on the compose network. If that ever changes, this function is wrong and
    so is every limit built on it.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    if request.client and request.client.host:
        return request.client.host
    # A request with no discernible origin is still a request. Bucketing them
    # together is the safe failure: they share one allowance rather than each
    # getting an unlimited one.
    return "unknown"


def _prune(now: float) -> None:
    """Drop entries whose newest hit is older than the longest window.

    Called with the lock held. The longest window is computed from the limits
    above rather than hard coded, so adding a slower bucket cannot silently
    start evicting it early.
    """
    longest = max(window for _, window in (REGISTER, PASSWORD_RESET, LOGIN, VERIFY_OTP))
    stale = [key for key, hits in _HITS.items() if not hits or now - hits[-1] > longest]
    for key in stale:
        del _HITS[key]


def allow(bucket: str, ip: str, limit: int, window: float, now: float | None = None) -> bool:
    """Record one request and say whether it is within the allowance.

    A sliding window, kept as the timestamps of the hits still inside it. At
    these limits that is at most a few dozen floats per address, which is
    cheaper than the arithmetic needed to avoid storing them, and it has no
    edge at a window boundary: a fixed window would let a caller spend a full
    allowance either side of one second and pass twice the limit.

    A REFUSED REQUEST IS NOT RECORDED. Otherwise a caller who keeps hammering
    keeps pushing their own window forward and stays locked out indefinitely,
    which turns a speed limit into a ban nobody chose to impose.

    `now` is injectable because a window that nobody can test is a window
    nobody has checked.
    """
    moment = time.monotonic() if now is None else now
    key = (bucket, ip)
    with _LOCK:
        if len(_HITS) >= MAX_KEYS:
            _prune(moment)
            while len(_HITS) >= MAX_KEYS:
                # Still full after pruning means a live flood across many
                # addresses. Drop the oldest insertion rather than refusing
                # service: dicts preserve insertion order, so this is the
                # entry least likely to be mid-window.
                _HITS.pop(next(iter(_HITS)))
        hits = _HITS.setdefault(key, deque())
        while hits and moment - hits[0] > window:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(moment)
        return True


def reset() -> None:
    """Forget everything. For tests, which must not inherit each other's counts."""
    with _LOCK:
        _HITS.clear()


def exceeded(bucket: str, rule: tuple[int, float], request: Request) -> bool:
    """True when this request is over the allowance for its bucket.

    A PREDICATE RATHER THAN A DEPENDENCY FACTORY THAT RAISES, and the reason
    is a rule this codebase enforces in backend/tests/test_error_codes.py:
    every AppError's code= must be a plain string literal, readable straight
    out of the source, because the two errorMessages suites scan for exactly
    that to prove each code has a French and an English sentence. A helper
    taking the code as an argument would hide it from that scan and let a
    refusal ship untranslated. The first version of this module did that and
    the test caught it. So the raising stays at the call site, where the code
    is written out and a reader can see which sentence a caller will get.
    """
    requests, window = rule
    return not allow(bucket, client_ip(request), requests, window)

"""The HTTP clients must not write Kolabo's credentials into the log.

WHAT THIS FILE PINS. app/core/logging.py exists because turning application
logging on in #188 also turned on httpx's own per-request INFO record, which
carries the FULL REQUEST URL. Every credential this platform sends to Meta or to
Google travels as a query parameter (client_secret, code, fb_exchange_token,
access_token in profiles/oauth.py; access_token and key in
profiles/enrichment.py), so that record wrote one of them out in clear text on
every SUCCESSFUL call.

THE SHAPE OF THESE TESTS IS COPIED FROM #183 ON PURPOSE. #183 fixed the ERROR
path of the same exposure and its tests prove the leak is REAL before proving it
is CLOSED, so that a fake which drifts away from the thing it imitates fails
loudly instead of passing for the wrong reason. The same trap is waiting here
and it is worse: after the fix, the honest expectation is that httpx writes
NOTHING, and "the credential is in no record" is trivially true of an empty
capture. A test that only asserted the absence would go on passing if httpx
stopped logging, if the request never happened, or if the capture were wired up
wrong. So the leak is demonstrated first, with the same fake credential through
the same code path, and only then closed.

THE REQUEST IS DRIVEN THROUGH A REAL httpx.Client against httpx.MockTransport,
not through a stub. The record under test is one httpx composes itself, inside
_send_single_request, out of the request it actually built: nothing here writes
the log line being asserted on, which is the only way this test can say anything
about the library. MockTransport keeps it off the network.

EVERY CREDENTIAL IN THIS FILE IS OBVIOUSLY FAKE and is not a value from any
account, live or otherwise.
"""
import logging

import httpx
import pytest

from app.core.logging import (
    HTTP_CLIENT_LEVEL,
    HTTP_CLIENT_LOGGERS,
    LEVEL,
    configure_logging,
)

# Shaped like a Meta app secret so a human reading a failure knows what it
# stands for, and unmistakably not one.
FAKE_CREDENTIAL = "SECRET-abc123-fake-app-secret-never-a-real-one"

# The exact call profiles/oauth.py makes on the first leg of a token exchange,
# which is the one that carries the app secret.
TOKEN_URL = "https://graph.facebook.com/v26.0/oauth/access_token"

# The application's own loggers, which must stay at INFO. Silencing httpx by
# turning everything down would undo what #188 was for, so these are asserted
# on as explicitly as the ones being quietened.
APP_LOGGERS = (
    "kolabo.sweeps",
    "kolabo.profiles.oauth",
    "kolabo.profiles.enrichment",
    "kolabo.notifications.email",
)


@pytest.fixture(autouse=True)
def restore_logging_levels():
    """Put every level back afterwards.

    configure_logging() writes to PROCESS-WIDE state: the root logger and four
    named ones. Without this, the first test in this file would set the root
    logger to INFO for every test that runs after it in the same session, which
    is the kind of cross-test coupling that gets blamed on the wrong file three
    months later. The handler basicConfig may install is left in place, because
    removing a handler other tests may since have relied on is a worse trade
    than one idle StreamHandler.
    """
    names = ("",) + tuple(HTTP_CLIENT_LOGGERS) + APP_LOGGERS
    before = {name: logging.getLogger(name).level for name in names}
    try:
        yield
    finally:
        for name, level in before.items():
            logging.getLogger(name).setLevel(level)


class Capture(logging.Handler):
    """Collects formatted records off the root logger.

    A handler of our own rather than caplog, so that what is captured is
    unambiguous: this one sits at NOTSET on the root logger and therefore sees
    every record that survives its own logger's level check, which is exactly
    the filter under test. caplog would work too, but it also manipulates
    levels, and a test about levels should not share its instrument with the
    thing it is measuring.
    """

    def __init__(self):
        super().__init__(level=logging.NOTSET)
        self.lines: list[str] = []

    def emit(self, record):
        self.lines.append(record.getMessage())

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _as_if_freshly_booted() -> None:
    """Put the root logger where a real boot puts it: INFO.

    WHY A TEST HAS TO DO THIS BY HAND. configure_logging() leaves the root
    level to logging.basicConfig, and basicConfig does NOTHING when the root
    logger already has a handler. In a container root has none, so a real boot
    lands at INFO. Under pytest the framework has installed capture handlers
    long before any test runs, so basicConfig is a no-op and root sits at
    WARNING. See configure_logging for why it is not forced.

    That matters more than a detail of setup, because root at WARNING would
    hide httpx's INFO record all by itself and every assertion below about the
    credential being absent would pass without the fix doing anything at all.
    INFO on the root logger IS the condition #188 created and IS the condition
    this leak needs, so these tests recreate it deliberately and then show the
    silencing holds anyway.
    """
    logging.getLogger().setLevel(logging.INFO)


@pytest.fixture()
def captured():
    handler = Capture()
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield handler
    finally:
        root.removeHandler(handler)


def _a_successful_token_request() -> httpx.Response:
    """One real httpx GET, with the credential in the query string, that SUCCEEDS.

    200, deliberately. The leak this file is about is on the success path: it is
    not an exception message, nothing is raised, and raise_for_status is never
    reached. A test written against a failure would be testing #183 again.
    """
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    with httpx.Client(transport=transport) as client:
        return client.get(
            TOKEN_URL,
            params={
                "client_id": "1234567890",
                "client_secret": FAKE_CREDENTIAL,
                "redirect_uri": "https://api.example/cb",
                "code": "the-authorization-code",
            },
        )


# --- the premise -------------------------------------------------------------


def test_httpx_really_does_write_the_whole_url_at_info(captured):
    """THE LEAK, DEMONSTRATED, so that closing it below means something.

    With httpx's logger at INFO, which is what a bare
    `logging.basicConfig(level=logging.INFO)` gives it, one successful request
    puts the client secret and the authorization code into a log record. If this
    test ever goes green-by-accident (httpx stops logging, the capture breaks,
    the request does not happen) it fails here rather than handing a false pass
    to the test below.
    """
    _as_if_freshly_booted()
    logging.getLogger("httpx").setLevel(logging.INFO)

    response = _a_successful_token_request()
    assert response.status_code == 200

    assert "HTTP Request: GET" in captured.text, "httpx logged nothing at all"
    assert FAKE_CREDENTIAL in captured.text
    assert "the-authorization-code" in captured.text


# --- the fix -----------------------------------------------------------------


def test_configure_logging_keeps_the_credential_out_of_every_record(captured):
    """THE SAME REQUEST, THE SAME CREDENTIAL, AFTER configure_logging().

    Not "no httpx record", but the stronger and more useful claim: the secret
    appears in NO captured record at all, whoever emitted it.

    THE ROOT LOGGER IS PUT AT INFO FIRST, which is the whole point. Left at
    pytest's WARNING this test would pass with configure_logging deleted, and
    would be proving nothing except that a high root level hides everything.
    """
    configure_logging()
    _as_if_freshly_booted()

    response = _a_successful_token_request()
    assert response.status_code == 200

    assert FAKE_CREDENTIAL not in captured.text
    assert "the-authorization-code" not in captured.text
    assert "HTTP Request" not in captured.text


def test_the_http_client_loggers_are_at_warning_or_above():
    """The level itself, named logger by named logger.

    getEffectiveLevel rather than .level, because what decides whether a record
    is emitted is the effective level, and a test that read the raw attribute
    would pass on a logger set to NOTSET that inherits INFO from the root.

    AND THE ROOT LOGGER IS PUT AT INFO FIRST, for a reason found by deleting
    the fix and watching which tests noticed. Left at pytest's WARNING, an
    unconfigured httpx logger INHERITS 30 and this test goes green against a
    configure_logging() that does nothing whatsoever. At INFO it can only pass
    if the level really was set on the logger itself, which is the claim.
    """
    configure_logging()
    _as_if_freshly_booted()

    for name in ("httpx", "httpcore"):
        logger = logging.getLogger(name)
        assert logger.getEffectiveLevel() >= logging.WARNING, name

    # The whole configured set, so adding a name to HTTP_CLIENT_LOGGERS without
    # it actually taking effect cannot pass.
    for name in HTTP_CLIENT_LOGGERS:
        assert logging.getLogger(name).getEffectiveLevel() >= HTTP_CLIENT_LEVEL, name


def test_the_applications_own_loggers_are_still_at_info():
    """#188'S PURPOSE SURVIVES THIS FIX, which is half the point of it.

    The cheap way to stop httpx talking is to turn the root logger down, and it
    would also throw away every `_log.info` in this codebase, which is the exact
    thing #188 existed to start recording. So this asserts the application side
    explicitly: at the root level a real boot produces, every module logger
    that inherits from it is still enabled for INFO, and configure_logging has
    pinned none of them down on its way past.
    """
    configure_logging()
    _as_if_freshly_booted()

    assert LEVEL == logging.INFO
    assert logging.getLogger().getEffectiveLevel() == logging.INFO
    for name in APP_LOGGERS:
        logger = logging.getLogger(name)
        assert logger.getEffectiveLevel() == logging.INFO, name
        assert logger.isEnabledFor(logging.INFO), name


def test_an_application_info_line_still_reaches_a_handler(captured):
    """The level is the mechanism, but a record arriving is the point.

    Asserts the two halves together in one place: an application INFO line is
    written, and the httpx line raised by a request in the same breath is not.
    """
    configure_logging()
    _as_if_freshly_booted()

    logging.getLogger("kolabo.profiles.oauth").info(
        "Meta connection manages %d Pages, so no follower count was recorded", 4
    )
    _a_successful_token_request()

    assert "no follower count was recorded" in captured.text
    assert FAKE_CREDENTIAL not in captured.text


def test_configure_logging_can_be_called_twice(captured):
    """Both entrypoints call it, and a test may call it after pytest has already
    installed handlers of its own. basicConfig does NOTHING when the root logger
    already has a handler, so the levels have to be set regardless of who got
    there first; this is what pins that.
    """
    configure_logging()
    configure_logging()
    _as_if_freshly_booted()

    assert logging.getLogger().getEffectiveLevel() == logging.INFO
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING

    _a_successful_token_request()
    assert FAKE_CREDENTIAL not in captured.text

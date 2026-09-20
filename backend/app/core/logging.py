"""How this application configures the standard library's logging, in one place.

WHY THIS IS A MODULE AND NOT TWO COPIES OF A basicConfig CALL. There are two
entrypoints, app/main.py and app/jobs/sweeps.py, and each used to spell out its
own `logging.basicConfig(level=logging.INFO, ...)`. Two copies of a setting are
how the two drift apart, and the drift is only ever noticed on the copy that
stayed correct. The incident below is the expensive version of that: the thing
that had to change was written down twice, so fixing it in the API would have
left the job container exactly as it was.

WHAT TURNING APPLICATION LOGGING ON COST, which is why this file has a
docstring rather than three lines of code and nothing else.

httpx WRITES ONE INFO RECORD PER REQUEST AND IT CARRIES THE FULL URL. The
statement lives in httpx._client.Client._send_single_request, on a logger named
plainly "httpx", and it reads:

    logger.info('HTTP Request: %s %s "%s %d %s"', request.method, request.url,
                response.http_version, response.status_code,
                response.reason_phrase)

`request.url` is the url as it went out, query string and all. It fires AFTER a
response is in hand, on the ordinary successful path, once per call.

EVERY KOLABO CREDENTIAL THAT TRAVELS TO META OR TO GOOGLE TRAVELS AS A QUERY
PARAMETER, which is what turns that record into a credential dump:

  * profiles/oauth.py `_graph` sends `client_secret` (the Meta app secret, which
    acts as the whole application), `code` (a spendable authorization code),
    `fb_exchange_token` and `access_token` (a creator's own long lived token).
  * profiles/enrichment.py sends META_GRAPH_TOKEN as `access_token` and
    YOUTUBE_API_KEY as `key`.

So on every SUCCESSFUL outbound call, httpx wrote one of those into the
application log in clear text, where anybody who can read the container's
output can read it.

THIS IS NOT THE BUG #183 FIXED, AND IT IS THE WORSE HALF OF IT. #183 was the
ERROR path: httpx interpolates the url into the message of the HTTPStatusError
that raise_for_status() composes, and the enrichment handlers logged that
exception object. A failed request is the uncommon case. This is the SUCCESS
path, so it fires every single time instead of only when something already went
wrong, and no amount of redacting an exception message reaches it, because no
exception is involved at any point.

IT OPENED THE MOMENT #188 ADDED basicConfig TO app/main.py. Before that the API
configured no logging at all: the root logger had no handler, the effective
level was WARNING through Python's last resort handler, and httpx's INFO
records were dropped before anything could write them down. #188 turned
application logging on for reasons that still stand and are still recorded in
app/main.py. Turning application logging on is what turned this on with it.
Logging was not the mistake; leaving the HTTP clients inside it was.

SO THE FIX IS NOT TO TURN LOGGING BACK OFF. It is to say which libraries may
talk at which level, here, once, with the argument written next to the setting.

TO WHOEVER IS ABOUT TO RAISE A LEVEL: read HTTP_CLIENT_LOGGERS below first.
Dropping the ROOT logger to DEBUG does not on its own reopen this, because each
name in that tuple is given an explicit level and an explicit level beats an
inherited one. Deleting a name from the tuple does reopen it, and so does
calling setLevel on one of those loggers anywhere else in the codebase.

WHAT WAS CHECKED AND LEFT ALONE, so the next audit does not start from zero.
Every pin in backend/requirements.txt was looked at for a logger that writes a
url or a request body at INFO or DEBUG, and these were measured rather than
assumed:

  * sqlalchemy 2.0.35 does NOT echo SQL just because the root logger went to
    INFO. With `echo` unset it pins "sqlalchemy.engine.Engine" to WARNING
    itself, measured at an effective level of 30 under this exact basicConfig,
    so bound parameters are not in the log and nothing here needs to silence
    it. Setting `echo=True` in app/core/db.py WOULD put every statement and
    every bound parameter in, which is worth knowing before anybody tries it
    to debug a query.
  * alembic 1.13.3 logs at INFO, but only migration progress: no url, no body.
  * fastapi 0.115.0 and starlette log nothing per request of their own.
  * passlib, python-jose, cryptography, bcrypt, pydantic, psycopg2 and
    email-validator have no url or body logging on any path this uses.

AND ONE THING DELIBERATELY NOT FIXED HERE: uvicorn's access log. "uvicorn.access"
records the INBOUND request line, which includes the query string, so
GET /profiles/oauth/facebook/callback?code=...&state=... puts a spendable Meta
authorization code and the state that authorises the callback into the API log.
That is a real exposure and it is a SEPARATE one: uvicorn configures its own
loggers from its own log config, so it was already at INFO long before #188 and
is untouched by anything in this file. Silencing it here would also delete the
access log wholesale, which is an operational tool somebody relies on. It needs
its own change, with its own argument about what the access log is for.

A NOTE ON THIS MODULE'S NAME. `app/core/logging.py` importing `logging` gets the
standard library and not itself, because Python 3 resolves imports absolutely.
There is no shadowing here and there is nothing to work around.
"""
import logging

# The level the application's own loggers run at, and the one #188 chose. Every
# `_log.info` in this codebase depends on it.
LEVEL = logging.INFO

# The same format string both entrypoints already passed, kept exactly so that
# the API container and the job container go on producing identical lines.
FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"

# WARNING rather than ERROR, deliberately. A client that has something genuinely
# wrong to report (a retry it gave up on, a response it could not parse) should
# still be able to say so. What is being taken away is only the per-request
# chatter that nothing here asked for.
HTTP_CLIENT_LEVEL = logging.WARNING

# The loggers held at HTTP_CLIENT_LEVEL, and why each one is on the list.
HTTP_CLIENT_LOGGERS = (
    # THE ONE THAT WAS ACTUALLY LEAKING, and the reason this module exists.
    # One INFO record per request, carrying the whole url. See the docstring.
    "httpx",
    # The transport layer underneath httpx. Its records are DEBUG rather than
    # INFO, and measured against the pinned httpcore 1.0.9 they name the host
    # and port but NOT the query string: an http11 trace renders the request as
    # `<Request [b'GET']>` and the connection trace says
    # `connect_tcp.started host='graph.facebook.com' port=443`. So it is not a
    # second copy of this leak today. It is here anyway because it is the other
    # half of the same client: somebody debugging a connection problem reaches
    # for DEBUG on the root logger, and the point of this module is that doing
    # that does not quietly restart a per-request stream in the one process
    # holding the Meta app secret.
    "httpcore",
    # NOT AN httpx PROBLEM, AND MEASURED SEPARATELY. requirements.txt pins
    # google-auth[requests], whose `requests` extra pulls requests, which pulls
    # urllib3, and google sign in verification goes out through it rather than
    # through httpx. urllib3.connectionpool logs the request target INCLUDING
    # THE QUERY STRING:
    #
    #     log.debug('%s://%s:%s "%s %s %s" %s %s', scheme, host, port, method,
    #               url, version, status, length)
    #
    # measured against urllib3 by driving a real request at a local server and
    # reading the record back. That is DEBUG, so basicConfig at INFO does not
    # emit it and nothing has leaked through this path. It is on the list for
    # exactly the reason httpcore is: it is the same class of line, in the same
    # process, and the next person who turns DEBUG on to chase a Google sign in
    # problem should not have to know this to stay safe.
    "urllib3",
)


def configure_logging() -> None:
    """Apply this application's logging setup. Both entrypoints call this.

    IDEMPOTENT, AND SAFE TO CALL FROM A TEST. Nothing here removes a handler
    somebody else installed, which is what `basicConfig(force=True)` would do
    and is why it is not used: under pytest that would tear out the capture
    handler the test framework relies on.

    THE ROOT LEVEL IS LEFT ENTIRELY TO basicConfig, AND THAT IS A DECISION
    RATHER THAN AN OVERSIGHT, because `logging.basicConfig` DOES NOTHING AT ALL
    when the root logger already has a handler and returns quietly rather than
    saying so. In a real boot root has none: uvicorn's log config installs
    handlers on its own "uvicorn" loggers and not on root, which is precisely
    what #188 relied on, so basicConfig installs the handler and sets INFO and
    the application's loggers inherit it. Under pytest root ALREADY has
    handlers, so this line is a no-op there and the root level stays wherever
    the test framework left it.

    Forcing the level afterwards would make the two agree, and it was
    deliberately not done. It would change what the EXISTING test suite
    captures, session wide, in every file that imports app.main, in service of
    nothing that production does differently. An urgent credential fix is the
    wrong change to hide that inside. backend/tests/test_http_logging.py
    therefore sets the root logger to INFO itself, which is both the state #188
    created and the only state in which this leak exists, and then asserts the
    silencing still holds.

    THE PER-LOGGER LEVELS, on the other hand, are set unconditionally and that
    is what actually closes the hole. They do not depend on the root logger
    having been configured, they survive the basicConfig no-op, and an explicit
    level on a logger beats whatever it would otherwise inherit.
    """
    logging.basicConfig(level=LEVEL, format=FORMAT)
    for name in HTTP_CLIENT_LOGGERS:
        logging.getLogger(name).setLevel(HTTP_CLIENT_LEVEL)

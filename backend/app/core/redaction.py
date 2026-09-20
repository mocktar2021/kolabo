"""Striking a credential out of a line before anything writes it down.

WHY THIS IS A SHARED MODULE RATHER THAN A SECOND COPY OF THREE LINES. #183
fixed a live leak in profiles/enrichment.py: every enricher sent its credential
as a query parameter, so the credential was part of the request url, and httpx
puts the whole url inside the message of the HTTPStatusError that
raise_for_status() composes. Both handlers logged the exception object, so
every non-2xx wrote YOUTUBE_API_KEY or META_GRAPH_TOKEN into the application
log in clear text.

KOL-108 then asked the same question of profiles/oauth.py, which sends
META_APP_SECRET by the same means. The answer there turned out to be different
(see MetaOAuthProvider._graph, which records what was measured), but the LAST
line of defence wanted is identical: whatever is about to be logged, strike the
credential out of it first.

TWO COPIES OF THAT LOOP IS HOW THE TWO DRIFT. One of them grows a case, the
other does not, and the one that did not is the one holding the app secret. So
the striking lives here, once, and both callers reach for it. That is also why
this is a core module rather than an import of enrichment's private helper:
oauth.py and enrichment.py are deliberately parallel and neither should have to
import the other to borrow a rule they share.

DELIBERATELY NOT A CLEVER REDACTOR. It does not guess what a secret looks like,
it matches no patterns, and it keeps no list of key names of its own. It
strikes out the exact strings a caller names, because the caller is the only
thing that knows which of its values are credentials. A regex that recognised
"things that look like tokens" would miss the one that does not, and would
mangle ordinary text that merely resembles one.
"""

# One spelling, so a line reads the same whichever caller produced it and a
# search for what was caught finds every place something was struck out.
REDACTED = "[redacted]"


def redact(text: str, *secrets: str | None) -> str:
    """`text` with every secret the caller names replaced by REDACTED.

    None and "" are skipped rather than treated as secrets. A caller reads its
    credentials back off a params dict or a settings object, where an unset one
    is absent rather than empty, and striking "" would match at every position
    in the string: that turns a readable failure into confetti and destroys the
    log line it was meant to protect.
    """
    for secret in secrets:
        if secret:
            text = text.replace(secret, REDACTED)
    return text

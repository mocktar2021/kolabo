"""A url somebody else wrote, checked before anything is pointed at it.

WHY THIS EXISTS. Two places in this codebase take a url from outside and hand
it onward to something with real authority behind it. A creator types the link
to their published post into a deliverable submission, and both clients render
that value as a LIVE LINK in front of the brand. The profile importer takes an
avatar url out of a third-party API response and FETCHES it, from inside the
process, with whatever network position this process has. Until now neither url
was checked at all: submit() did `(payload.link_url or "").strip()` and stored
whatever came back.

THE CASE THAT MATTERS MOST IS `javascript:`. A creator can store
`javascript:...` today and wait for the brand to click it, on the page where
that brand is signed in and one button away from releasing escrow. `data:` and
`file:` are the same shape of problem carrying different payloads. None of it
needs a clever parser to stop, and trying to be clever about it is how these
filters get bypassed: an allow list of exactly two schemes refuses all of them,
and no honest submission has ever needed a third.

WHY ONE SHARED MODULE. The rule is a sentence long, which is precisely why it
must not be written twice. Two copies of a security check drift, and the drift
is only ever noticed on the copy that stayed strict. It sits in core/ rather
than inside either caller for the same reason contact_guard does: neither of
them owns the rule, they both just obey it.

WHAT THIS IS NOT. It is not a reputation check, it has no opinion about which
hosts are worth trusting, and `is_public_host` cannot see where a NAME resolves
to (the comment on it says so in detail rather than leaving a reader to assume
otherwise). This module refuses the shapes that are never legitimate. Judging
the ones that are is a different job with a different budget.
"""
import ipaddress
from urllib.parse import urlsplit, urlunsplit

# The ceiling on a url anybody stores. 2048 is the old Internet Explorer limit
# and has survived as the number every proxy, log line and database column is
# sized for; a link longer than this is not a link somebody typed.
#
# DELIBERATELY NOT ENFORCED BELOW. normalized_public_url answers one question,
# "would we hand this to a browser", and it answers it with None. A ceiling
# refused the same way would tell a creator with a 3000 character link that
# their link is malformed, which is both wrong and unactionable. The caller
# checks the length itself, before it asks about shape, so that it can raise
# its own error code with this number travelling beside it for the translated
# sentence to interpolate. See deliverables/service.py::submit.
MAX_URL_CHARS = 2048

# The scheme allow list. Two entries, and a third would need an argument about
# what browser behaviour it triggers, not a preference.
_ALLOWED_SCHEMES = ("http", "https")

# The one hostname that is a loopback without being an address literal. Written
# out rather than resolved, because resolving it here would mean resolving
# everything here, which is the wrong place to do it (see is_public_host).
_LOOPBACK_NAME = "localhost"


def _is_forbidden_character(ch: str) -> bool:
    """A character that has no business inside a url somebody typed.

    C0 controls, DEL, and whitespace of any kind. The whitespace half is the
    interesting one: a NEWLINE OR A TAB INSIDE A URL IS HOW A SCHEME FILTER
    GETS BYPASSED. urlsplit itself strips tabs and newlines before parsing, in
    line with the WHATWG rule browsers follow, so a `javascript:` url with a
    tab spliced into the middle of the word still parses as the scheme
    `javascript`, while a check on the raw text sees a word that is not one.
    Two readers disagreeing about what a string says is exactly the gap these
    payloads are built for.

    So the answer is not to parse more carefully, it is to refuse: nothing
    legitimate arrives with a control character in it, and a url with a space
    in it is either a typo or an attack.
    """
    return ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F


def normalized_public_url(raw: str | None) -> str | None:
    """The trimmed url if it is one we will hand to a browser, else None."""
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None

    # Before any parsing, because the parser and the raw string must not be
    # allowed to disagree about what this text says.
    if any(_is_forbidden_character(ch) for ch in value):
        return None

    parts = urlsplit(value)
    if not parts.scheme:
        # `instagram.com/p/abc` is the commonest thing a creator actually
        # pastes, and refusing it teaches them nothing except that the field is
        # fussy. One retry with https:// in front, and ONLY when there was no
        # scheme at all: never as a repair for a scheme that was rejected,
        # which would turn `javascript:alert(1)` into a fetchable url with a
        # host called javascript. A protocol-relative `//evil.com/x` falls out
        # here as None rather than as a working link, which is right: nobody
        # types one on purpose, and its whole point is to inherit a scheme it
        # was never given.
        parts = urlsplit("https://" + value)

    if parts.scheme.lower() not in _ALLOWED_SCHEMES:
        return None
    if not parts.hostname:
        return None

    # Reassembled from what was PARSED rather than returned as typed, so that
    # the value stored is the value the guard actually reasoned about. If the
    # two ever differ, the stored one is the one a browser follows.
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc, parts.path, parts.query, parts.fragment)
    )


def is_public_host(host: str | None) -> bool:
    """False for a loopback, private, link-local or otherwise non-routable literal."""
    if not host:
        return False
    # A trailing dot is a fully qualified name and means the same host, so
    # `localhost.` must not slip past the name below. Brackets are how an IPv6
    # literal is written in a url; urlsplit's .hostname already removes them,
    # but this function is public and should not assume its caller went through
    # that path.
    name = host.strip().lower().rstrip(".")
    if name.startswith("[") and name.endswith("]"):
        name = name[1:-1]
    if not name:
        return False
    if name == _LOOPBACK_NAME:
        return False

    try:
        address = ipaddress.ip_address(name)
    except ValueError:
        # Not an address literal, so it is a NAME.
        #
        # THE HONEST LIMIT OF THIS FUNCTION, stated here rather than left for a
        # reader to assume: a name that resolves to 127.0.0.1, or to the cloud
        # metadata address 169.254.169.254, returns True from this call.
        # Nothing here performs a lookup, and adding one would not close the
        # hole anyway, because DNS is free to answer differently between the
        # check and the connection that follows it. Closing it properly means
        # pinning the resolved address AT CONNECT TIME, through a transport
        # that refuses to dial a private address, and that is a follow-up
        # rather than something this function is quietly claiming to do.
        return True

    return not (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )

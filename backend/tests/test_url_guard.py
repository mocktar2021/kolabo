"""The url guard, as a table of things people actually send.

Pure functions, no database, no app, no request: text in, text or None out.
That is the whole reason app/core/urls.py is a module of its own rather than a
few lines inside submit(), and it is what lets this file grow every time
somebody finds a payload it should have refused, or a link it should not have.

The refusals below are not hypothetical shapes. `link_url` on a submission is
rendered as a live link by both clients, in front of a brand who is signed in
and one button away from releasing escrow, so `javascript:` in that column is a
click away from running as them. The case, whitespace and scheme-less variants
are here because a filter that only knows the lowercase spelling of a thing is
a filter somebody has already got past.
"""
import pytest

from app.core.urls import MAX_URL_CHARS, is_public_host, normalized_public_url

# (what arrives, what we store). None means refused.
CASES = [
    # The reason this module exists. Both clients render link_url as an anchor.
    ("javascript:alert(1)", None),
    # Case is not a disguise: urlsplit lowercases the scheme and so do we.
    ("JavaScript:alert(1)", None),
    ("JAVASCRIPT:alert(1)", None),
    # A whole document, inline, on our origin as far as the browser is told.
    ("data:text/html,x", None),
    # Reaches for the machine, not the web.
    ("file:///etc/passwd", None),
    # Not dangerous, simply not a web address. A link field is for links.
    ("mailto:ama@example.com", None),
    # SPLICED CONTROL CHARACTERS, the classic scheme-filter bypass: urlsplit
    # strips tab, carriage return and newline before parsing, so a check on the
    # raw text and a check on the parse can be made to disagree. Refused before
    # anything is parsed, which is why they cannot.
    ("java\nscript:alert(1)", None),
    ("java\tscript:alert(1)", None),
    ("java\rscript:alert(1)", None),
    ("https://example.com/a\nb", None),
    # A space inside a url is a typo or an attack, never a link.
    ("https://example.com/a b", None),
    # THE COMMONEST REAL INPUT. A creator copies what the app showed them,
    # which has no scheme on it. Refusing this would teach nothing except that
    # the field is fussy, so it gets exactly one retry with https:// in front.
    ("instagram.com/p/abc", "https://instagram.com/p/abc"),
    ("www.tiktok.com/@ama/video/7", "https://www.tiktok.com/@ama/video/7"),
    # An ordinary link survives untouched, query and fragment included.
    ("https://instagram.com/p/abc123", "https://instagram.com/p/abc123"),
    ("http://example.com/a?b=c#d", "http://example.com/a?b=c#d"),
    # Trimmed at the edges, because a pasted link usually arrives with a space.
    ("  https://example.com/x  ", "https://example.com/x"),
    # Protocol-relative. Its entire purpose is to inherit a scheme it was never
    # given, and the https:// retry does not rescue it: there is no scheme
    # missing here that we can honestly supply.
    ("//evil.com/x", None),
    # Nothing to store, and nothing to complain about either. The caller's
    # "a submission needs a link or a file" rule is what speaks up.
    ("", None),
    ("   ", None),
    (None, None),
    # A scheme with no host behind it.
    ("https://", None),
    ("https:///path", None),
]


@pytest.mark.parametrize("raw,expected", CASES)
def test_normalized_public_url(raw, expected):
    assert normalized_public_url(raw) == expected


def test_the_ceiling_is_the_callers_job_not_the_guards():
    """A 3000 character link is refused by submit(), NOT here, and that is
    deliberate: this function's only answer is None, and answering None to a
    link that is merely too long would tell the creator their link is
    malformed. The caller measures it first so its refusal can name the real
    problem and carry the number for the translated sentence."""
    long_url = "https://example.com/" + ("a" * 3000)
    assert len(long_url) > MAX_URL_CHARS
    assert normalized_public_url(long_url) == long_url


HOSTS = [
    # Loopback, the obvious one.
    ("127.0.0.1", False),
    ("::1", False),
    ("[::1]", False),
    ("localhost", False),
    # A trailing dot is the same host fully qualified.
    ("localhost.", False),
    # RFC1918. A url that reaches these reaches something inside our network
    # that was never meant to answer the internet.
    ("10.0.0.1", False),
    ("192.168.1.1", False),
    ("172.16.0.5", False),
    # Link-local, and the cloud metadata address in particular: the single
    # most valuable thing a server-side fetch can be pointed at.
    ("169.254.169.254", False),
    ("fe80::1", False),
    # Unspecified, multicast, and one from the reserved space.
    ("0.0.0.0", False),
    ("224.0.0.1", False),
    ("240.0.0.1", False),
    # Nothing at all is not a public host either.
    (None, False),
    ("", False),
    # An ordinary name, and an ordinary public literal.
    ("instagram.com", True),
    ("graph.facebook.com", True),
    ("8.8.8.8", True),
]


@pytest.mark.parametrize("host,expected", HOSTS)
def test_is_public_host(host, expected):
    assert is_public_host(host) is expected


def test_a_name_is_trusted_because_nothing_here_resolves_it():
    """The honest limit, asserted so nobody reads this guard as more than it is.

    A hostname that resolves to a loopback or metadata address passes. Closing
    that means pinning the resolved address at connect time, which is a
    follow-up and not something this function pretends to do. The test states
    the gap rather than leaving the next reader to discover it.
    """
    assert is_public_host("localtest.me") is True

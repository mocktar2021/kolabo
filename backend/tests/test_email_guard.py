"""The email guard, as a table of things people actually type.

Pure functions, no database, no app, no request: text in, text or None out.
That is the whole reason app/core/emails.py is a module of its own rather than
a few lines inside update_me, and it is what lets this file grow every time
somebody finds a spelling it should have refused, or an address it should not
have.

The refusals are not hypothetical. This value is about to carry a UNIQUE index
and it is the address notifications are sent to, so two spellings of one
address are two accounts, and a value with a newline in it is a header
somebody else wrote. The case rows are the ones worth reading twice: the domain
is normalised because it is case insensitive by standard, and the local part is
left alone because it is not, which is a rule almost every provider ignores and
we therefore cannot.
"""
import pytest

from app.core.emails import MAX_EMAIL_CHARS, normalized_email

# (what arrives, what we store). None means refused.
CASES = [
    # Nothing at all. The caller's "send a phone, an email or a password" rule
    # is what speaks up about an empty patch, not this function.
    (None, None),
    ("", None),
    ("   ", None),
    ("\t\n ", None),
    # An ordinary address survives untouched, plus addressing tricks people
    # really use to file their mail.
    ("ama@example.com", "ama@example.com"),
    ("ama+kolabo@example.com", "ama+kolabo@example.com"),
    ("ama.kouassi@sub.example.co.uk", "ama.kouassi@sub.example.co.uk"),
    # Trimmed at the edges, because a pasted address arrives with a space on it
    # more often than not.
    ("  ama@example.com  ", "ama@example.com"),
    # THE CASE RULE, both halves of it. The domain is lowercased because it is
    # case insensitive by standard; the local part is preserved because RFC
    # 5321 leaves it to the receiving host, and lowercasing it here would
    # quietly rewrite the address of everybody whose provider is not one of the
    # big ones that happen not to care.
    ("ama@EXAMPLE.COM", "ama@example.com"),
    ("ama@Example.Com", "ama@example.com"),
    ("Ama.K@Example.COM", "Ama.K@example.com"),
    ("AMA@EXAMPLE.COM", "AMA@example.com"),
    # SPLICED CONTROL CHARACTERS. A subject line is a mail header and a header
    # ends at a newline, so a stored address carrying one is the start of a
    # header somebody else wrote. Refused before anything is parsed, so the raw
    # text and the parser cannot be made to disagree about what this says.
    ("ama\n@example.com", None),
    ("ama@example.com\nbcc: someone@evil.test", None),
    ("ama\t@example.com", None),
    ("ama\r@example.com", None),
    ("ama@exam ple.com", None),
    # A space inside an address is a typo or an attack, never an address, and
    # the display-name spelling is not one either: this column stores a
    # mailbox, not a To: header.
    ("ama @example.com", None),
    ("Ama K <ama@example.com>", None),
    # Not an address at all. The commonest of these is somebody typing their
    # name, or their phone number, into the wrong field.
    ("notanemail", None),
    ("+22990000001", None),
    # A local part with nothing behind the @, and a domain with nothing in
    # front of it.
    ("ama@", None),
    ("@example.com", None),
    ("ama@@example.com", None),
    # A bare hostname with no dot in it. Resolvable on somebody's LAN, never a
    # public mailbox, and there is no honest repair to make to it.
    ("ama@localhost", None),
]


@pytest.mark.parametrize("raw,expected", CASES)
def test_normalized_email(raw, expected):
    assert normalized_email(raw) == expected


def test_an_address_longer_than_the_path_limit_is_refused():
    """254 is the RFC 5321 forward path limit, so nothing longer could be
    delivered to even if we stored it. Refused here rather than by the caller,
    unlike MAX_URL_CHARS: a 3000 character link is one a creator really typed
    and deserves its own sentence, while a 300 character address is not a
    mistake anybody makes."""
    long_local = "a" * (MAX_EMAIL_CHARS - len("@example.com") + 1)
    too_long = f"{long_local}@example.com"
    assert len(too_long) > MAX_EMAIL_CHARS
    assert normalized_email(too_long) is None


def test_nothing_here_asks_dns_anything():
    """The honest limit, asserted so nobody reads this guard as more than it is.

    A domain that has never had an MX record passes, because deliverability
    checks are off: a DNS lookup on the signup path is a latency and an
    availability dependency, and what it buys is a guess the first real send
    answers properly. A stored address is a CLAIM until there is a confirmation
    flow behind it, and this test states that rather than leaving the next
    reader to discover it.
    """
    assert normalized_email("ama@no-mx-here.example") == "ama@no-mx-here.example"

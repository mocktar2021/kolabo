"""An email address somebody typed, checked before anything is stored under it.

WHY THIS EXISTS. The email address IS the login identity. Registration,
verification, login and password reset all resolve an account by it, and
notifications/service.py addresses every message it sends to it. So a
malformed value here is not a validation error in the ordinary sense: it is an
account nobody can sign in to, and a notification that silently goes nowhere.
The column carries a unique index as well, so two spellings of one address
would be two accounts, or a 500 on the insert that discovers they are not.

Both of those are arguments for deciding what an address IS exactly once. The
rule is a paragraph long, which is precisely why it must not be written twice:
two copies of a normalisation rule drift, and the drift is only ever noticed on
the copy that stayed strict. It sits in core/ for the reason urls.py and
contact_guard sit there — auth does not own the definition of an email address,
it merely obeys it.

WHAT THIS IS NOT. It is not evidence that anybody reads the mailbox. Nothing
here asks DNS whether the domain accepts mail (the comment on that decision is
below, in the function), and nothing anywhere yet sends a confirmation link, so
a stored address is a CLAIM and every caller should read it as one until there
is a verification flow behind it. This module refuses the shapes that are never
an address. Deciding whether an address is really theirs is a different job
with a different budget.

ABSENT AND INVALID COME BACK THE SAME, and that is a choice rather than an
oversight: most callers want one branch, not two, and a pair of sentinels to
keep straight is how the wrong one gets checked. A caller that does need them
apart asks the cheaper question of the RAW TEXT before calling: `raw is None or
not raw.strip()` is "nobody gave me one", and anything else that answers None
is "that is not one". One strip() is the whole difference.
"""
from email_validator import EmailNotValidError, validate_email

# The ceiling on an address anybody stores. 254 is the RFC 5321 limit on the
# forward path: the Path production is capped at 256 characters and the angle
# brackets around the address are two of them, so 254 is what the address
# itself may be. Every mail server on the way enforces something like it, so an
# address longer than this is one nothing could deliver to even if we stored it.
#
# Checked here rather than left to the caller, unlike MAX_URL_CHARS in urls.py,
# and for a reason worth stating: a url that is too long is a link a creator
# genuinely typed and deserves its own refusal naming the number. An address of
# 300 characters is not a typo anybody makes. It is one answer, so it gets the
# one answer this function has.
MAX_EMAIL_CHARS = 254


def normalized_email(raw: str | None) -> str | None:
    """The address as we will store it, or None if it is not one.

    In order: nothing at all, too long, characters that never belong inside an
    address, then the library's opinion, then the one normalisation we perform
    ourselves, which is to LOWERCASE THE WHOLE ADDRESS. Cheap and certain
    first, so the expensive parse only ever sees text that is already the right
    shape.

    THE LOCAL PART IS FORMALLY CASE SENSITIVE AND THIS DELIBERATELY IGNORES
    THAT, which is a reversal of what this module did when it was written and
    is worth stating rather than leaving a later reader to "fix" back. RFC 5321
    leaves the local part to the receiving host, but essentially no consumer
    mail provider treats it as significant. Meanwhile the address is now the
    login key: somebody who registers as Kofi@gmail.com and later types
    kofi@gmail.com gets told their credentials are wrong, about a spelling
    their own provider considers the same mailbox. In these markets that is a
    support ticket at best and a lost signup at worst, and the RFC purity is
    not worth either of them.

    The trade is not symmetric, which is what settles it. A user whose host
    really does distinguish case still receives mail at the lowercased
    spelling from every large provider they correspond with, because those
    providers fold case on the way out anyway. A user locked out of their own
    account has no workaround at all.
    """
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None

    if len(value) > MAX_EMAIL_CHARS:
        return None

    # Refused before the parser is asked anything, for the reason urls.py
    # sets out at length about the same class of character: A TAB OR A NEWLINE
    # SPLICED INTO A STRING is how a check on the raw text and a check on the
    # parse are made to disagree about what that string says, and two readers
    # disagreeing is exactly the gap these payloads are built for. An address
    # has a second reason of its own, which is that it is written into a mail
    # header, where a newline is not a typo, it is the start of another header.
    #
    # The same predicate is spelled out in urls.py rather than shared with it.
    # Four lines do not earn a module, and a url and an address are allowed to
    # disagree about their legal characters later without one of them silently
    # dragging the other along.
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        return None

    try:
        # DELIVERABILITY CHECKS OFF, deliberately. Left on, this call resolves
        # the domain's MX records, which puts a DNS LOOKUP ON THE PATH OF A
        # SIGNUP: a latency nobody budgeted for, and worse, an availability
        # dependency. A slow resolver turns "save my email" into a timeout, and
        # a domain having a bad afternoon into "that address does not look
        # right", which is a sentence we would be saying about a perfectly good
        # address. What the lookup buys is a guess about whether mail can be
        # delivered; the first real send answers that properly, and answers it
        # about the mailbox rather than about the zone.
        parsed = validate_email(value, check_deliverability=False)
    except EmailNotValidError:
        # The library's own reason is not passed on. It is written for a
        # developer ("The part after the @-sign is not valid") and the caller
        # already has one sentence of its own to say, in two languages, to
        # somebody who mistyped their address. See auth_email_invalid.
        return None

    # ONE SPELLING PER MAILBOX, domain and local part alike. See the docstring
    # for why the local part is folded despite the standard.
    #
    # The domain half needs no argument: it is case insensitive by standard,
    # and validate_email has already lowercased and IDNA-normalised it.
    # .lower() on it here is what makes that visible in this module rather
    # than a property a reader has to go and confirm somewhere else.
    #
    # This is also what makes the unique index on users.email mean one account
    # per mailbox rather than one account per SPELLING of a mailbox. Two rows
    # holding Kofi@gmail.com and kofi@gmail.com would not collide on it, and
    # the second of them is a duplicate account nobody can explain to the
    # person who owns both.
    return f"{parsed.local_part.lower()}@{parsed.domain.lower()}"

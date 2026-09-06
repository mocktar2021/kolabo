"""Contact details do not travel through Kolabo.

THE PRODUCT RULE, AND THE HONEST CLAIM ABOUT IT.

Swapping a phone number or an email address is how a deal leaves the platform.
Two people who have each other's WhatsApp can agree the price there, pay there,
and fall out there — and a deal agreed off-platform has no contract, no escrow
and no recourse for either side, on top of carrying no fee. Every other rule in
this codebase points the same way: messaging opens only when a contract does,
negotiation happens in numbered proposal versions rather than in a chat, and a
business reply is a version and not a message. This module applies that rule to
the free-text fields those decisions left behind.

IT IS FRICTION, NOT PREVENTION, and claiming otherwise would be dishonest.
Anyone determined to pass a number can spell it out in words, split it across
two messages, photograph it, or write it in an image caption. A regular
expression will never win that argument and is not trying to. What it stops is
the CASUAL case — the message that ends "here's my number, call me", written by
somebody who was not evading anything and simply reached for the habit — which
is the large majority of them. It also makes the platform's position explicit
at the exact moment somebody is about to leave it, which no amount of terms of
service does.

NEVER SILENTLY REDACT. Every caller refuses the write and says what was found.
An altered message is worse than a refused one: the sender believes they said
something they did not say, the recipient reads a sentence with a hole in it,
and neither of them knows the platform did it. A refusal is at least honest and
is a thing the sender can act on.

FALSE POSITIVES ARE THE WHOLE DESIGN PROBLEM.

A guard that refuses a creator's quote is worse than no guard at all. It does
not merely annoy: it teaches both sides that the platform is broken, and the
next thing they do is take the conversation somewhere that works — which is the
exact outcome this exists to prevent. So the bar is not "catches everything",
it is "never refuses an ordinary sentence about money, dates or paperwork".

This marketplace prices in XOF, so its prose is full of long numbers. All of
these must pass untouched, and all of them are in the test file:

    300000 XOF                  a rate, unseparated
    1 000 000                   an amount, grouped in thousands
    12 000 000 FCFA             a bigger one, with its currency
    45 000 F par post           the same thing said twice in one sentence
    02/08/2026, 02-08-2026      a deadline
    2026-08-15                  the same deadline the other way round
    CT-2026-000123              a contract reference
    REF8829301145               a transfer reference
    250000 abonnés              an audience number

The rules that make that work, in the order they are applied to a run of digits
and separators:

  * BETWEEN 8 AND 15 DIGITS. Shorter is an amount, a quantity or a year; longer
    is not a telephone number anywhere. This alone disposes of 300000 (six),
    1 000 000 (seven) and every audience figure under ten million.

  * NOT A DATE. 02.08.2026 is eight digits grouped in a way that otherwise
    looks exactly like a phone number, so dates are matched first and their
    spans skipped. The date pattern refuses to match when another separator and
    digit follow it, which is what keeps it from eating the front of
    06.12.34.56.78 and declaring it a deadline.

  * NOT GROUPED IN THOUSANDS. This is the load-bearing one. An amount is a
    short lead group and then groups of exactly three (1 000 000, 12 000 000);
    a phone number in this region is groups of two (06 12 34 56 78,
    +229 97 00 00 00). The convention is different enough to separate them, and
    where it is not — a plausible number written in threes — the amount reading
    wins, because refusing a quote costs more than missing a number.

  * NO CURRENCY WORD BESIDE IT. 15000000 FCFA is eight digits, unseparated, and
    passes every rule above. The currency token next to it is what says it is
    money. The window is deliberately narrow (a dozen characters), so "je
    facture 300000 XOF, appelle le 97 00 00 00" still finds the number.

  * NOT GLUED TO LETTERS. CT-2026-000123 and REF8829301145 contain digit runs
    of the right length. They are references, and nobody can dial them. Any run
    whose surrounding token contains a letter is skipped, which covers ids,
    urls and file names in one rule rather than a list of id formats that would
    go stale.

  * AND THEN A SHAPE. It counts as a phone number if it starts with + (an
    international prefix is never an amount), or it is grouped into clusters of
    at most four, or it is a single bare run of 8 to 12 digits. The last of
    those is the loosest and is the deliberate trade: a bare eight-digit number
    with no currency beside it is a Benin mobile far more often than it is
    anything else this product writes.

The email rules are looser because they can afford to be: there is no innocent
reason to write "(at)" between two words. The only care needed is that the
spelled-out form ("name at domain dot com") requires the word "dot" as well as
the word "at" — accepting a literal dot there would flag "available at
kolabo.com", and "meet at the studio" must never be an email address.

WHAT IS NOT HERE. Naming an app is not the offence; handing over the address is.
"I don't really use WhatsApp" and "the signal was bad during the live" are
ordinary sentences and stay ordinary. A channel only counts when it arrives
with a handle, a number, a link, or an explicit invitation to move the
conversation to it.
"""
import re

from fastapi import status

from app.core.errors import AppError

# The kinds. Short, stable strings: they are what find_contact_details returns
# and what the tests assert on. The prose a person reads lives in _WHAT_WAS_FOUND
# so that changing the wording of a refusal is not a change to the API.
EMAIL = "email"
PHONE = "phone"
HANDLE = "handle"

_WHAT_WAS_FOUND = {
    EMAIL: "an email address",
    PHONE: "a phone number",
    HANDLE: "a messaging app handle",
}

# Reported in a fixed order rather than in the order they happen to be found,
# so the same text always produces the same sentence.
_REPORT_ORDER = (EMAIL, PHONE, HANDLE)

# WHAT IS BEING REFUSED, as a closed set of tokens.
#
# `surface` is interpolated into the refusal ("Take it out and send the
# statement again"), so it has to be a word, and until now any caller could
# invent one. That was fine while the sentence was English-only. It stopped
# being fine when the client started composing this refusal in French: an
# unknown surface is a hole in the middle of a French sentence that nothing
# catches, because a surface is not a code and the code-coverage test cannot
# see it.
#
# So the set is closed, written out as literals, and checked from both ends:
# backend/tests/test_error_codes.py asserts every call site passes one of
# these, and web/src/lib/errorMessages.test.ts asserts every one of them has a
# French and an English noun. Adding a fifth surface means adding it here and
# in both languages, and the build says so if you forget.
SURFACES = ("message", "statement", "proposal note", "brief description")


# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------

_PLAIN_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Both halves must contain a letter. Without that, "prix (at) 300000" reads as
# an email address, and a rate with a stray bracket in it is not one.
_LOCAL = r"(?=[A-Za-z0-9._%+-]*[A-Za-z])[A-Za-z0-9._%+-]{2,}"
_DOMAIN = r"(?=[A-Za-z0-9-]*[A-Za-z])[A-Za-z0-9-]{2,}"
_TLD = r"[A-Za-z]{2,}"

_BRACKETED_AT = r"[\(\[\{]\s*(?:at|arobase|@)\s*[\)\]\}]"
_SPELLED_AT = r"\s+(?:at|arobase)\s+"
_BRACKETED_DOT = r"[\(\[\{]\s*(?:dot|point)\s*[\)\]\}]"
_SPELLED_DOT = r"\s+(?:dot|point)\s+"
_WORD_DOT = r"(?:" + _BRACKETED_DOT + r"|" + _SPELLED_DOT + r")"
_ANY_DOT = r"(?:" + _BRACKETED_DOT + r"|" + _SPELLED_DOT + r"|\s*\.\s*)"

# Two forms, and they are allowed different amounts of evidence.
#
# The BRACKETED form needs no domain suffix at all: "ama (at) gmail" is already
# somebody obfuscating an address, because there is no other reason to put a
# word in brackets between two others. Missing the tld is common precisely
# because the writer knows they are hiding something.
#
# The SPELLED form has to be stricter, because " at " is an English preposition
# and a French noun. It therefore requires the dot to be spelled out too. This
# is what keeps "available at kolabo.com" and "meet at the studio" out.
_OBFUSCATED_EMAIL = re.compile(
    "(?:"
    + _LOCAL + r"\s*" + _BRACKETED_AT + r"\s*" + _DOMAIN + r"(?:" + _ANY_DOT + _TLD + r")?"
    + "|"
    + _LOCAL + _SPELLED_AT + _DOMAIN + _WORD_DOT + _TLD
    + ")",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------
# Phone
# --------------------------------------------------------------------------

MIN_PHONE_DIGITS = 8
MAX_PHONE_DIGITS = 15

# A single unseparated run longer than this is a reference number, an order id
# or a timestamp, not something anybody dials.
MAX_BARE_PHONE_DIGITS = 12

# How far either side of a digit run to look for a currency word.
MAX_GROUP_DIGITS = 4
_CURRENCY_WINDOW = 12

# Separators a phone number is written with. Deliberately NOT \s: a newline
# between two unrelated numbers would otherwise splice them into one long run.
# Deliberately not "/" either, which is what keeps 02/08/2026 from ever being a
# candidate in the first place.
#
# The no-break space is written as \u00A0 rather than as the character itself,
# and re reads the escape as that character. A literal one is invisible, and a
# tool that normalises whitespace turns it into an ordinary space without a
# word: this file lost it exactly that way once, and the guard then silently
# stopped matching numbers pasted from a phone. Keep it as the escape.
_SEPARATORS = r"\u00A0 \t.\-()"
_DIGIT_RUN = re.compile(r"\+?\d[\d" + _SEPARATORS + r"]{5,}\d")
_GROUP_SPLIT = re.compile(r"[" + _SEPARATORS + r"]+")

# Dates, both ways round. The lookaround is the important part: without it the
# first eight digits of 06.12.34.56.78 match "day.month.year" and the whole
# number is skipped as a deadline. Refusing to match when another separator and
# digit follow, or when one precedes, means a date only matches when it stands
# on its own — which is the only time it is one.
_DATE = re.compile(
    r"(?<![\d.\-/])"
    r"(?:\d{1,2} *[./\-] *\d{1,2} *[./\-] *\d{2,4}"
    r"|\d{4} *[./\-] *\d{1,2} *[./\-] *\d{1,2})"
    r"(?! *[./\-] *\d)"
)

_CURRENCY = re.compile(
    r"(?:xof|f\s?cfa|fcfa|cfa|eur|euros?|usd|dollars?|ngn|naira|ghs|cedis?|"
    r"francs?|[€$£])",
    re.IGNORECASE,
)

# What counts as "still the same token". Includes the separators an id is built
# from, so CT-2026-000123 is read as one thing rather than as a bare digit run
# that happens to sit next to some letters.
_TOKEN_CHARS = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789+._-/#"
)


def _token_around(text: str, start: int, end: int) -> str:
    """The whole token a digit run sits inside.

    Expanded through the characters ids and urls are built from, so that a run
    can be judged by the company it keeps. A run with a letter anywhere in its
    token is a reference, a filename or a url — never a number to dial.
    """
    i = start
    while i > 0 and text[i - 1] in _TOKEN_CHARS:
        i -= 1
    j = end
    while j < len(text) and text[j] in _TOKEN_CHARS:
        j += 1
    return text[i:j]


def _looks_like_an_amount(groups: list[str], text: str, start: int, end: int) -> bool:
    """Money, not a number somebody can call.

    Two independent tells, either of which is enough.

    THOUSANDS GROUPING. A short lead group followed by groups of exactly three
    is how every amount in this product is written: 1 000 000, 12 000 000. A
    phone number in this region is written in twos. Where the two conventions
    genuinely collide the amount reading wins, and that is the intended bias:
    refusing a creator's quote costs more than missing one phone number.

    A CURRENCY WORD BESIDE IT. 15000000 FCFA is eight unseparated digits and
    passes every other rule. The window is narrow on purpose — a dozen
    characters — so that a sentence which mentions a price AND a number still
    catches the number.
    """
    if len(groups) >= 2 and 1 <= len(groups[0]) <= 3 and all(len(g) == 3 for g in groups[1:]):
        return True
    before = text[max(0, start - _CURRENCY_WINDOW):start]
    after = text[end:end + _CURRENCY_WINDOW]
    return bool(_CURRENCY.search(before) or _CURRENCY.search(after))


def _has_phone_number(text: str) -> bool:
    """Whether any run of digits in the text is a number somebody could ring.

    Written as a scan with explicit rejections rather than as one heroic
    regular expression, because every rejection here is a decision somebody
    will want to read and argue with later, and a regex cannot carry a reason.
    """
    dates = [m.span() for m in _DATE.finditer(text)]
    for match in _DIGIT_RUN.finditer(text):
        start, end = match.span()

        # A deadline, not a number.
        if any(start < date_end and date_start < end for date_start, date_end in dates):
            continue

        # A reference, a url or a filename.
        if any(ch.isalpha() for ch in _token_around(text, start, end)):
            continue

        run = match.group()
        groups = [g for g in _GROUP_SPLIT.split(run.lstrip("+")) if g]
        digits = "".join(groups)
        if not MIN_PHONE_DIGITS <= len(digits) <= MAX_PHONE_DIGITS:
            continue

        # An international prefix settles it: no amount is ever written with a
        # leading +, so the amount tests are skipped rather than risked.
        international = run.startswith("+")
        if not international and _looks_like_an_amount(groups, text, start, end):
            continue

        grouped = len(groups) >= 2 and max(len(g) for g in groups) <= MAX_GROUP_DIGITS
        bare = len(groups) == 1 and len(digits) <= MAX_BARE_PHONE_DIGITS
        if international or grouped or bare:
            return True
    return False


# --------------------------------------------------------------------------
# Messaging handles
# --------------------------------------------------------------------------

# Naming an app is not the offence. "I don't really use WhatsApp" and "the
# signal was bad during the live" are ordinary sentences, and a guard that
# refused them would be refusing people for talking about their work. A channel
# only counts when it arrives WITH an address, or with an explicit invitation
# to continue somewhere else.
_CHANNEL = (
    r"(?:whats\s?app|wa\.me|telegram|t\.me|m\.me|messenger|signal|viber|"
    r"snapchat|skype|imo|botim)"
)

_CHANNEL_LINK = re.compile(r"\b(?:wa\.me|t\.me|m\.me)/\S+", re.IGNORECASE)

# "telegram: @ama_k", "whatsapp 97 00 00 00", "Signal +229 97 00 00 00".
_CHANNEL_WITH_ADDRESS = re.compile(
    r"\b" + _CHANNEL + r"\s*(?:me|moi|us|nous)?\s*[:,\-–—]?\s*"
    r"(?:on|sur|au|at|via|à|a)?\s*[:,\-–—]?\s*"
    r"(?:\+?\d[\d \t.\-]{5,}\d|@[A-Za-z0-9_.]{3,})",
    re.IGNORECASE,
)

# "whatsapp me", "telegram moi".
_CHANNEL_ME = re.compile(r"\b" + _CHANNEL + r"[\s\-]+(?:me|moi|nous|us)\b", re.IGNORECASE)

# "écris-moi sur WhatsApp", "on peut continuer sur Signal", "add me on Telegram".
# The connector is required: without it "le message signal" would match, and a
# noun is not an invitation.
_MOVE_VERB = (
    r"(?:écris|ecris|contact(?:e|ez|er)?|join(?:s|dre)?|ajoute|add|ping|dm|"
    r"appelle|call|text|reach|talk|chat|move|switch|message|"
    r"(?:parl|discut|continu|pass|bascul)(?:e|er|ez|ons|era|erons|ent)?)"
)
_MOVE_TO_CHANNEL = re.compile(
    _MOVE_VERB
    + r"[\s\-]+(?:moi|me|us|nous|en|ça|ca)?[\s\-]*"
    r"(?:sur|on|via|au|to|à|a)[\s\-]*\b" + _CHANNEL,
    re.IGNORECASE,
)


def _has_handle(text: str) -> bool:
    return bool(
        _CHANNEL_LINK.search(text)
        or _CHANNEL_WITH_ADDRESS.search(text)
        or _CHANNEL_ME.search(text)
        or _MOVE_TO_CHANNEL.search(text)
    )


# --------------------------------------------------------------------------
# The public surface
# --------------------------------------------------------------------------


def find_contact_details(text: str | None) -> list[str]:
    """Which kinds of contact detail a string contains.

    Pure. No database, no request, no settings, no side effects — text in, a
    list of kinds out, in a fixed order. That is deliberate and is what makes
    the interesting half of this feature testable without standing anything up:
    the false-positive block in test_contact_guard.py is a list of strings and
    an assertion, and it can grow every time somebody finds a sentence this
    refuses that it should not.

    Returns an empty list for None and for empty strings, so callers with
    optional fields need no None check of their own.
    """
    if not text:
        return []
    found = set()
    if _PLAIN_EMAIL.search(text) or _OBFUSCATED_EMAIL.search(text):
        found.add(EMAIL)
    if _has_phone_number(text):
        found.add(PHONE)
    if _has_handle(text):
        found.add(HANDLE)
    return [kind for kind in _REPORT_ORDER if kind in found]


def contact_details_detail(kinds: list[str], surface: str) -> str:
    """The refusal, in the words the person who wrote the text will read.

    It names WHAT was found, because "this was rejected" without a reason is a
    dead end — the writer has to guess which part of their message was the
    problem, and the usual guess is "all of it".

    It says the exchange stays on Kolabo AND why, because the rule only sounds
    arbitrary until somebody explains that the contract and the escrow are what
    they would be giving up.

    It says nothing was saved and nothing was edited. That is the promise this
    whole module rests on, and the moment to make it is the moment somebody is
    wondering whether half their message went out.
    """
    names = [_WHAT_WAS_FOUND[kind] for kind in kinds]
    if len(names) == 1:
        what = names[0]
    else:
        what = ", ".join(names[:-1]) + " and " + names[-1]
    return (
        f"This {surface} looks like it contains {what}. Kolabo keeps the "
        "conversation, the contract and the money in one place: a deal agreed "
        "elsewhere has no contract and no escrow behind it, so neither side has "
        f"any recourse if it goes wrong. Take it out and send the {surface} "
        "again. Nothing was saved and nothing was edited."
    )


def check_no_contact_details(text: str | None, surface: str) -> None:
    """Refuse the write if the text carries contact details.

    400 rather than 422: this is a rule about what a field may contain, not
    about its type or shape, and a client can act on the sentence. `surface` is
    the noun the message will use for the thing being refused, and it must be
    one of SURFACES above — so one wording serves every call site, they cannot
    drift apart, and the client has a French noun to put in its own sentence.
    """
    kinds = find_contact_details(text)
    if kinds:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="contact_details_found",
            detail=contact_details_detail(kinds, surface),
            # The KINDS and the SURFACE, not the finished sentence. Both are
            # stable tokens the client turns into its own nouns and joins with
            # its own "and" — French does not put a list together the way
            # English does, and a sentence assembled here could only ever be
            # assembled in one language.
            #
            # This is the first refusal whose values are not numbers, and it is
            # why errorMessages.ts grew a per-code prepare step: a value that
            # is itself a word needs translating before it is interpolated.
            values={"kinds": kinds, "surface": surface},
        )

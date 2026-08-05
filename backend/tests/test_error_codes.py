"""Refusals that name themselves, and a migration that cannot slide backwards.

The API says "no" 200-odd times across 25 files, always as an English sentence
in `detail`, and the web app renders that sentence verbatim. So the French half
of a bilingual product is bilingual right up until something goes wrong.
app/core/errors.py adds a stable `code` beside the English, and the client
renders its own sentence from it.

Two hundred raises do not move in one commit, so this file exists to make the
move MONOTONIC. It keeps a list of the modules that have been converted, and
asserts that those modules contain no bare `raise HTTPException` any more. A
converted module can therefore never quietly grow an un-coded refusal — the
next person to add one to deliverables/service.py gets a red build naming the
line, rather than shipping an English-only error into a French screen and
nobody noticing for a month.

The other half of the guarantee lives on the frontend:
web/src/lib/errorMessages.test.ts reads these same sources and fails if a code
has no French and English sentence. Together: every converted refusal has a
code, and every code has both languages. Neither test is much use without the
other.
"""
import ast
import re
from pathlib import Path

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.core import contact_guard
from app.core.errors import AppError, app_error_handler

APP = Path(__file__).resolve().parents[1] / "app"

# ------------------------------------------------------------------ #
# THE LIST IS GONE, and that is the point of this commit.
#
# For six PRs this held the modules converted so far, and asserted only those
# were clean — a ratchet, so the migration could not slide backwards while it
# was half done. It is not half done any more: every `raise HTTPException` in
# `app/` now carries a code, so the honest assertion is about the whole tree
# rather than a list somebody has to remember to extend.
#
# A file that genuinely needs a bare HTTPException goes in ALLOWED below, with
# a reason. It is empty, and a pull request that adds to it is asking for a
# conversation, which is exactly the friction it should have.
ALLOWED: set[str] = set()

BARE_RAISE = re.compile(r"^\s*raise HTTPException\(", re.MULTILINE)


def _app_error_calls(source: str) -> list[ast.Call]:
    """Every AppError(...) call in a module, found by PARSING it.

    This was a regular expression — "is there a `code=` anywhere in this file
    that is not followed by a quote" — and it was wrong in a way worth
    recording, because it is the same mistake this whole migration exists to
    stop people making. auth/service.py builds an OTP challenge with
    `OtpChallenge(code=code, ...)`, where `code` means a six-digit SMS code and
    has nothing to do with error codes at all. The regex flagged it, because a
    regex was answering a question nobody asked: it looked for a SUSPICIOUS
    STRING anywhere in the file, when the invariant is about AppError calls
    specifically.

    An AST walk asks the real question and cannot be fooled by a variable that
    happens to be spelled `code`, by prose in a docstring, or by a `code=` in
    an unrelated constructor. It costs one import.
    """
    return [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "AppError"
    ]


def test_no_refusal_anywhere_is_missing_its_code():
    """Every "no" this API says names itself.

    216 raises across 25 files began this migration; this is the line that
    says it finished. A new endpoint that reaches for HTTPException out of
    habit fails here, naming the file and the line, rather than shipping an
    English-only sentence into a French screen.
    """
    offenders = []
    for path in _python_files():
        relative = str(path.relative_to(APP))
        if relative in ALLOWED:
            continue
        source = path.read_text(encoding="utf-8")
        for m in BARE_RAISE.finditer(source):
            offenders.append(f"{relative}:{source[:m.start()].count(chr(10)) + 1}")
    assert offenders == [], (
        "Raise AppError with a code instead, and give the code a French and an "
        "English sentence in web/src/lib/errorMessages.ts:\n" + "\n".join(offenders)
    )


def test_every_code_is_a_plain_literal():
    """No f-strings, no variables, no helper that assembles one.

    A code built at runtime cannot be read out of the source, which means
    web/src/lib/errorMessages.test.ts cannot check it has a translation, which
    means it can ship untranslated — the exact hole this pair of tests exists
    to close. The keyword-only `*` in AppError.__init__ already forces the
    `code=` spelling; this forces the value beside it to be readable too, and
    is what makes the frontend's regex trustworthy rather than hopeful.
    """
    unreadable = []
    total = 0
    for path in _python_files():
        relative = str(path.relative_to(APP))
        for call in _app_error_calls(path.read_text(encoding="utf-8")):
            total += 1
            keyword = next((k for k in call.keywords if k.arg == "code"), None)
            if keyword is None:
                unreadable.append(f"{relative}:{call.lineno} passes no code=")
            elif not (isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str)):
                unreadable.append(f"{relative}:{call.lineno} builds its code instead of writing one")
    assert total > 200, f"only {total} AppError calls found — has app/ moved?"
    assert unreadable == [], "\n".join(unreadable)


# --------------------------------------------------------------------------
# The contact guard's surface
# --------------------------------------------------------------------------

CALL_SITE = re.compile(r'check_no_contact_details\(\s*[^,]+,\s*"([^"]*)"\s*\)')


def _python_files():
    return sorted(p for p in APP.rglob("*.py") if "__pycache__" not in p.parts)


def test_every_surface_is_one_of_the_declared_ones():
    """`surface` is a token the CLIENT translates, not a word the backend picks.

    It is interpolated into the refusal — "send the statement again" — and the
    French sentence gets its noun from apiError.surface_<token>. So an
    invented surface is not a missing sentence that falls back to English, it
    is a HOLE IN THE MIDDLE of a French one, and nothing catches it: a surface
    is not a code, so the frontend's code-coverage test never sees it.

    Hence the closed set, checked from both ends. This is the backend end.
    web/src/lib/errorMessages.test.ts is the other, asserting each of these
    has a French and an English noun.
    """
    unknown = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        for match in CALL_SITE.finditer(source):
            if match.group(1) not in contact_guard.SURFACES:
                line = source[: match.start()].count(chr(10)) + 1
                unknown.append(f"{path.relative_to(APP)}:{line} passes {match.group(1)!r}")
    assert unknown == [], (
        "Add the surface to contact_guard.SURFACES and give it a noun in both "
        "languages (web/src/lib/errorMessages.ts), or reuse one:\n" + "\n".join(unknown)
    )


def test_the_declared_surfaces_are_all_used():
    """A surface nobody passes is a translation nobody reads. Not a failure
    worth blocking a build over in the other direction — a body can be written
    ahead of its caller — but a set that only ever grows is a set that rots."""
    used = {
        m.group(1)
        for path in _python_files()
        for m in CALL_SITE.finditer(path.read_text(encoding="utf-8"))
    }
    assert set(contact_guard.SURFACES) == used


PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
TEMPLATE = re.compile(r'^  ([a-z][a-z0-9_]*): "((?:[^"\\]|\\.)*)",?$', re.MULTILINE)

MESSAGES_TS = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "errorMessages.ts"

# Codes whose interpolation values are BUILT ON THE CLIENT rather than sent by
# the backend, so the check below cannot match them up and should not try.
# Today that is the contact guard: it sends `kinds` and `surface` as tokens,
# and errorMessages.ts composes {{what}} and {{surface}} from them (see the
# PREPARE map there). One entry, and it has to earn its place.
CLIENT_COMPOSED = {"contact_details_found"}


def _templates() -> dict[str, set[str]]:
    """Every code in errorMessages.ts, mapped to the placeholders it asks for.

    Reading TypeScript from a Python test is the mirror image of what
    web/src/lib/errorMessages.test.ts does to these sources, and for the same
    reason: the seam has one side in each language, so one of them has to look
    across it.
    """
    source = MESSAGES_TS.read_text(encoding="utf-8")
    wanted: dict[str, set[str]] = {}
    for code, template in TEMPLATE.findall(source):
        wanted.setdefault(code, set()).update(PLACEHOLDER.findall(template))
    return wanted


def _values_sent() -> dict[str, set[str]]:
    """Every code the backend raises, mapped to the value keys it sends with it.

    The UNION across call sites, not the intersection: two sites raising the
    same code may legitimately send different extras, and a placeholder is
    satisfied if some site provides it. A stricter rule would be a better
    test, and would also fail on `escrow_not_found`, which several call sites
    raise with nothing at all.
    """
    sent: dict[str, set[str]] = {}
    for path in _python_files():
        for call in _app_error_calls(path.read_text(encoding="utf-8")):
            code = next((k.value.value for k in call.keywords
                         if k.arg == "code" and isinstance(k.value, ast.Constant)), None)
            if code is None:
                continue
            keys = sent.setdefault(code, set())
            values = next((k.value for k in call.keywords if k.arg == "values"), None)
            if isinstance(values, ast.Dict):
                keys.update(k.value for k in values.keys
                            if isinstance(k, ast.Constant) and isinstance(k.value, str))
    return sent


def test_every_placeholder_has_a_value_behind_it():
    """A {{placeholder}} nobody fills is a hole in a sentence.

    THIS IS THE CHECK THAT WAS MISSING. `campaigns/cart.py` briefly sent
    `values={"index": ...}` down one branch while its sentence interpolated
    `{{cart_index}}`; both sides were internally consistent and neither test
    suite could see the mismatch, because one asserted the code had a
    translation and the other asserted the translation had a code. Nothing
    asserted the sentence could actually be rendered. It was caught by
    reading the diff, which is not a mechanism.

    Only codes the backend actually raises are checked — a body written ahead
    of its call site is fine and deliberate, and has no values to compare
    against yet.
    """
    templates = _templates()
    sent = _values_sent()
    holes = []
    for code, keys in sent.items():
        if code in CLIENT_COMPOSED:
            continue
        missing = templates.get(code, set()) - keys
        if missing:
            holes.append(f"{code} interpolates {sorted(missing)} but no call site sends it")
    assert holes == [], "\n".join(holes)


def test_the_templates_were_actually_found():
    """A regex that silently matched nothing would make the test above pass
    over an empty set — the same failure the frontend suite guards against by
    asserting it can see the backend at all."""
    templates = _templates()
    assert len(templates) > 100, f"only {len(templates)} templates parsed out of {MESSAGES_TS}"
    assert "deliverable_note_too_long" in templates
    assert templates["deliverable_note_too_long"] == {"max"}


def test_the_whole_app_still_imports():
    """AppError is raised from a module main.py imports; a circular import here
    would only show up when the server boots, which is not where anybody wants
    to find it."""
    import app.main  # noqa: F401


@pytest.fixture()
def client():
    """The REAL handler on a throwaway app.

    Registered from app.core.errors rather than re-declared here on purpose: a
    handler that merely resembles the production one is a test that stays green
    while the wiring is wrong.
    """
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)

    @app.get("/plain")
    def plain():
        raise AppError(status.HTTP_400_BAD_REQUEST, code="a_rule", detail="A sentence.")

    @app.get("/valued")
    def valued():
        raise AppError(
            status.HTTP_409_CONFLICT,
            code="another_rule",
            detail="At most 10.",
            values={"max": 10},
        )

    return TestClient(app, raise_server_exceptions=False)


def test_the_code_reaches_the_client(client):
    r = client.get("/plain")
    assert r.status_code == 400
    assert r.json() == {"detail": "A sentence.", "code": "a_rule"}


def test_detail_is_still_a_string_in_the_old_place(client):
    """The whole migration rests on this. `detail` keeps its name, its position
    and its type, so a client that has never heard of `code` — the mobile app,
    an API consumer, a log line — reads this response exactly as it always did
    and shows the English."""
    body = client.get("/valued").json()
    assert isinstance(body["detail"], str)
    assert body["detail"] == "At most 10."


def test_values_travel_as_data(client):
    """The ceiling is a number, not a number baked into two sentences that then
    drift apart from the constant and from each other."""
    assert client.get("/valued").json()["values"] == {"max": 10}


def test_no_values_means_no_empty_object(client):
    """An empty {} in a payload invites a reader to wonder what was meant to be
    in it."""
    assert "values" not in client.get("/plain").json()

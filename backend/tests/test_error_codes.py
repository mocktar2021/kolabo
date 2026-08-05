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

# Modules whose every refusal now carries a code. ADD TO THIS LIST as each one
# is converted — that is the whole ratchet. Removing an entry to make a build
# go green is undoing the migration, not fixing the test.
CONVERTED = [
    "core/contact_guard.py",
    "modules/deliverables/service.py",
    "modules/payments/service.py",
    "modules/payments/disputes.py",
    "modules/payments/resolution.py",
    "modules/contracts/service.py",
    "modules/contracts/cancellation.py",
    "modules/auth/service.py",
    "modules/auth/deps.py",
    "modules/auth/account.py",
    "modules/profiles/service.py",
]

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


@pytest.mark.parametrize("relative", CONVERTED)
def test_a_converted_module_has_no_bare_refusals(relative):
    source = (APP / relative).read_text(encoding="utf-8")
    lines = [
        f"{relative}:{source[:m.start()].count(chr(10)) + 1}"
        for m in BARE_RAISE.finditer(source)
    ]
    assert lines == [], (
        "These refusals lost their code — a converted module must raise AppError:\n"
        + "\n".join(lines)
    )


@pytest.mark.parametrize("relative", CONVERTED)
def test_every_code_is_a_plain_literal(relative):
    """No f-strings, no variables, no helper that assembles one.

    A code built at runtime cannot be read out of the source, which means
    web/src/lib/errorMessages.test.ts cannot check it has a translation, which
    means it can ship untranslated — the exact hole this pair of tests exists
    to close. The keyword-only `*` in AppError.__init__ already forces the
    `code=` spelling; this forces the value beside it to be readable too, and
    is what makes the frontend's regex trustworthy rather than hopeful.
    """
    source = (APP / relative).read_text(encoding="utf-8")
    calls = _app_error_calls(source)
    assert calls, f"{relative} is listed as converted but raises no AppError"

    unreadable = []
    for call in calls:
        keyword = next((k for k in call.keywords if k.arg == "code"), None)
        if keyword is None:
            unreadable.append(f"{relative}:{call.lineno} passes no code=")
        elif not (isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str)):
            unreadable.append(f"{relative}:{call.lineno} builds its code instead of writing one")
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

"""A refusal the client can translate.

Every "no" this API says is a sentence written in English — "This proposal is
closed and cannot be answered", "A rejection requires a reason", "Work can only
be submitted on a fully signed contract" — and until now that sentence WAS the
whole answer. The web app renders `detail` verbatim, so a French user hits a
wall of English at exactly the moment they most need to know what to do next.
Half the product is bilingual and the other half is bilingual right up until
something goes wrong, which is the half that matters.

THE FIX IS THE ONE THE BELL ALREADY USES. A notification carries an English
`message` plus a `{key, ...values}` the client renders its own sentence from
(see notifications/models.py). An error now carries an English `detail` plus a
stable `code` and its `values`, and the client does the same thing with it.
The English does not go away and is not a legacy field: it is the fallback for
a code the client has never heard of, it is what an API consumer reading the
docs sees, and it is what turns up in a log where nobody has a `t`.

WHY A SUBCLASS AND NOT A DICT IN `detail`. Making `detail` a dict would have
been fewer lines and would have broken every existing reader at once — the web
app's parseError accepts `detail` only when it is a string, and FastAPI's own
422 handler already puts a different shape there. A new sibling FIELD is
additive: 200-odd un-migrated `raise HTTPException` lines keep working exactly
as they do today, and the migration proceeds one module at a time instead of
in one enormous commit that nobody can review.

WHY `code` IS KEYWORD-ONLY. web/src/lib/errorMessages.test.ts reads these
source files to check that every code the backend can emit has a French and an
English sentence waiting for it. That check works by finding `code="..."`
written out as a literal, so a positional argument — or a code assembled from
an f-string — would be invisible to it and could ship untranslated. The `*` in
the signature below is what makes the readable form the only form. The same
constraint, and the same reasoning, as the notification body keys.
"""
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class AppError(HTTPException):
    """An HTTPException that also says WHICH refusal this is, in one stable word.

    `code` is a snake_case name for the rule that refused, not for the sentence
    that describes it. Rewording the English must never change the code — that
    is the whole point of having one — and two call sites enforcing the same
    rule should share a code even if their prose differs.

    `values` are the interpolation values the translated sentence needs: a
    ceiling, a count, a currency. They travel as data so that "A note is at
    most 4000 characters" can become "Une note fait au plus 4000 caractères"
    without the number being baked into either string.
    """

    def __init__(
        self,
        status_code: int,
        *,
        code: str,
        detail: str,
        values: dict | None = None,
        headers: dict | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code
        self.values = values or {}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Serialise an AppError, keeping the shape every existing client expects.

    `detail` stays exactly where it was and stays a string. `code` and `values`
    are new siblings, so a client that has not been taught about them reads
    this response as an ordinary error and shows the English — which is what
    the mobile app will do until it catches up.

    `values` is omitted rather than sent as {} when there is nothing to
    interpolate: an empty object in a payload invites a reader to wonder what
    was supposed to be in it.

    Lives here rather than in main.py so that a test can register the real
    handler instead of a lookalike. A handler that only resembles the one in
    production is a test that passes while the wiring is wrong.
    """
    body: dict = {"detail": exc.detail, "code": exc.code}
    if exc.values:
        body["values"] = exc.values
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)

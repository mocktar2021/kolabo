/* Reading the Python, so the TypeScript can be checked against it.

   Two things in this app are strings the BACKEND names and the FRONTEND
   writes: notification body keys (notificationBodies.ts) and API error codes
   (errorMessages.ts). Both share a failure mode that is silent by
   construction — the backend starts emitting a name nobody translated, the
   client falls back to English, the build passes, and a French reader quietly
   reads English forever. No type checker can see across that seam, because one
   side of it is Python.

   So the tests read the Python. This module is the shared half of that: find
   the backend sources, and pull the literals out of them.

   IT LIVES IN src/lib RATHER THAN A TEST FOLDER because `web` has no test
   folder — the suites sit beside the code they cover — and because it must be
   typechecked, which `include: ["src"]` gives it for free. Nothing in the app
   imports it, so vite never bundles it and the node:fs import never reaches a
   browser. If something ever does import it, that is a bug in the importer.

   WHAT THE PATTERNS CAN AND CANNOT SEE. Every one of them requires a QUOTED
   LITERAL. A name that is assembled — a variable, an f-string, a helper that
   appends a suffix — is invisible here, and no regex fixes that. Both sides
   are built to keep it visible instead: AppError takes `code` keyword-only,
   the notification call sites write their anonymous-name variants out as pairs
   of literal dicts rather than building `f"{key}_anon"`, and a backend test
   (backend/tests/test_error_codes.py) PARSES each converted module and fails
   any AppError whose code is not a string literal. That AST walk is what makes
   the ERROR_CODE pattern below trustworthy rather than hopeful: this file can
   only find codes that were written down, and something else has to guarantee
   they all are. If a call site ever genuinely needs a computed one, add it to
   a hand-kept list in the test that needs it and say why — do not teach these
   patterns to be clever. */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

/* web/src/lib/ -> repo root -> the backend package. */
export const APP_DIR = fileURLToPath(new URL("../../../backend/app", import.meta.url));
export const MODULES_DIR = join(APP_DIR, "modules");

/* One named backend file, for the checks that are about a specific module
   rather than a sweep — the contact guard's SURFACES, say, which lives in
   app/core and is not a code the pattern scan would ever find. */
export function readAppFile(relative: string): string {
  return readFileSync(join(APP_DIR, relative), "utf8");
}

/* A notification body key: `{"key": "escrow_funded_creator"}` written at the
   call site, or `..._key="order_cart"` passed as a keyword argument (which
   campaigns.service._place_order does, because its three callers say three
   different sentences about the same order).

   Across backend/app these match notify() keys and nothing else: primary_key=,
   ForeignKey(, sort(key= and the prose in the comments all fail them, because
   none is followed immediately by a quoted string. */
export const NOTIFICATION_KEY = /(?:["']key["']:\s*|\b[a-z_]*key=)(?<q>["'])(?<name>[a-z0-9_]+)\k<q>/g;

/* An API error code: `code="deliverable_note_too_long"` in an AppError call.
   The lookbehind is load-bearing — without it this also matches the `code=`
   inside `status_code=`, which is on nearly every line that raises.

   BOTH QUOTE STYLES, which mobile/tests/backendKeys.ts has accepted since it
   was written and this copy did not. Today the backend is uniformly
   double-quoted and both find the same set; the single-quote arm costs
   nothing and means a future `code='x'` cannot slip past this test while
   looking translated. A scanner that cannot see a code reports GREEN over it,
   which is worse than having no scanner at all — and widening can only ever
   find MORE codes, never fewer, so it can never turn a red build green. */
export const ERROR_CODE = /(?<![a-z_])code=(?<q>["'])(?<name>[a-z0-9_]+)\k<q>/g;

/* EVERY PYTHON FILE UNDER app/, and not only the ones under app/modules/.

   This walked modules/ alone, and that was a hole with a name in it: the
   contact guard raises `contact_details_found` from app/core/contact_guard.py,
   so the one refusal a creator meets for putting a phone number into a message
   was invisible to both coverage tests below. It happened to be translated —
   an audit found it by hand and PR #127 wrote the sentences — but nothing made
   it STAY translated, and the next coded refusal raised from core/, from
   jobs/, or from anywhere else outside modules/ would have shipped
   untranslated with a green build standing behind it.

   backend/tests/test_error_codes.py has always walked the whole of app/. These
   scanners now agree with it, which is the only arrangement in which "every
   code has both languages" is a claim rather than a hope. */
export function pythonFiles(dir: string = APP_DIR): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (entry === "__pycache__") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...pythonFiles(full));
    else if (entry.endsWith(".py")) out.push(full);
  }
  return out;
}

/* Every literal the pattern finds, mapped to the files it was found in. The
   filenames are what makes a failure actionable: "order_cart is untranslated"
   is a puzzle, "order_cart, emitted by campaigns/cart.py" is a task.

   Paths are relative to app/ rather than to app/modules/, because the scan is
   no longer confined to modules/: slicing a core/ path at the length of the
   modules/ prefix would report "ntact_guard.py", which is worse than useless
   in the one message somebody reads while the build is red. */
export function literals(pattern: RegExp): Map<string, string[]> {
  const found = new Map<string, string[]>();
  for (const file of pythonFiles()) {
    const source = readFileSync(file, "utf8");
    for (const match of source.matchAll(pattern)) {
      const name = match.groups?.name;
      if (!name) continue;
      const where = found.get(name) ?? [];
      where.push(file.slice(APP_DIR.length + 1));
      found.set(name, where);
    }
  }
  return found;
}

/* A moved or renamed backend directory must fail LOUDLY. Without this a
   coverage test would pass over an empty set and report success while
   checking absolutely nothing, which is the worst outcome available — worse
   than the bug it was written to catch, because it also hides it.

   BOTH DIRECTORIES ARE NAMED. The file count alone would still catch modules/
   going missing — the dozen files left in core/ and jobs/ are under the floor
   — but only by arithmetic accident, and only until core/ grows. Saying which
   tree was expected makes the failure an answer instead of a riddle. */
export function assertBackendIsThere(): void {
  if (!statSync(APP_DIR).isDirectory()) throw new Error(`not a directory: ${APP_DIR}`);
  if (!statSync(MODULES_DIR).isDirectory()) throw new Error(`not a directory: ${MODULES_DIR}`);
  const count = pythonFiles().length;
  if (count < 20) throw new Error(`only ${count} python files under ${APP_DIR} — has it moved?`);
}

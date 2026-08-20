/* Reading the Python, so the TypeScript can be checked against it — the mobile
   port of web/src/lib/backendKeys.ts.

   Two things in this app are strings the BACKEND names and the FRONTEND
   writes: notification body keys (notificationBodies.ts) and API error codes
   (errorMessages.ts). Both share a failure mode that is silent by
   construction — the backend starts emitting a name nobody translated, the
   client falls back to English, the build passes, and a French reader quietly
   reads English forever. No type checker can see across that seam, because one
   side of it is Python.

   A THIRD KIND JOINED THEM: the notification TYPE, which is what the client
   routes a tap by when the row carries no link. It has the same seam and a
   worse failure — not a sentence in the wrong language but a tap that goes
   nowhere, which reads as a broken app rather than as a missing translation.

   Mobile was exposed to exactly that for longer than web was, because mobile
   CI ran `tsc --noEmit` and nothing else: there was no test step at all, so a
   missing sentence could not fail anything. These files are that step.

   WHY tests/ AND NOT src/lib/, WHICH IS WHERE WEB PUTS ITS COPY. Web keeps its
   scanner beside the code so `include: ["src"]` type-checks it for free. Doing
   the same here would drag @types/node into an Expo app's global type space to
   satisfy the `node:fs` import, and Node's timer declarations would then merge
   with React Native's across every screen in the app — `setTimeout` starts
   returning a Timeout instead of a number. That is a large blast radius for a
   pair of tests that read two files as data. So they sit outside
   tsconfig's `include`, run by vitest (which transpiles rather than
   type-checks), and the app's type environment is left alone.

   WHAT THE PATTERNS CAN AND CANNOT SEE. Every one of them requires a QUOTED
   LITERAL. A name that is assembled — a variable, an f-string, a helper that
   appends a suffix — is invisible here, and no regex fixes that. Both sides
   are built to keep it visible instead: AppError takes `code` keyword-only,
   the notification call sites write their anonymous-name variants out as pairs
   of literal dicts rather than building `f"{key}_anon"`, and a backend test
   (backend/tests/test_error_codes.py) PARSES each module and fails any
   AppError whose code is not a string literal. That AST walk is what makes the
   ERROR_CODE pattern below trustworthy rather than hopeful. */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

/* mobile/tests/ -> mobile/ -> repo root -> the backend package. Resolved from
   this file's own URL rather than process.cwd(), so a run from the repo root
   and a run from mobile/ find the same tree. */
export const APP_DIR = fileURLToPath(new URL("../../backend/app", import.meta.url));
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

   BOTH QUOTE STYLES, and now so does the web copy — it accepted double quotes
   only until the two were brought back into line. Today the backend is
   uniformly double-quoted and both find the same set; the single-quote arm
   costs nothing and means a future `code='x'` cannot slip past this test while
   looking translated. Widening can only ever find MORE codes, never fewer, so
   it cannot turn a red build green. */
export const ERROR_CODE = /(?<![a-z_])code=(?<q>["'])(?<name>[a-z0-9_]+)\k<q>/g;

/* Whitespace or a full-line Python comment — the run of text that can sit
   between two arguments of a call. It is not decoration: campaigns.completion
   explains its choice of notification type in a comment written BETWEEN the
   recipient and the type, so a pattern that only skipped whitespace would miss
   that call site entirely and report green over it. */
const BETWEEN_ARGS = String.raw`(?:\s|#[^\n]*)*`;

/* The TYPE argument of a notify() call: the third positional, after the
   session and the recipient.

   `notify(db, escrow.influencer_user_id, "payment", ...)` and the multi-line
   form both match. The recipient is allowed to be one nested call —
   `other_party(escrow, actor_user_id)`, which payments.disputes passes — which
   is what the `\([^()]*\)` arm is for; commas inside it must not be read as
   the end of the argument.

   It does NOT match `def notify(` in notifications/service.py (the parameter
   is `db: Session,`, so the comma does not follow `db` directly) nor the
   `notify()` written in prose throughout the module docstrings. */
export const NOTIFICATION_TYPE = new RegExp(
  String.raw`notify\(${BETWEEN_ARGS}db${BETWEEN_ARGS},${BETWEEN_ARGS}` +
    String.raw`(?:[^,()#]|\([^()]*\))+,${BETWEEN_ARGS}(?<q>["'])(?<name>[a-z0-9_]+)\k<q>`,
  "g"
);

/* EVERY PYTHON FILE UNDER app/, and not only the ones under app/modules/.

   This walked modules/ alone, and that was a hole with a name in it: the
   contact guard raises `contact_details_found` from app/core/contact_guard.py,
   so the one refusal a creator meets for putting a phone number into a message
   was invisible to the coverage tests that read this. It happened to be
   translated — the audit behind this file's own existence found it by hand —
   but nothing made it STAY translated, and the next coded refusal raised from
   core/, from jobs/, or from anywhere else outside modules/ would have shipped
   untranslated with a green build standing behind it.

   backend/tests/test_error_codes.py has always walked the whole of app/. Both
   clients' scanners now agree with it, and with each other. */
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

/* The keys WRITTEN OUT in one of the catalogs, read from the source text
   rather than from the imported object.

   This exists to check the reader, not the catalog. The tests import the maps,
   so a value's quote style cannot hide a key from them — but a scanner that
   matched `key: "` would silently skip the four single-quoted English
   sentences in this app's catalog (profile_social_method_unknown,
   deliverable_not_on_platform, admin_decision_unknown and
   report_decision_unknown each embed a double quote of their own, so each is
   written with single quotes), and a scanner that cannot see an entry reports
   green over a hole. Comparing this against
   Object.keys() asserts the two agree, so the day somebody swaps a quote style
   the test says so instead of quietly covering less.

   Matches `  key:` at the start of a line inside the named map — the file's
   two-space entry indent — which catches wrapped entries whose value sits on
   the following line as well as single-line ones. */
export function declaredKeys(source: string, mapName: string): string[] {
  const start = source.indexOf(`export const ${mapName}`);
  if (start === -1) throw new Error(`${mapName} not found — has it been renamed?`);
  const end = source.indexOf("\n};", start);
  if (end === -1) throw new Error(`${mapName} is not closed by a \\n}; — has its shape changed?`);
  const block = source.slice(start, end);
  return [...block.matchAll(/^ {2}([a-z][a-z0-9_]*):/gm)].map((m) => m[1]);
}

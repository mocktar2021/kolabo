/* The two languages must say the same things, and between them they must
   cover everything the backend actually emits.

   Localising notification bodies is a job done one call site at a time, and
   the failure mode is silent by construction: a backend that starts sending
   {"key": "order_declined"} before anybody writes the French for it produces
   no error anywhere. The client falls back to the stored English `message`,
   the row still renders, the build still passes — and a French reader quietly
   reads English forever. Nothing catches that but a test that knows about
   both sides at once.

   So this file asserts three things, and the third is the one that bites:

     1. the two maps have the same key set — a key added to one language and
        forgotten in the other is a French reader reading English;
     2. a key's {{placeholders}} match between languages — the backend sends
        ONE params dict for both, so a French string asking for {{campaign}}
        when the English asks for {{title}} renders the raw braces;
     3. EVERY key the backend emits exists in both maps. This one reads the
        Python sources rather than a list maintained here, because a list
        maintained here is a list that goes stale the first time somebody adds
        a notification in a hurry.

   Reading .py from a frontend test is unusual and deliberate. The alternative
   — a backend test that greps the TypeScript — puts the same coupling in the
   other direction, and this direction is the one where the missing half is
   the frontend's own data.

   WHAT THE REGEX SEES, and what it cannot. Two forms, both requiring a quoted
   literal: `"key": "name"` (a params dict written at the call site) and
   `..._key="name"` (a key passed as a keyword argument, which
   campaigns.service._place_order does because its three callers say three
   different sentences about the same order). Across backend/app/modules those
   two match notify() keys and nothing else — primary_key=, ForeignKey(,
   sort(key= and the prose in the comments all fail them, because none has a
   quoted string immediately after.

   What it CANNOT see is a key that is assembled rather than written: a
   variable, an f-string, a helper that appends a suffix. That is a real limit
   and the reason the backend spells its anonymous-name variants out as pairs
   of literal dicts instead of building `f"{key}_anon"` — see the note above
   UNNAMED_CREATOR in campaigns/service.py. A call site that genuinely needs a
   computed key should add it to a hand-kept list here and say why, rather
   than teach this regex to be clever.

   If a stray literal ever matches, the failure names the key and the file it
   came from: fix it by translating the key or by narrowing the pattern, not
   by deleting the assertion. */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { body_en, body_fr } from "./notificationBodies";

const PLACEHOLDER = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g;

function placeholders(template: string): string[] {
  return [...template.matchAll(PLACEHOLDER)].map((m) => m[1]).sort();
}

/* web/src/lib/ -> repo root -> the backend package. */
const MODULES_DIR = fileURLToPath(new URL("../../../backend/app/modules", import.meta.url));

function pythonFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (entry === "__pycache__") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...pythonFiles(full));
    else if (entry.endsWith(".py")) out.push(full);
  }
  return out;
}

function emittedKeys(): Map<string, string[]> {
  const found = new Map<string, string[]>();
  for (const file of pythonFiles(MODULES_DIR)) {
    const source = readFileSync(file, "utf8");
    for (const match of source.matchAll(/(?:"key":\s*|\b[a-z_]*key=)"([a-z0-9_]+)"/g)) {
      const where = found.get(match[1]) ?? [];
      where.push(file.slice(MODULES_DIR.length + 1));
      found.set(match[1], where);
    }
  }
  return found;
}

describe("the two languages agree", () => {
  it("has the same keys in French and English", () => {
    expect(Object.keys(body_fr).sort()).toEqual(Object.keys(body_en).sort());
  });

  it("asks for the same interpolation values in both", () => {
    const mismatched: string[] = [];
    for (const [key, fr] of Object.entries(body_fr)) {
      const en = (body_en as Record<string, string>)[key];
      if (en === undefined) continue; // the test above owns that failure
      const a = placeholders(fr);
      const b = placeholders(en);
      if (a.join(",") !== b.join(",")) mismatched.push(`${key}: fr[${a}] vs en[${b}]`);
    }
    expect(mismatched).toEqual([]);
  });

  it("has no empty body in either language", () => {
    const blank = [...Object.entries(body_fr), ...Object.entries(body_en)]
      .filter(([, text]) => text.trim() === "")
      .map(([key]) => key);
    expect(blank).toEqual([]);
  });
});

describe("every key the backend emits is translated", () => {
  /* A moved backend directory must fail loudly. If this resolved to nothing
     the coverage test below would pass over an empty set and report success
     while checking absolutely nothing — the worst outcome available. */
  it("can see the backend modules", () => {
    expect(statSync(MODULES_DIR).isDirectory()).toBe(true);
    expect(pythonFiles(MODULES_DIR).length).toBeGreaterThan(20);
  });

  it("finds a French and an English body for each one", () => {
    const untranslated: string[] = [];
    for (const [key, files] of emittedKeys()) {
      const missing: string[] = [];
      if (!(key in body_fr)) missing.push("fr");
      if (!(key in body_en)) missing.push("en");
      if (missing.length) untranslated.push(`${key} (${missing.join("+")}) emitted by ${files.join(", ")}`);
    }
    expect(untranslated).toEqual([]);
  });

  /* The other direction is NOT an error. A key can outlive the call site that
     emitted it, and a body written ahead of the backend change that uses it is
     a perfectly good way to work. Recorded as a count so the drift is at least
     visible in the run. */
  it("reports bodies no backend call site emits", () => {
    const emitted = new Set(emittedKeys().keys());
    const unused = Object.keys(body_en).filter((k) => !emitted.has(k));
    expect(unused.length).toBeLessThan(Object.keys(body_en).length);
  });
});

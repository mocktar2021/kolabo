/* The two languages must say the same things, and between them they must
   cover everything the backend actually emits.

   Localising notification bodies is a job done one call site at a time, and
   the failure mode is silent by construction: a backend that starts sending
   {"key": "order_declined"} before anybody writes the French for it produces
   no error anywhere. The client falls back to the stored English `message`,
   the row still renders, the build still passes — and a French reader quietly
   reads English forever. Nothing catches that but a test that knows about
   both sides at once.

   web/src/lib/notificationBodies.test.ts has asserted this for the web catalog
   for some time. The mobile catalog is a hand-kept mirror of it, which is
   precisely the arrangement that drifts: nothing made the mirror's copy fail
   when it fell behind. Now something does.

   Three assertions, and the third is the one that bites:

     1. the two maps have the same key set — a key added to one language and
        forgotten in the other is a French reader reading English;
     2. a key's {{placeholders}} match between languages — the backend sends
        ONE params dict for both, so a French string asking for {{campaign}}
        when the English asks for {{title}} renders the raw braces;
     3. EVERY key the backend emits exists in both maps, read out of the Python
        rather than from a list maintained here, because a list maintained here
        goes stale the first time somebody adds a notification in a hurry. */
import { describe, expect, it } from "vitest";

import { NOTIFICATION_KEY, assertBackendIsThere, literals } from "./backendKeys";
import { body_en, body_fr } from "../src/lib/notificationBodies";

const PLACEHOLDER = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g;

function placeholders(template: string): string[] {
  return [...template.matchAll(PLACEHOLDER)].map((m) => m[1]).sort();
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
  it("can see the backend modules", () => {
    expect(() => assertBackendIsThere()).not.toThrow();
  });

  it("finds a French and an English body for each one", () => {
    const untranslated: string[] = [];
    for (const [key, files] of literals(NOTIFICATION_KEY)) {
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
    const emitted = new Set(literals(NOTIFICATION_KEY).keys());
    const unused = Object.keys(body_en).filter((k) => !emitted.has(k));
    expect(unused.length).toBeLessThan(Object.keys(body_en).length);
  });
});

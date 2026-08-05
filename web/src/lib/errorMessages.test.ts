/* Every error code the backend can send has a sentence in both languages.

   The backend half of this guarantee is backend/tests/test_error_codes.py: a
   converted module may not raise a bare HTTPException, and may not build a
   code it cannot write out. This is the other half — given that every code is
   readable in the Python, every one of them must have somewhere to land here.

   Neither test is much use without the other. Together they close the loop:
   a refusal in a converted module has a code, and a code has both languages.

   Same shape as notificationBodies.test.ts, sharing its scanner (backendKeys),
   because it is the same seam and the same silent failure. */
import { describe, expect, it } from "vitest";

import { ERROR_CODE, assertBackendIsThere, literals } from "./backendKeys";
import { GENERIC_KEY, errorText, error_en, error_fr } from "./errorMessages";

const PLACEHOLDER = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g;

function placeholders(template: string): string[] {
  return [...template.matchAll(PLACEHOLDER)].map((m) => m[1]).sort();
}

/* A stand-in for i18next: looks the key up in one language, interpolates, and
   honours defaultValue the way the real one does. Small enough to be obviously
   correct, which matters — errorText's fallback chain is the logic under test
   and mocking it away would leave nothing behind. */
function translator(map: Record<string, string>) {
  return (key: string, opts?: Record<string, unknown>) => {
    const template = map[key.replace(/^apiError\./, "")];
    if (template === undefined) return (opts?.defaultValue as string) ?? key;
    return template.replace(PLACEHOLDER, (whole, name) =>
      opts && name in opts ? String(opts[name]) : whole
    );
  };
}

describe("the two languages agree", () => {
  it("has the same codes in French and English", () => {
    expect(Object.keys(error_fr).sort()).toEqual(Object.keys(error_en).sort());
  });

  it("asks for the same interpolation values in both", () => {
    const mismatched: string[] = [];
    for (const [code, fr] of Object.entries(error_fr)) {
      const en = (error_en as Record<string, string>)[code];
      if (en === undefined) continue; // the test above owns that failure
      const a = placeholders(fr);
      const b = placeholders(en);
      if (a.join(",") !== b.join(",")) mismatched.push(`${code}: fr[${a}] vs en[${b}]`);
    }
    expect(mismatched).toEqual([]);
  });

  it("has no empty sentence in either language", () => {
    const blank = [...Object.entries(error_fr), ...Object.entries(error_en)]
      .filter(([, text]) => text.trim() === "")
      .map(([code]) => code);
    expect(blank).toEqual([]);
  });

  it("has a generic fallback, which errorText reaches for by name", () => {
    expect(GENERIC_KEY).toBe("apiError.generic");
    expect(error_fr.generic).toBeTruthy();
    expect(error_en.generic).toBeTruthy();
  });
});

describe("every code the backend emits is translated", () => {
  it("can see the backend modules", () => {
    expect(() => assertBackendIsThere()).not.toThrow();
  });

  it("finds a French and an English sentence for each one", () => {
    const untranslated: string[] = [];
    for (const [code, files] of literals(ERROR_CODE)) {
      const missing: string[] = [];
      if (!(code in error_fr)) missing.push("fr");
      if (!(code in error_en)) missing.push("en");
      if (missing.length) untranslated.push(`${code} (${missing.join("+")}) raised in ${files.join(", ")}`);
    }
    expect(untranslated).toEqual([]);
  });
});

describe("errorText picks the best sentence available", () => {
  const t = translator(error_fr);

  it("prefers the localised sentence for a known code", () => {
    const text = errorText(
      { code: "deliverable_already_answered", message: "This submission has already been answered." },
      t
    );
    expect(text).toBe(error_fr.deliverable_already_answered);
  });

  it("interpolates the values the backend sent", () => {
    const text = errorText({ code: "deliverable_note_too_long", values: { max: 4000 }, message: "x" }, t);
    expect(text).toBe("Une note fait au plus 4000 caractères.");
    expect(text).not.toContain("{{");
  });

  it("falls back to the backend's English for a code it does not know", () => {
    /* An un-migrated module, or one migrated ahead of its translations. The
       English is worse than French for a French reader and better than
       "something went wrong", because it says what to do next. */
    const text = errorText({ code: "payment_something_new", message: "The escrow is frozen." }, t);
    expect(text).toBe("The escrow is frozen.");
  });

  it("never shows the raw i18n key when a lookup misses", () => {
    const text = errorText({ code: "not_a_real_code" }, t);
    expect(text).not.toContain("apiError.");
    expect(text).toBe(error_fr.generic);
  });

  it("falls back to the English when there is no code at all", () => {
    /* Every one of the 200-odd refusals not yet converted. This is the case
       that must not regress: it is exactly what the app showed before any of
       this existed. */
    expect(errorText({ message: "Proposal not found" }, t)).toBe("Proposal not found");
  });

  it("says something sensible for a thrown non-error", () => {
    /* A network failure, a CORS refusal, a response that was not JSON — the
       cases where a page used to render the bare literal "Error". */
    expect(errorText(null, t)).toBe(error_fr.generic);
    expect(errorText(undefined, t)).toBe(error_fr.generic);
    expect(errorText(new Error(""), t)).toBe(error_fr.generic);
  });

  it("works the same way in English", () => {
    const te = translator(error_en);
    expect(errorText({ code: "deliverable_note_too_long", values: { max: 4000 } }, te)).toBe(
      "A note is at most 4000 characters."
    );
  });
});

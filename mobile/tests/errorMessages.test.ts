/* Every error code the backend can send has a sentence in both languages.

   The backend half of this guarantee is backend/tests/test_error_codes.py: a
   module may not raise a bare HTTPException, and may not build a code it
   cannot write out. This is the mobile half — given that every code is
   readable in the Python, every one of them must have somewhere to land here.

   Until this file existed, mobile had no second half at all. CI ran
   `tsc --noEmit`, which cannot see across a seam whose far side is Python, so
   a code with no entry in errorMessages.ts fell through to the backend's
   English `message` and nothing anywhere went red. Three of the five launch
   countries are francophone; the code that motivated this, and that the audit
   found missing, was contact_details_found — the refusal a creator gets for
   putting a phone number in a message.

   Same shape as web/src/lib/errorMessages.test.ts, deliberately, so the two
   clients are guarded the same way and a change to one is obvious in the
   other. */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { ERROR_CODE, assertBackendIsThere, declaredKeys, literals, readAppFile } from "./backendKeys";
import { GENERIC_KEY, errorText, error_en, error_fr } from "../src/lib/errorMessages";

const CATALOG = fileURLToPath(new URL("../src/lib/errorMessages.ts", import.meta.url));

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
      const en = error_en[code];
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

describe("the catalog reader can see every entry", () => {
  /* THE SCANNER CHECKING ITSELF. The tests above import the maps, so quote
     style cannot hide an entry from them. This asserts that property instead
     of assuming it: the keys written in the source text must be exactly the
     keys in the object. A reader that matched `key: "` would miss the two
     English sentences written with single quotes — they embed a double quote —
     and a reader that cannot see an entry reports green over a hole, which is
     worse than having no reader at all. */
  const source = readFileSync(CATALOG, "utf8");

  it("finds the same French keys in the text as in the map", () => {
    expect(declaredKeys(source, "error_fr").sort()).toEqual(Object.keys(error_fr).sort());
  });

  it("finds the same English keys in the text as in the map", () => {
    expect(declaredKeys(source, "error_en").sort()).toEqual(Object.keys(error_en).sort());
  });

  it("reads the single-quoted sentences, double quotes and all", () => {
    /* Named rather than merely covered by the counts above, because these two
       are the reason the check exists. */
    expect(error_en.profile_social_method_unknown).toContain('"oauth"');
    expect(error_en.deliverable_not_on_platform).toContain('"{{type}}"');
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

describe("the contact guard's tokens are all translated", () => {
  /* A surface and a kind are NOT codes, so the code-coverage test above cannot
     see them — and an untranslated one is a hole in the middle of a French
     sentence rather than a missing sentence, which is worse because nothing
     falls back. Both sets are closed and written out as literals in
     app/core/contact_guard.py precisely so this test can read them. */
  const guard = readAppFile("core/contact_guard.py");

  function tupleLiterals(name: string): string[] {
    const block = new RegExp(`${name}\\s*=\\s*\\(([^)]*)\\)`).exec(guard);
    if (!block) throw new Error(`${name} not found in contact_guard.py — has it been renamed?`);
    return [...block[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
  }

  it("has a noun for every surface, in both languages", () => {
    const surfaces = tupleLiterals("SURFACES");
    expect(surfaces.length).toBeGreaterThan(0);
    const missing: string[] = [];
    for (const surface of surfaces) {
      const key = `surface_${surface.trim().replace(/\s+/g, "_")}`;
      if (!(key in error_fr)) missing.push(`${key} (fr)`);
      if (!(key in error_en)) missing.push(`${key} (en)`);
    }
    expect(missing).toEqual([]);
  });

  it("has a noun for every kind, in both languages", () => {
    const kinds = [...guard.matchAll(/^(?:EMAIL|PHONE|HANDLE) = "([a-z]+)"$/gm)].map((m) => m[1]);
    expect(kinds.sort()).toEqual(["email", "handle", "phone"]);
    for (const kind of kinds) {
      expect(error_fr).toHaveProperty(`kind_${kind}`);
      expect(error_en).toHaveProperty(`kind_${kind}`);
    }
  });
});

describe("errorText composes the contact-guard refusal", () => {
  /* contact_details_found is the one sentence whose values are WORDS. It
     interpolates {{what}}, which no backend payload contains — errorMessages
     builds it out of `kinds`. Copying the sentence without that step would put
     a literal "{{what}}" mid-refusal, so these assert the composition travelled
     with it. */
  const fr = translator(error_fr);
  const en = translator(error_en);

  function refusal(kinds: string[], surface: string) {
    return { code: "contact_details_found", values: { kinds, surface }, message: "English original." };
  }

  it("names one kind with no list at all", () => {
    const text = errorText(refusal(["phone"], "statement"), fr);
    expect(text).toContain("Ce texte");
    expect(text).toContain("semble contenir un numéro de téléphone.");
    expect(text).not.toContain("{{");
  });

  it("joins two kinds with the language's own word", () => {
    expect(errorText(refusal(["email", "phone"], "message"), fr)).toContain(
      "une adresse e-mail et un numéro de téléphone"
    );
    expect(errorText(refusal(["email", "phone"], "message"), en)).toContain(
      "an email address and a phone number"
    );
  });

  it("commas all but the last of three", () => {
    expect(errorText(refusal(["email", "phone", "handle"], "message"), en)).toContain(
      "an email address, a phone number and a messaging app handle"
    );
  });

  it("normalises a spaced surface to its key", () => {
    expect(errorText(refusal(["phone"], "proposal note"), fr)).toContain("commentaire de proposition");
  });

  it("falls back to the token for a surface or kind it does not know", () => {
    const text = errorText(refusal(["carrier_pigeon"], "smoke signal"), fr);
    expect(text).toContain("carrier_pigeon");
    expect(text).toContain("smoke signal");
    expect(text).not.toContain("{{");
    expect(text).not.toContain("apiError.");
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
    const text = errorText({ code: "payment_something_new", message: "The escrow is frozen." }, t);
    expect(text).toBe("The escrow is frozen.");
  });

  it("never shows the raw i18n key when a lookup misses", () => {
    const text = errorText({ code: "not_a_real_code" }, t);
    expect(text).not.toContain("apiError.");
    expect(text).toBe(error_fr.generic);
  });

  it("falls back to the English when there is no code at all", () => {
    expect(errorText({ message: "Proposal not found" }, t)).toBe("Proposal not found");
  });

  it("says something sensible for a thrown non-error", () => {
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

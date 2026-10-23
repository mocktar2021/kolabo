/* The content-licence shape and the sentence a creator reads, asserted rather
   than assumed.

   lib/licenceTerms exists because one table is read by four things at once:
   the render order of the brand's form, the gate on its submit button, the
   body of the request, and the plain-language sentence the creator reads
   before accepting. The module's whole value is that those four cannot
   disagree, and a table nothing checks is a table that drifts.

   THE FOURTH READER IS WHY THIS FILE GOES FURTHER THAN partyDetails.test.ts.
   A wrong field list on a form costs a round trip. A wrong sentence costs a
   creator accepting a licence they did not price, which is the thing this
   whole feature exists to prevent, and mobile has no UI tests, so the only
   place that wording is checked at all is here. Hence the last two groups:
   one drives licenceSentences through every state, including the ones that
   should be unreachable, and one reads lib/licenceStrings.ts as TEXT to check
   that the templates those sentences are built from exist in both languages
   and ask for the same values. errorMessages.test.ts reads its catalog the
   same way and for the same reason: a reader that cannot see an entry reports
   green over a hole.

   licenceStrings.ts is read and never imported. It imports the i18n instance,
   which boots expo-localization, and this suite runs in node. */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  EMPTY_DRAFT,
  EMPTY_VALUES,
  FIELDS,
  LICENCE_OPTIONS,
  OPTIONAL,
  draftIsComplete,
  draftPayload,
  isComplete,
  isOptional,
  licenceSentences,
  missingFields,
  optionOf,
  redistributes,
  toPayload,
  valuesFrom,
  type LicenceField,
  type LicenceOption,
  type LicenceTerms,
  type LicenceValues,
} from "../src/lib/licenceTerms";

const STRINGS = fileURLToPath(new URL("../src/lib/licenceStrings.ts", import.meta.url));

const PLACEHOLDER = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g;

function placeholders(template: string): string[] {
  return [...template.matchAll(PLACEHOLDER)].map((m) => m[1]).sort();
}

/* A filled set of values for one option, so a test about one field does not
   have to write out the others that are not the point. */
function filled(option: LicenceOption): LicenceValues {
  const values = { ...EMPTY_VALUES };
  for (const field of FIELDS[option]) values[field] = `${field} value`;
  return values;
}

/* A stand-in for i18next: echoes the key with its interpolated values, so a
   test can see WHICH template was chosen and WHAT went into it without
   depending on a sentence anybody may reword. The real sentences are checked
   against the copy file further down. */
function stub(key: string, opts?: Record<string, unknown>): string {
  const values = Object.entries(opts ?? {})
    .map(([name, value]) => `${name}=${String(value)}`)
    .join(",");
  return values ? `${key}[${values}]` : key;
}

describe("the three options and their tables line up", () => {
  it("offers exactly the three options article 10 offers", () => {
    /* The contract says "Option retenue : [ 1 / 2 / 3 ]" and the backend
       stores that character. A fourth option here would be a value no
       document can print. */
    expect(LICENCE_OPTIONS).toEqual(["1", "2", "3"]);
  });

  it("has a field list and an exception list for every option", () => {
    expect(Object.keys(FIELDS).sort()).toEqual([...LICENCE_OPTIONS].sort());
    expect(Object.keys(OPTIONAL).sort()).toEqual([...LICENCE_OPTIONS].sort());
  });

  it("names every field in a shape the form state can hold", () => {
    /* A field in FIELDS with no slot in the values record would render an
       uncontrolled input that loses what is typed into it. */
    const known = Object.keys(EMPTY_VALUES);
    for (const option of LICENCE_OPTIONS) {
      for (const field of FIELDS[option]) expect(known).toContain(field);
    }
  });

  it("marks optional only fields the option actually asks for", () => {
    for (const option of LICENCE_OPTIONS) {
      for (const field of OPTIONAL[option]) expect(FIELDS[option]).toContain(field);
    }
  });

  it("asks nothing further for option 1", () => {
    /* The creator publishes on their own accounts and the brand has no
       redistribution right, so there is no duration to state and no territory
       to name. A single required field here would ask a brand claiming
       nothing to describe the nothing. */
    expect(FIELDS["1"]).toEqual([]);
    expect(isComplete("1", { ...EMPTY_VALUES })).toBe(true);
  });

  it("requires a duration, territories and media for option 2", () => {
    /* The clause with three blanks in it, and the sentence a creator prices
       against. A licence of unstated length is not one anybody can put a
       number on. */
    expect(FIELDS["2"]).toEqual(["licence_duration", "licence_territories", "licence_media"]);
    expect(missingFields("2", { ...EMPTY_VALUES })).toEqual(FIELDS["2"]);
    for (const field of FIELDS["2"]) expect(isOptional("2", field)).toBe(false);
  });

  it("requires a duration and territories for option 3, and lets the consideration be blank", () => {
    /* The contract says a separate consideration MAY be agreed, so an empty
       one means none was, not that something is missing. */
    expect(isOptional("3", "licence_consideration")).toBe(true);
    const values = filled("3");
    values.licence_consideration = "";
    expect(missingFields("3", values)).toEqual([]);
    expect(isComplete("3", values)).toBe(true);
    values.licence_duration = "";
    expect(missingFields("3", values)).toEqual(["licence_duration"]);
  });

  it("reports everything missing in render order", () => {
    /* The order is load-bearing: the form points the reader at the first
       thing to fix, and a set in some other order would point at the wrong
       one. */
    expect(missingFields("2", { ...EMPTY_VALUES })).toEqual(FIELDS["2"]);
    expect(missingFields("3", { ...EMPTY_VALUES })).toEqual(["licence_duration", "licence_territories"]);
  });

  it("does not accept whitespace as an answer", () => {
    /* A duration of three spaces prints as a blank in the middle of the
       clause and reads as filled in, which is worse than an empty one. */
    const values = filled("2");
    values.licence_duration = "   ";
    expect(missingFields("2", values)).toEqual(["licence_duration"]);
  });

  it("calls option 2 and option 3 redistribution, and option 1 not", () => {
    /* Both surfaces use this for one thing: whether the pricing warning is
       worth a line of screen. Under option 1 there is nothing extra to
       price. */
    expect(redistributes("1")).toBe(false);
    expect(redistributes("2")).toBe(true);
    expect(redistributes("3")).toBe(true);
    expect(redistributes(null)).toBe(false);
  });
});

describe("optionOf reads what a payload states and guesses nothing", () => {
  it("reads each of the three", () => {
    for (const option of LICENCE_OPTIONS) {
      expect(optionOf({ licence_option: option })).toBe(option);
    }
  });

  it("treats an absent, null or empty option as nothing stated", () => {
    expect(optionOf(null)).toBeNull();
    expect(optionOf(undefined)).toBeNull();
    expect(optionOf({})).toBeNull();
    expect(optionOf({ licence_option: null })).toBeNull();
    expect(optionOf({ licence_option: "" })).toBeNull();
  });

  it("degrades an unrecognised option to nothing stated", () => {
    /* A fourth value is a row this client cannot describe, and the honest
       answer on screen is the one it gives an empty field. Guessing which
       option a stranger meant would put a sentence about paid advertising in
       front of a creator on no evidence. */
    expect(optionOf({ licence_option: "4" })).toBeNull();
    expect(optionOf({ licence_option: "exclusive" })).toBeNull();
    expect(optionOf({ licence_option: 2 } as unknown as LicenceTerms)).toBeNull();
  });

  it("tolerates surrounding whitespace on an option it recognises", () => {
    expect(optionOf({ licence_option: " 2 " })).toBe("2");
  });
});

describe("toPayload sends all four fields every time", () => {
  /* THE ONE PLACE THIS MODULE DEPARTS FROM lib/partyDetails, which omits a
     field its type does not ask for. A party block is replaced whole by a
     PUT; these columns hang off a campaign edited in pieces, so an omitted
     field is a field left at whatever it was. */
  const expectedKeys = ["licence_option", ...Object.keys(EMPTY_VALUES)].sort();

  it("sends exactly the same keys for every option", () => {
    for (const option of LICENCE_OPTIONS) {
      expect(Object.keys(toPayload(option, filled(option))).sort()).toEqual(expectedKeys);
    }
  });

  it("carries the option and every field that option asks for", () => {
    const body = toPayload("2", filled("2"));
    expect(body.licence_option).toBe("2");
    for (const field of FIELDS["2"]) expect(body[field]).toBe(`${field} value`);
  });

  it("nulls a field the chosen option does not ask for", () => {
    /* A brand that narrows its claim from option 2 to option 1 must not keep
       a stale twelve months and a stale territory list, because those would
       print on the contract underneath a sentence saying it has no
       redistribution right. */
    const body = toPayload("1", filled("2"));
    expect(body.licence_option).toBe("1");
    expect(body.licence_duration).toBeNull();
    expect(body.licence_territories).toBeNull();
    expect(body.licence_media).toBeNull();
    expect(body.licence_consideration).toBeNull();
  });

  it("nulls option 2's media when option 3 is chosen", () => {
    const body = toPayload("3", filled("2"));
    expect(body.licence_media).toBeNull();
    expect(body.licence_duration).toBe("licence_duration value");
  });

  it("trims, and turns a blank field into null", () => {
    const values = filled("2");
    values.licence_duration = "  12 mois  ";
    values.licence_media = "   ";
    const body = toPayload("2", values);
    expect(body.licence_duration).toBe("12 mois");
    expect(body.licence_media).toBeNull();
  });
});

describe("the brand's draft starts unanswered", () => {
  it("pre-selects nothing", () => {
    /* A pre-selected option 2 would claim a paid-advertising licence from a
       brand that never read the question, and even a pre-selected option 1
       would answer article 10 on the brand's behalf. */
    expect(EMPTY_DRAFT.option).toBe("");
    expect(EMPTY_DRAFT.values).toEqual(EMPTY_VALUES);
  });

  it("is never complete and has nothing to send while no option is chosen", () => {
    expect(draftIsComplete(EMPTY_DRAFT)).toBe(false);
    expect(draftPayload(EMPTY_DRAFT)).toBeNull();
  });

  it("sends five nulls for nobody: an unanswered form is not option 1", () => {
    /* Five nulls is a brand stating that it claims nothing, which IS option
       1. A caller handed null has to omit the keys instead. */
    expect(draftPayload({ option: "", values: filled("2") })).toBeNull();
  });

  it("is complete as soon as option 1 is chosen", () => {
    expect(draftIsComplete({ option: "1", values: { ...EMPTY_VALUES } })).toBe(true);
    expect(draftPayload({ option: "1", values: { ...EMPTY_VALUES } })).toEqual({
      licence_option: "1",
      licence_duration: null,
      licence_territories: null,
      licence_media: null,
      licence_consideration: null,
    });
  });

  it("waits for option 2's three fields", () => {
    const values = filled("2");
    values.licence_media = "";
    expect(draftIsComplete({ option: "2", values })).toBe(false);
    values.licence_media = "Instagram, Facebook";
    expect(draftIsComplete({ option: "2", values })).toBe(true);
  });
});

describe("valuesFrom reads a payload into form state", () => {
  it("gives every field an empty string when there are no terms", () => {
    expect(valuesFrom(null)).toEqual(EMPTY_VALUES);
    expect(valuesFrom(undefined)).toEqual(EMPTY_VALUES);
    expect(valuesFrom({})).toEqual(EMPTY_VALUES);
  });

  it("turns a null field into an empty string rather than passing it through", () => {
    const values = valuesFrom({ licence_option: "2", licence_duration: "12 mois", licence_media: null });
    expect(values.licence_duration).toBe("12 mois");
    expect(values.licence_media).toBe("");
  });

  it("never lets the option itself into the values record", () => {
    /* licence_option is the discriminator, not a field, so it has no slot
       here and there is no path by which the form can edit it as text. */
    const values = valuesFrom({ licence_option: "2" });
    expect(Object.keys(values).sort()).toEqual(Object.keys(EMPTY_VALUES).sort());
    expect((values as Record<string, string>).licence_option).toBeUndefined();
  });

  it("keeps the field union and the empty record in step", () => {
    const fields: LicenceField[] = Object.keys(EMPTY_VALUES) as LicenceField[];
    for (const field of fields) expect(EMPTY_VALUES[field]).toBe("");
    expect(fields.length).toBe(4);
  });

  it("survives a round trip through toPayload", () => {
    const stored: LicenceTerms = {
      licence_option: "2",
      licence_duration: "12 mois a compter de la publication",
      licence_territories: "Benin et Togo",
      licence_media: "reseaux sociaux de la marque et affichage en magasin",
      licence_consideration: null,
    };
    const body = toPayload("2", valuesFrom(stored));
    expect(body.licence_duration).toBe(stored.licence_duration);
    expect(body.licence_territories).toBe(stored.licence_territories);
    expect(body.licence_media).toBe(stored.licence_media);
  });
});

describe("the sentence a creator reads before accepting", () => {
  it("says nothing at all when no option is stated", () => {
    /* The caller owns that case, because "the brand has not said" is a
       different piece of news from any of the three options and belongs in
       its own sentence. */
    expect(licenceSentences(null, stub)).toEqual([]);
    expect(licenceSentences({}, stub)).toEqual([]);
    expect(licenceSentences({ licence_option: "4" }, stub)).toEqual([]);
  });

  it("states option 1 rather than printing nothing", () => {
    /* "No redistribution right" and "nobody mentioned the licence" look
       identical if the first prints nothing, and they end in different
       places. */
    expect(licenceSentences({ licence_option: "1" }, stub)).toEqual(["licence.o1"]);
  });

  it("ignores values left over under option 1", () => {
    /* A row that was option 2 before somebody narrowed it may still carry a
       duration if the request that narrowed it omitted the field. The
       sentence follows the option, not the leftovers. */
    const lines = licenceSentences(
      { licence_option: "1", licence_duration: "12 mois", licence_territories: "Benin" },
      stub
    );
    expect(lines).toEqual(["licence.o1"]);
  });

  it("names the brand's own duration, territories and media in one sentence", () => {
    /* The happy path, and the whole point of the feature: one sentence, in
       the second person, with the stated values inside it. */
    const lines = licenceSentences(
      {
        licence_option: "2",
        licence_duration: "12 mois",
        licence_territories: "Benin et Togo",
        licence_media: "publicite payante Meta",
      },
      stub
    );
    expect(lines).toHaveLength(1);
    expect(lines[0]).toContain("licence.o2_full");
    expect(lines[0]).toContain("duration=12 mois");
    expect(lines[0]).toContain("territories=Benin et Togo");
    expect(lines[0]).toContain("media=publicite payante Meta");
  });

  it("repeats the stated values exactly, without rewording or translating", () => {
    /* Free text written by the brand and printed verbatim into the contract.
       An apostrophe survives because i18n.ts sets escapeValue false. */
    const territories = "le Benin, le Togo et la Cote d'Ivoire";
    const lines = licenceSentences(
      { licence_option: "2", licence_duration: "6 mois", licence_territories: territories, licence_media: "Reels" },
      stub
    );
    expect(lines[0]).toContain(`territories=${territories}`);
  });

  it("gives option 3 its headline and its consideration on a line of its own", () => {
    const lines = licenceSentences(
      {
        licence_option: "3",
        licence_duration: "sans limite de duree",
        licence_territories: "monde entier",
        licence_consideration: "150000 XOF",
      },
      stub
    );
    expect(lines).toHaveLength(2);
    expect(lines[0]).toContain("licence.o3_full");
    expect(lines[1]).toBe("licence.f_consideration[value=150000 XOF]");
  });

  it("leaves option 3's consideration out when none was agreed", () => {
    const lines = licenceSentences(
      { licence_option: "3", licence_duration: "2 ans", licence_territories: "Ghana" },
      stub
    );
    expect(lines).toHaveLength(1);
    expect(lines[0]).toContain("licence.o3_full");
  });

  it("degrades to the part that is still true when a required value is missing", () => {
    /* The backend requires those fields, so this should be unreachable. It is
       tested because the cost of being wrong about that is a creator
       accepting terms nobody wrote down. Interpolating an empty duration
       would read like a bug, and an invented filler would read as a term
       somebody agreed. */
    const lines = licenceSentences(
      { licence_option: "2", licence_territories: "Benin", licence_media: "" },
      stub
    );
    expect(lines[0]).toBe("licence.o2_head");
    expect(lines).toContain("licence.f_territories[value=Benin]");
    expect(lines[lines.length - 1]).toBe("licence.incomplete");
  });

  it("never leaves a hole where a value should be", () => {
    /* The assertion that would have caught the naive version: a template
       interpolated with nothing keeps its braces. */
    for (const terms of [
      { licence_option: "2" },
      { licence_option: "2", licence_duration: "12 mois" },
      { licence_option: "3" },
      { licence_option: "3", licence_consideration: "100000 XOF" },
    ] as LicenceTerms[]) {
      for (const line of licenceSentences(terms, stub)) {
        expect(line).not.toContain("{{");
        expect(line).not.toContain("=undefined");
        expect(line).not.toContain("=null");
      }
    }
  });

  it("says something for every option, in every state", () => {
    /* A card that renders an empty block says less than one that says
       nothing, because an empty block reads as a control that failed. */
    for (const option of LICENCE_OPTIONS) {
      expect(licenceSentences({ licence_option: option }, stub).length).toBeGreaterThan(0);
      expect(licenceSentences({ licence_option: option, ...filled(option) }, stub).length).toBeGreaterThan(0);
    }
  });
});

describe("the copy those sentences are built from exists in both languages", () => {
  /* Read as text, because importing lib/licenceStrings boots the i18n
     instance and expo-localization with it. Same approach
     errorMessages.test.ts takes to its catalog, and for the same reason: a
     missing template is a raw key shown to the one reader who most needs the
     sentence. */
  const source = readFileSync(STRINGS, "utf8");

  /* No expect() in here. This runs while the file is being collected, not
     inside a test, and an assertion that throws there fails the whole suite
     with a collection error rather than naming the bundle it could not
     read. */
  function bundle(name: "fr" | "en"): Record<string, string> {
    const start = source.indexOf(`const ${name} = {`);
    if (start < 0) return {};
    const end = source.indexOf("\n};", start);
    if (end < start) return {};
    const block = source.slice(start, end);
    const out: Record<string, string> = {};
    for (const match of block.matchAll(/^ {4}([a-zA-Z0-9_]+): "((?:[^"\\]|\\.)*)",$/gm)) {
      out[match[1]] = match[2];
    }
    return out;
  }

  const fr = bundle("fr");
  const en = bundle("en");

  /* Every key licenceSentences can ask for. Written out rather than derived,
     so adding a sentence to the module without copy for it fails here. */
  const SENTENCE_KEYS = [
    "o1",
    "o2_full",
    "o2_head",
    "o3_full",
    "o3_head",
    "f_duration",
    "f_territories",
    "f_media",
    "f_consideration",
    "incomplete",
  ];

  it("can actually see the entries in both bundles", () => {
    /* THE SCANNER CHECKING ITSELF, the same guard errorMessages.test.ts puts
       on its catalog reader. A regex that stopped matching would make every
       check below pass over two empty objects. */
    expect(Object.keys(fr).length).toBeGreaterThan(20);
    expect(Object.keys(en).length).toBeGreaterThan(20);
    expect(fr.o2_full).toContain("{{duration}}");
    expect(en.o2_full).toContain("{{duration}}");
  });

  it("has the same keys in French and English", () => {
    expect(Object.keys(fr).sort()).toEqual(Object.keys(en).sort());
  });

  it("has a sentence for every state the module can report", () => {
    for (const key of SENTENCE_KEYS) {
      expect(fr).toHaveProperty(key);
      expect(en).toHaveProperty(key);
    }
  });

  it("has no empty sentence in either language", () => {
    const blank = [...Object.entries(fr), ...Object.entries(en)]
      .filter(([, text]) => text.trim() === "")
      .map(([key]) => key);
    expect(blank).toEqual([]);
  });

  it("asks for the same interpolation values in both languages", () => {
    const mismatched: string[] = [];
    for (const [key, text] of Object.entries(fr)) {
      const a = placeholders(text);
      const b = placeholders(en[key] ?? "");
      if (a.join(",") !== b.join(",")) mismatched.push(`${key}: fr[${a}] vs en[${b}]`);
    }
    expect(mismatched).toEqual([]);
  });

  it("names all three of option 2's values in its full sentence", () => {
    /* The sentence the whole feature exists for. A template that lost one of
       the three would quietly stop telling a creator how long, or where. */
    for (const text of [fr.o2_full, en.o2_full]) {
      expect(placeholders(text)).toEqual(["duration", "media", "territories"]);
    }
    for (const text of [fr.o3_full, en.o3_full]) {
      expect(placeholders(text)).toEqual(["duration", "territories"]);
    }
  });

  it("interpolates nothing in the sentences that take no values", () => {
    for (const key of ["o1", "o2_head", "o3_head", "incomplete", "notStated"]) {
      expect(placeholders(fr[key])).toEqual([]);
      expect(placeholders(en[key])).toEqual([]);
    }
  });

  it("carries one value in each of the four field lines", () => {
    for (const key of ["f_duration", "f_territories", "f_media", "f_consideration"]) {
      expect(placeholders(fr[key])).toEqual(["value"]);
      expect(placeholders(en[key])).toEqual(["value"]);
    }
  });

  it("never claims Kolabo checked any of it", () => {
    /* The constraint lib/licenceStrings carries, and the one that is easiest
       to break while rewording: a stated licence is self declared contract
       content, and copy that implied otherwise would promise a guarantee the
       platform does not offer. */
    /* v[eé]rif, because the French for it is accented and an ASCII-only
       pattern would pass over "verifie" without ever looking at it, which is
       the trivially-green test this one replaced. */
    const banned = /v[eé]rif|\bverify|\bvalidat|\bchecked\b/i;
    const offenders: string[] = [];
    for (const [key, text] of [...Object.entries(fr), ...Object.entries(en)]) {
      /* formHint is the one sentence allowed to use the word, because it says
         the platform does NOT. */
      if (key === "formHint") continue;
      if (banned.test(text)) offenders.push(key);
    }
    expect(offenders).toEqual([]);
  });
});

/* The content-licence shape and the sentence a creator reads, asserted rather
   than assumed.

   lib/licenceTerms exists because one table is read by four things at once:
   the render order of the brand's form, the gate on its submit button, the
   body of the request, and the plain-language sentence the creator reads
   before accepting. The module's whole value is that those four cannot
   disagree, and a table nothing checks is a table that drifts.

   AND THE SHAPE IT TRAVELS IN IS NOW ASSERTED TOO, because that is what was
   wrong with it. The five names ride inside ONE `licence_terms` object, in and
   out, which is what the API takes and serves; this module wrote and read them
   flat at the top level of the carrier, so the brand's form was ignored and
   every creator-facing sentence reported "not stated" for a licence that was
   stated. No test caught it, because every test wrote the same flat shape the
   module did. The group below asserts the nesting from both directions and
   pins the flat shape as the WRONG answer, so a reader cannot accidentally
   agree with itself again.

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
  licenceTermsFor,
  missingFields,
  optionOf,
  redistributes,
  toPayload,
  valuesFrom,
  type LicenceField,
  type LicenceOption,
  type LicenceTerms,
  type LicenceValues,
  type StoredLicenceBlock,
} from "../src/lib/licenceTerms";

const STRINGS = fileURLToPath(new URL("../src/lib/licenceStrings.ts", import.meta.url));

const PLACEHOLDER = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g;

function placeholders(template: string): string[] {
  return [...template.matchAll(PLACEHOLDER)].map((m) => m[1]).sort();
}

/* A row as the API sends it: the block NESTED under licence_terms.

   Every reader below goes through this rather than writing the object out, so
   the nesting is stated in one place and a test cannot quietly assert the flat
   shape the module used to read. `carrier(null)` is the ordinary legacy row:
   the key is there and the column is empty. */
function carrier(block: StoredLicenceBlock | null): LicenceTerms {
  return { licence_terms: block };
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

describe("the block travels nested under licence_terms, in and out", () => {
  /* THE BUG THIS GROUP EXISTS FOR. campaigns/schemas.py declares
     LicenceTermsIn as a nested object on CampaignCreate, CampaignPatch,
     OrderIn and CartItemIn, serves it back as one dict on CampaignOut,
     ProposalOut and ContractDetailOut, and stores it as a single JSON column
     that campaigns/editing.py compares whole. This module used to write and
     read the five names flat at the top level of the body and of the carrier,
     which the real API ignores in one direction and never produces in the
     other. */

  it("puts everything it sends under one licence_terms key", () => {
    for (const option of LICENCE_OPTIONS) {
      expect(Object.keys(toPayload(option, filled(option)))).toEqual(["licence_terms"]);
    }
  });

  it("sends none of the five names at the top level of the body", () => {
    /* The flat shape pinned as the WRONG answer, in the direction the brand's
       form travels. A body carrying licence_option beside `title` is a body
       pydantic drops on the floor. */
    const body = toPayload("2", filled("2")) as unknown as Record<string, unknown>;
    for (const name of ["licence_option", ...Object.keys(EMPTY_VALUES)]) {
      expect(body[name]).toBeUndefined();
    }
  });

  it("reads the option out of the nested block", () => {
    expect(optionOf(carrier({ licence_option: "2" }))).toBe("2");
  });

  it("ignores the five names when they sit flat on the carrier", () => {
    /* The same pin, in the reading direction. A payload shaped the old way is
       a payload from nowhere, and answering "option 2" to it would mean this
       module still agreed with its own mistake. */
    const flat = { licence_option: "2", licence_duration: "12 mois" } as unknown as LicenceTerms;
    expect(optionOf(flat)).toBeNull();
    expect(valuesFrom(flat)).toEqual(EMPTY_VALUES);
    expect(licenceSentences(flat, stub)).toEqual([]);
  });

  it("treats a carrier with no block as nothing stated", () => {
    /* The ordinary legacy row: the campaign exists, the column is null, and
       there is nothing to backfill from. */
    expect(optionOf(carrier(null))).toBeNull();
    expect(valuesFrom(carrier(null))).toEqual(EMPTY_VALUES);
    expect(licenceSentences(carrier(null), stub)).toEqual([]);
  });

  it("survives a round trip from a stored block back into a body", () => {
    const stored: StoredLicenceBlock = {
      licence_option: "2",
      licence_duration: "12 mois a compter de la publication",
      licence_territories: "Benin et Togo",
      licence_media: "reseaux sociaux de la marque et affichage en magasin",
      licence_consideration: null,
    };
    const block = toPayload("2", valuesFrom(carrier(stored))).licence_terms;
    expect(block.licence_option).toBe("2");
    expect(block.licence_duration).toBe(stored.licence_duration);
    expect(block.licence_territories).toBe(stored.licence_territories);
    expect(block.licence_media).toBe(stored.licence_media);
  });
});

describe("optionOf reads what a payload states and guesses nothing", () => {
  it("reads each of the three", () => {
    for (const option of LICENCE_OPTIONS) {
      expect(optionOf(carrier({ licence_option: option }))).toBe(option);
    }
  });

  it("treats an absent, null or empty option as nothing stated", () => {
    expect(optionOf(null)).toBeNull();
    expect(optionOf(undefined)).toBeNull();
    expect(optionOf({})).toBeNull();
    expect(optionOf(carrier({}))).toBeNull();
    expect(optionOf(carrier({ licence_option: null }))).toBeNull();
    expect(optionOf(carrier({ licence_option: "" }))).toBeNull();
  });

  it("degrades an unrecognised option to nothing stated", () => {
    /* A fourth value is a row this client cannot describe, and the honest
       answer on screen is the one it gives an empty field. Guessing which
       option a stranger meant would put a sentence about paid advertising in
       front of a creator on no evidence. */
    expect(optionOf(carrier({ licence_option: "4" }))).toBeNull();
    expect(optionOf(carrier({ licence_option: "exclusive" }))).toBeNull();
    expect(optionOf(carrier({ licence_option: 2 } as unknown as StoredLicenceBlock))).toBeNull();
  });

  it("tolerates surrounding whitespace on an option it recognises", () => {
    expect(optionOf(carrier({ licence_option: " 2 " }))).toBe("2");
  });
});

describe("licenceTermsFor follows the backend's precedence", () => {
  /* THE RULE IS contracts.service._licence_snapshot's: the OFFER's block
     first, the brief's second. A brief states its licence on the campaign; a
     direct order states it on the brand's own proposal row, because there the
     proposal IS the offer. A client that resolved it the other way would show
     a creator one licence and have a different one written into the contract
     they accepted. */
  const order = carrier({ licence_option: "2", licence_duration: "12 mois" });
  const brief = carrier({ licence_option: "1" });

  it("takes the offer's block when the offer states one", () => {
    expect(licenceTermsFor(order, brief)).toBe(order);
    expect(optionOf(licenceTermsFor(order, brief))).toBe("2");
  });

  it("falls back to the brief when the offer states nothing", () => {
    /* Every proposal born of a brief is in this case: the licence is on the
       campaign and the chain states nothing. */
    expect(licenceTermsFor(carrier(null), brief)).toBe(brief);
    expect(licenceTermsFor(carrier({}), brief)).toBe(brief);
    expect(licenceTermsFor({}, brief)).toBe(brief);
  });

  it("falls back to the brief when there is no offer at all", () => {
    /* A brief nobody has priced yet carries no proposal. */
    expect(licenceTermsFor(null, brief)).toBe(brief);
    expect(licenceTermsFor(undefined, brief)).toBe(brief);
  });

  it("keeps the offer's block even when its option is one this build cannot read", () => {
    /* The difference between degrading and lying. optionOf answers null and
       the notice says the terms cannot be read here, which is honest; falling
       back to the BRIEF would print one party's clause in place of another's.
       The backend only asks whether the row has a block at all. */
    const strange = carrier({ licence_option: "4", licence_duration: "12 mois" });
    expect(licenceTermsFor(strange, brief)).toBe(strange);
    expect(licenceSentences(licenceTermsFor(strange, brief), stub)).toEqual([]);
  });

  it("answers null when neither side has anything", () => {
    expect(licenceTermsFor(null, null)).toBeNull();
    expect(licenceTermsFor(undefined, undefined)).toBeNull();
  });
});

describe("toPayload sends all four fields every time", () => {
  /* THE ONE PLACE THIS MODULE DEPARTS FROM lib/partyDetails, which omits a
     field its type does not ask for. A party block is replaced whole by a
     PUT; this block hangs off a campaign edited in pieces, so an omitted
     field is a field left at whatever it was. */
  const expectedKeys = ["licence_option", ...Object.keys(EMPTY_VALUES)].sort();

  it("sends exactly the same keys inside the block for every option", () => {
    for (const option of LICENCE_OPTIONS) {
      expect(Object.keys(toPayload(option, filled(option)).licence_terms).sort()).toEqual(expectedKeys);
    }
  });

  it("carries the option and every field that option asks for", () => {
    const block = toPayload("2", filled("2")).licence_terms;
    expect(block.licence_option).toBe("2");
    for (const field of FIELDS["2"]) expect(block[field]).toBe(`${field} value`);
  });

  it("nulls a field the chosen option does not ask for", () => {
    /* A brand that narrows its claim from option 2 to option 1 must not keep
       a stale twelve months and a stale territory list, because those would
       print on the contract underneath a sentence saying it has no
       redistribution right. */
    const block = toPayload("1", filled("2")).licence_terms;
    expect(block.licence_option).toBe("1");
    expect(block.licence_duration).toBeNull();
    expect(block.licence_territories).toBeNull();
    expect(block.licence_media).toBeNull();
    expect(block.licence_consideration).toBeNull();
  });

  it("nulls option 2's media when option 3 is chosen", () => {
    const block = toPayload("3", filled("2")).licence_terms;
    expect(block.licence_media).toBeNull();
    expect(block.licence_duration).toBe("licence_duration value");
  });

  it("trims, and turns a blank field into null", () => {
    const values = filled("2");
    values.licence_duration = "  12 mois  ";
    values.licence_media = "   ";
    const block = toPayload("2", values).licence_terms;
    expect(block.licence_duration).toBe("12 mois");
    expect(block.licence_media).toBeNull();
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

  it("sends no licence_terms key for nobody: an unanswered form is not option 1", () => {
    /* A block of five nulls is a brand stating that it claims nothing, which
       IS option 1. A caller handed null has to omit the key instead, which is
       what the `?? {}` at every call site does. */
    expect(draftPayload({ option: "", values: filled("2") })).toBeNull();
  });

  it("is complete as soon as option 1 is chosen", () => {
    expect(draftIsComplete({ option: "1", values: { ...EMPTY_VALUES } })).toBe(true);
    expect(draftPayload({ option: "1", values: { ...EMPTY_VALUES } })).toEqual({
      licence_terms: {
        licence_option: "1",
        licence_duration: null,
        licence_territories: null,
        licence_media: null,
        licence_consideration: null,
      },
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
    expect(valuesFrom(carrier(null))).toEqual(EMPTY_VALUES);
    expect(valuesFrom(carrier({}))).toEqual(EMPTY_VALUES);
  });

  it("turns a null field into an empty string rather than passing it through", () => {
    const values = valuesFrom(
      carrier({ licence_option: "2", licence_duration: "12 mois", licence_media: null })
    );
    expect(values.licence_duration).toBe("12 mois");
    expect(values.licence_media).toBe("");
  });

  it("never lets the option itself into the values record", () => {
    /* licence_option is the discriminator, not a field, so it has no slot
       here and there is no path by which the form can edit it as text. */
    const values = valuesFrom(carrier({ licence_option: "2" }));
    expect(Object.keys(values).sort()).toEqual(Object.keys(EMPTY_VALUES).sort());
    expect((values as Record<string, string>).licence_option).toBeUndefined();
  });

  it("keeps the field union and the empty record in step", () => {
    const fields: LicenceField[] = Object.keys(EMPTY_VALUES) as LicenceField[];
    for (const field of fields) expect(EMPTY_VALUES[field]).toBe("");
    expect(fields.length).toBe(4);
  });
});

describe("the sentence a creator reads before accepting", () => {
  it("says nothing at all when no option is stated", () => {
    /* The caller owns that case, because "the brand has not said" is a
       different piece of news from any of the three options and belongs in
       its own sentence. */
    expect(licenceSentences(null, stub)).toEqual([]);
    expect(licenceSentences({}, stub)).toEqual([]);
    expect(licenceSentences(carrier({}), stub)).toEqual([]);
    expect(licenceSentences(carrier({ licence_option: "4" }), stub)).toEqual([]);
  });

  it("states option 1 rather than printing nothing", () => {
    /* "No redistribution right" and "nobody mentioned the licence" look
       identical if the first prints nothing, and they end in different
       places. */
    expect(licenceSentences(carrier({ licence_option: "1" }), stub)).toEqual(["licence.o1"]);
  });

  it("ignores values left over under option 1", () => {
    /* A row that was option 2 before somebody narrowed it may still carry a
       duration if the request that narrowed it omitted the field. The
       sentence follows the option, not the leftovers. */
    const lines = licenceSentences(
      carrier({ licence_option: "1", licence_duration: "12 mois", licence_territories: "Benin" }),
      stub
    );
    expect(lines).toEqual(["licence.o1"]);
  });

  it("names the brand's own duration, territories and media in one sentence", () => {
    /* The happy path, and the whole point of the feature: one sentence, in
       the second person, with the stated values inside it. */
    const lines = licenceSentences(
      carrier({
        licence_option: "2",
        licence_duration: "12 mois",
        licence_territories: "Benin et Togo",
        licence_media: "publicite payante Meta",
      }),
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
      carrier({
        licence_option: "2",
        licence_duration: "6 mois",
        licence_territories: territories,
        licence_media: "Reels",
      }),
      stub
    );
    expect(lines[0]).toContain(`territories=${territories}`);
  });

  it("gives option 3 its headline and its consideration on a line of its own", () => {
    const lines = licenceSentences(
      carrier({
        licence_option: "3",
        licence_duration: "sans limite de duree",
        licence_territories: "monde entier",
        licence_consideration: "150000 XOF",
      }),
      stub
    );
    expect(lines).toHaveLength(2);
    expect(lines[0]).toContain("licence.o3_full");
    expect(lines[1]).toBe("licence.f_consideration[value=150000 XOF]");
  });

  it("leaves option 3's consideration out when none was agreed", () => {
    const lines = licenceSentences(
      carrier({ licence_option: "3", licence_duration: "2 ans", licence_territories: "Ghana" }),
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
      carrier({ licence_option: "2", licence_territories: "Benin", licence_media: "" }),
      stub
    );
    expect(lines[0]).toBe("licence.o2_head");
    expect(lines).toContain("licence.f_territories[value=Benin]");
    expect(lines[lines.length - 1]).toBe("licence.incomplete");
  });

  it("never leaves a hole where a value should be", () => {
    /* The assertion that would have caught the naive version: a template
       interpolated with nothing keeps its braces. */
    for (const block of [
      { licence_option: "2" },
      { licence_option: "2", licence_duration: "12 mois" },
      { licence_option: "3" },
      { licence_option: "3", licence_consideration: "100000 XOF" },
    ] as StoredLicenceBlock[]) {
      for (const line of licenceSentences(carrier(block), stub)) {
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
      expect(licenceSentences(carrier({ licence_option: option }), stub).length).toBeGreaterThan(0);
      expect(
        licenceSentences(carrier({ licence_option: option, ...filled(option) }), stub).length
      ).toBeGreaterThan(0);
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

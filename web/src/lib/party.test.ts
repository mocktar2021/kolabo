/* The party-details field map, asserted.

   lib/party.ts holds one table that three things read at once: the form
   renders it (pages/PartyDetails.tsx), the Save gate counts it
   (partyIsComplete), and the request is built from it (partyBody). That is the
   whole reason it is a module rather than three branches written out on a
   screen, and a table nothing asserts is a table that drifts.

   WHAT THESE CASES ARE REALLY GUARDING is the agreement between this table and
   REQUIRED_BY_TYPE in backend/app/modules/profiles/party_details.py. Nothing
   else checks that pair: a form short of a required field refuses nothing on
   its own, it just produces party_details_invalid after somebody has filled in
   everything else, which is the exact experience the client-side gate exists to
   prevent. So the required sets below are written out field for field rather
   than derived, and they are what fails if either side moves.

   The mobile half of this feature has the equivalent suite over its own
   module. Two clients implementing one rule with a test on one of them is
   worse than a test on neither, because the green build reads as cover for
   both.

   No network and no React: every function under test is pure. */
import { describe, expect, it } from "vitest";

import {
  PARTY_FIELDS,
  PARTY_TYPES,
  partyBody,
  partyIsComplete,
  partyValues,
  type PartyField
} from "./party";
import type { PartyDetails, PartyType } from "./types";

/* A complete answer to every field of every branch, so a case can pick a
   party_type and ask what travels. Keyed exactly as the request is, which is
   also how the form holds its state: ONE flat record for all three branches,
   deliberately, so switching the first question does not wipe the address
   somebody already typed. */
const EVERYTHING: Record<string, string> = {
  legal_name: "SARL Kolabo",
  legal_form: "SARL",
  registration_number: "RB/COT/26 A 119654",
  tax_identifier: "1200900488800",
  address: "C 1357 Houeyiho, 07BP91, Cotonou",
  country: "BJ",
  representative_name: "Ama K.",
  representative_capacity: "Gerante"
};

function keysOf(type: PartyType, values: Record<string, string>): string[] {
  return Object.keys(partyBody(type, values)).sort();
}

function requiredOf(type: PartyType): string[] {
  return PARTY_FIELDS[type]
    .filter((field) => field.required)
    .map((field) => field.name as string)
    .sort();
}

function optionalOf(type: PartyType): string[] {
  return PARTY_FIELDS[type]
    .filter((field) => !field.required)
    .map((field) => field.name as string)
    .sort();
}

describe("each form asks for what the server asks for", () => {
  /* Mirrors REQUIRED_BY_TYPE and OPTIONAL_BY_TYPE in
     backend/app/modules/profiles/party_details.py, plus the common fields every
     block carries. If one of these fails, read that file before this one: the
     server is the side that refuses. */

  it("asks a registered company for its register entry and who signs", () => {
    expect(requiredOf("registered_company")).toEqual([
      "address",
      "country",
      "legal_form",
      "legal_name",
      "registration_number",
      "representative_capacity",
      "representative_name",
      "tax_identifier"
    ]);
    expect(optionalOf("registered_company")).toEqual([]);
  });

  it("asks somebody trading in their own name for a name and where to find them", () => {
    /* THE SHORTEST BRANCH, AND IT IS COMPLETE RATHER THAN REDUCED. Businesses
       on Kolabo are not limited to registered ones, so a natural person states
       a name, an address and a country and there is nothing else to ask: no
       register entry exists to quote, and nobody is representing anybody. The
       tax identifier is the one optional field in the whole table, because
       plenty of people trading in their own name in the launch markets hold
       none and a demanded one would be invented. */
    expect(requiredOf("sole_trader")).toEqual(["address", "country", "legal_name"]);
    expect(optionalOf("sole_trader")).toEqual(["tax_identifier"]);
  });

  it("asks an association for its register entry but not for a tax identifier", () => {
    expect(requiredOf("association")).toEqual([
      "address",
      "country",
      "legal_name",
      "registration_number",
      "representative_capacity",
      "representative_name"
    ]);
    expect(optionalOf("association")).toEqual([]);
  });

  it("asks every form for the three fields every block carries", () => {
    for (const type of PARTY_TYPES) {
      expect(requiredOf(type)).toContain("legal_name");
      expect(requiredOf(type)).toContain("address");
      expect(requiredOf(type)).toContain("country");
    }
  });

  it("gives every field a label and never repeats one within a form", () => {
    /* A field with no label renders an empty <label> above an input nobody can
       identify, and two fields sharing one label are two boxes asking the same
       question. */
    for (const type of PARTY_TYPES) {
      const labels = PARTY_FIELDS[type].map((field) => field.labelKey);
      expect(labels.every((key) => key.length > 0)).toBe(true);
      expect(new Set(labels).size).toBe(labels.length);
      const names = PARTY_FIELDS[type].map((field) => field.name);
      expect(new Set(names).size).toBe(names.length);
    }
  });
});

describe("display_label never reaches a payload", () => {
  /* Derived server side from the legal name. A client that sent one would be
     deciding how the other party is named on a contract, and the point of
     deriving it is that there is exactly one rule for that name rather than
     one per app. */

  it("is not a field of any form", () => {
    for (const type of PARTY_TYPES) {
      const names: string[] = PARTY_FIELDS[type].map((field) => field.name as string);
      expect(names).not.toContain("display_label");
    }
  });

  it("is dropped from the values a stored block was read into", () => {
    /* The round trip that would leak it if partyBody copied the record instead
       of iterating the table: a GET answers a block carrying a label, the form
       loads those values, and the next save must not send it back. */
    const stored: PartyDetails = {
      party_type: "sole_trader",
      display_label: "Ama K.",
      legal_name: "Ama Kouassi",
      address: "Rue 12, Cotonou",
      country: "BJ",
      legal_form: null,
      registration_number: null,
      tax_identifier: null,
      representative_name: null,
      representative_capacity: null
    };
    const body = partyBody("sole_trader", partyValues(stored)) as unknown as Record<string, string>;
    expect(Object.keys(body).sort()).toEqual(["address", "country", "legal_name", "party_type"]);
    expect(body.legal_name).toBe("Ama Kouassi");
  });
});

describe("only the chosen form travels", () => {
  it("sends a sole trader three fields out of eight answers", () => {
    expect(keysOf("sole_trader", EVERYTHING)).toEqual([
      "address",
      "country",
      "legal_name",
      "party_type",
      "tax_identifier"
    ]);
  });

  it("sends an association no legal form and no tax identifier", () => {
    const keys = keysOf("association", EVERYTHING);
    expect(keys).not.toContain("legal_form");
    expect(keys).not.toContain("tax_identifier");
    expect(keys).toContain("registration_number");
  });

  it("sends a registered company everything it asks for", () => {
    expect(keysOf("registered_company", EVERYTHING)).toEqual([
      "address",
      "country",
      "legal_form",
      "legal_name",
      "party_type",
      "registration_number",
      "representative_capacity",
      "representative_name",
      "tax_identifier"
    ]);
  });

  it("leaves an empty optional field out rather than sending a blank", () => {
    /* Every input the form renders sends something, so an untouched optional
       field arrives as "". Storing that would put a key on the block saying
       this party stated an empty tax identifier, which nobody stated, and the
       renderer would print a heading with nothing under it. */
    const keys = keysOf("sole_trader", { ...EVERYTHING, tax_identifier: "   " });
    expect(keys).not.toContain("tax_identifier");
  });

  it("trims what it does send", () => {
    const body = partyBody("sole_trader", {
      ...EVERYTHING,
      legal_name: "  Ama Kouassi  "
    }) as unknown as Record<string, string>;
    expect(body.legal_name).toBe("Ama Kouassi");
  });

  it("carries the party_type it was given", () => {
    for (const type of PARTY_TYPES) {
      const body = partyBody(type, EVERYTHING) as unknown as Record<string, string>;
      expect(body.party_type).toBe(type);
    }
  });
});

describe("the save gate counts the chosen form and not another", () => {
  it("holds a registered company to its registration number", () => {
    const values = { ...EVERYTHING, registration_number: "" };
    expect(partyIsComplete("registered_company", values)).toBe(false);
    /* The same answers are a complete sole trader block, which is the whole
       point of asking the first question first. */
    expect(partyIsComplete("sole_trader", values)).toBe(true);
  });

  it("never holds a sole trader to a tax identifier", () => {
    const values = { ...EVERYTHING, tax_identifier: "" };
    expect(partyIsComplete("sole_trader", values)).toBe(true);
  });

  it("does not accept whitespace as an answer", () => {
    /* A name of three spaces would print as a party of three spaces on a
       signed document. The server collapses and refuses it too. */
    expect(partyIsComplete("sole_trader", { ...EVERYTHING, legal_name: "   " })).toBe(false);
    expect(partyIsComplete("sole_trader", { ...EVERYTHING, address: " " })).toBe(false);
  });

  it("refuses an empty form for every type", () => {
    for (const type of PARTY_TYPES) {
      expect(partyIsComplete(type, {})).toBe(false);
    }
  });
});

describe("a stored block comes back into the form", () => {
  it("answers an empty record for a user who has stated nothing", () => {
    expect(partyValues(null)).toEqual({});
  });

  it("fills every field it has and an empty string for the rest", () => {
    const stored: PartyDetails = {
      party_type: "association",
      display_label: "ONG Lumiere",
      legal_name: "ONG Lumiere",
      address: "Lome",
      country: "TG",
      registration_number: "ASSOC/2024/118",
      representative_name: "Kofi A.",
      representative_capacity: "President"
    };
    const values = partyValues(stored);
    expect(values.registration_number).toBe("ASSOC/2024/118");
    /* Absent on this block because an association is never asked for one.
       Empty rather than missing, so the form's inputs are always controlled
       and React never swaps one between controlled and uncontrolled. */
    expect(values.tax_identifier).toBe("");
    expect(values.legal_form).toBe("");
  });

  it("round trips a block through the form and back to the same body", () => {
    /* What happens when somebody opens the screen and presses save without
       changing anything: the block that comes back has to be the block that
       went in, or every visit quietly edits the party on the next contract. */
    const stored: PartyDetails = {
      party_type: "registered_company",
      display_label: "SARL Kolabo",
      legal_name: "SARL Kolabo",
      legal_form: "SARL",
      registration_number: "RB/COT/26 A 119654",
      tax_identifier: "1200900488800",
      address: "C 1357 Houeyiho, 07BP91, Cotonou",
      country: "BJ",
      representative_name: "Ama K.",
      representative_capacity: "Gerante"
    };
    const body = partyBody(stored.party_type, partyValues(stored)) as unknown as Record<string, string>;
    for (const field of PARTY_FIELDS.registered_company) {
      const name: PartyField = field.name;
      expect(body[name]).toBe(stored[name]);
    }
  });
});

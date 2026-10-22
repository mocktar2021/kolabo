/* The party-details shape, asserted rather than assumed.

   lib/partyDetails exists because one table is read by three things at once:
   the render order of the form, the gate on its Save button, and the body of
   the PUT. The module's whole value is that those three cannot disagree, and a
   table nothing checks is a table that drifts, so this is the check.

   Two of the tests below are about rules that are STRUCTURAL in the module
   rather than enforced by a filter, which is exactly the kind of rule that
   quietly stops holding:

     display_label has no entry in FIELDS, and toPayload iterates FIELDS, so
     there is no path by which it reaches a request. That is a property of the
     arrangement, not a line of code anybody would notice deleting.

     PartyValues holds every field whatever type is selected, deliberately, so
     that switching type to read what it asks does not throw away typing. The
     cost is that the state routinely holds fields the selected type must not
     send, and toPayload dropping them is the only thing between that and a
     sole trader stored with a legal form. */
import { describe, expect, it } from "vitest";

import {
  EMPTY_VALUES,
  FIELDS,
  OPTIONAL,
  PARTY_TYPES,
  isComplete,
  isOptional,
  missingFields,
  toPayload,
  valuesFrom,
  type PartyField,
  type PartyType,
  type PartyValues,
} from "../src/lib/partyDetails";

/* A filled block for one type, so a test about one field does not have to
   write out seven others that are not the point. */
function filled(type: PartyType): PartyValues {
  const values = { ...EMPTY_VALUES };
  for (const field of FIELDS[type]) values[field] = `${field} value`;
  return values;
}

describe("the three types and their tables line up", () => {
  it("has a field list and an exception list for every type", () => {
    expect(Object.keys(FIELDS).sort()).toEqual([...PARTY_TYPES].sort());
    expect(Object.keys(OPTIONAL).sort()).toEqual([...PARTY_TYPES].sort());
  });

  it("names every field in a shape the form state can hold", () => {
    /* A field in FIELDS with no slot in PartyValues would render an
       uncontrolled input that loses what is typed into it on the next
       render. */
    const known = Object.keys(EMPTY_VALUES);
    for (const type of PARTY_TYPES) {
      for (const field of FIELDS[type]) expect(known).toContain(field);
    }
  });

  it("marks optional only fields the type actually asks for", () => {
    /* An optional field that is not in the type's list is a dead entry, and a
       dead entry reads as though a field were being asked for somewhere. */
    for (const type of PARTY_TYPES) {
      for (const field of OPTIONAL[type]) expect(FIELDS[type]).toContain(field);
    }
  });

  it("asks every type for a legal name, an address and a country", () => {
    /* The four fields the contract body needs on every party block, whatever
       kind of entity it is: a name to print, where it is, and the country it
       contracts from. display_label is derived from the first of them. */
    for (const type of PARTY_TYPES) {
      expect(FIELDS[type]).toContain("legal_name");
      expect(FIELDS[type]).toContain("address");
      expect(FIELDS[type]).toContain("country");
      expect(isOptional(type, "legal_name")).toBe(false);
    }
  });

  it("never lists display_label as a field of any type", () => {
    /* The structural half of the rule. The other half is asserted against a
       built payload further down. */
    for (const type of PARTY_TYPES) {
      expect(FIELDS[type] as string[]).not.toContain("display_label");
    }
    expect(Object.keys(EMPTY_VALUES)).not.toContain("display_label");
  });
});

describe("each type asks for what it should", () => {
  it("requires a registration number of a registered company", () => {
    const values = filled("registered_company");
    values.registration_number = "";
    expect(missingFields("registered_company", values)).toEqual(["registration_number"]);
    expect(isComplete("registered_company", values)).toBe(false);
  });

  it("never asks a sole trader for a registration number at all", () => {
    /* Not merely optional: absent. Asking an unregistered trader for a
       registration number is the reading the spec says this branch must not
       have, and an optional-but-present field still reads as something
       missing. */
    expect(FIELDS.sole_trader).not.toContain("registration_number");
    expect(FIELDS.sole_trader).not.toContain("legal_form");
    expect(FIELDS.sole_trader).not.toContain("representative_name");
  });

  it("lets a sole trader leave the tax identifier blank", () => {
    const values = filled("sole_trader");
    values.tax_identifier = "";
    expect(isOptional("sole_trader", "tax_identifier")).toBe(true);
    expect(missingFields("sole_trader", values)).toEqual([]);
    expect(isComplete("sole_trader", values)).toBe(true);
  });

  it("requires the tax identifier of a registered company", () => {
    /* THE ONE PLACE THE CLIENT IS STRICTER THAN THE SPEC'S TEST LIST, which
       names only the registration number as required for a company. The field
       list it gives for a company includes the tax identifier unmarked, and
       marks one optional only on the sole trader branch, so that is what the
       module follows. If the backend turns out to accept it empty, this test
       and OPTIONAL.registered_company are what change, together. */
    const values = filled("registered_company");
    values.tax_identifier = "";
    expect(missingFields("registered_company", values)).toEqual(["tax_identifier"]);
  });

  it("asks an association for a representative but not a legal form", () => {
    /* An association signs through a person, so the representative pair stays.
       Its legal form is what it is called, so there is nothing to ask. */
    expect(FIELDS.association).toContain("representative_name");
    expect(FIELDS.association).toContain("representative_capacity");
    expect(FIELDS.association).not.toContain("legal_form");
  });

  it("reports everything missing in render order", () => {
    /* The order is load-bearing: the form points the reader at the first thing
       to fix, and a set in some other order would point at the wrong one. */
    expect(missingFields("association", { ...EMPTY_VALUES })).toEqual(FIELDS.association);
  });

  it("does not accept whitespace as an answer", () => {
    /* A legal name of three spaces would print as a party of three spaces on
       a contract, which is worse than an empty one because it looks filled. */
    const values = filled("sole_trader");
    values.legal_name = "   ";
    expect(missingFields("sole_trader", values)).toEqual(["legal_name"]);
  });
});

describe("toPayload sends the type's own fields and nothing else", () => {
  it("carries the party type and every field of that type", () => {
    const body = toPayload("registered_company", filled("registered_company"));
    expect(body.party_type).toBe("registered_company");
    for (const field of FIELDS.registered_company) expect(body[field]).toBe(`${field} value`);
  });

  it("drops a field belonging to a type the reader switched away from", () => {
    /* The form state keeps the company answers on purpose, so switching type
       to read what it asks does not throw away typing. This is what stops
       those answers being stored against a party that has no such field. */
    const values = filled("registered_company");
    values.legal_name = "Ama K.";
    values.address = "Quartier Haie Vive, Cotonou";
    values.country = "BJ";
    const body = toPayload("sole_trader", values);
    expect(Object.keys(body).sort()).toEqual(["party_type", ...FIELDS.sole_trader].sort());
    expect(body.legal_form).toBeUndefined();
    expect(body.registration_number).toBeUndefined();
    expect(body.representative_name).toBeUndefined();
    expect(body.legal_name).toBe("Ama K.");
  });

  it("never sends display_label, even when the GET supplied one", () => {
    /* The behavioural half of the rule. A server-derived label comes back on
       every read, so the risk is not somebody typing one: it is a round trip
       carrying it back out again. */
    const values = valuesFrom({
      party_type: "sole_trader",
      display_label: "Ama K.",
      legal_name: "Ama K.",
      address: "Cotonou",
      country: "BJ",
    });
    const body = toPayload("sole_trader", values);
    expect(body).not.toHaveProperty("display_label");
    expect(Object.values(body)).not.toContain("Ama K. the label");
  });

  it("trims, and turns a blank optional field into null", () => {
    /* null clears the stored value; "" would store a blank string, which then
       prints as a blank line on a contract. */
    const values = filled("sole_trader");
    values.legal_name = "  Ama K.  ";
    values.tax_identifier = "   ";
    const body = toPayload("sole_trader", values);
    expect(body.legal_name).toBe("Ama K.");
    expect(body.tax_identifier).toBeNull();
  });
});

describe("valuesFrom reads a GET into form state", () => {
  it("gives every field an empty string when there is no block yet", () => {
    /* A 404 is the normal state of a profile that has not filled this in, and
       a controlled TextInput cannot hold null. */
    expect(valuesFrom(null)).toEqual(EMPTY_VALUES);
    expect(valuesFrom(undefined)).toEqual(EMPTY_VALUES);
  });

  it("turns a null field into an empty string rather than passing it through", () => {
    const values = valuesFrom({ party_type: "sole_trader", legal_name: "Ama K.", tax_identifier: null });
    expect(values.legal_name).toBe("Ama K.");
    expect(values.tax_identifier).toBe("");
  });

  it("survives a round trip through toPayload", () => {
    const stored = {
      party_type: "association" as PartyType,
      display_label: "Les Amis du Fleuve",
      legal_name: "Les Amis du Fleuve",
      registration_number: "RCCM/BJ/2024/B/1234",
      address: "Rue 12, Porto-Novo",
      country: "BJ",
      representative_name: "Koffi A.",
      representative_capacity: "Président",
    };
    const body = toPayload("association", valuesFrom(stored));
    for (const field of FIELDS.association) {
      expect(body[field]).toBe(stored[field as keyof typeof stored] as string);
    }
    expect(body).not.toHaveProperty("display_label");
  });

  it("ignores a field the API sends that no type asks for", () => {
    /* A backend that grows a field before the form does should not crash the
       screen. valuesFrom reads the fields it knows about and leaves the rest
       where they are. */
    const values = valuesFrom({
      party_type: "sole_trader",
      legal_name: "Ama K.",
      ...({ something_new: "x" } as Record<string, string>),
    } as Parameters<typeof valuesFrom>[0]);
    expect(Object.keys(values).sort()).toEqual(Object.keys(EMPTY_VALUES).sort());
    expect((values as Record<string, string>).something_new).toBeUndefined();
  });

  it("keeps the field union and the empty record in step", () => {
    /* If a PartyField is added to the union without a slot in EMPTY_VALUES,
       this is where it is noticed. The cast is the assertion: it only compiles
       while the two agree. */
    const fields: PartyField[] = Object.keys(EMPTY_VALUES) as PartyField[];
    expect(fields.length).toBe(Object.keys(EMPTY_VALUES).length);
    for (const field of fields) expect(EMPTY_VALUES[field]).toBe("");
  });
});

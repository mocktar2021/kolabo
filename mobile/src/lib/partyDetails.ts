/* Party details: who signs a contract, as each side states it about itself.

   Mirrors the party block in claude/kolabo-contract-parties-spec.md section 3.
   The platform records what a party declares and checks none of it, exactly as
   a paper contract would, so nothing in this module or in the copy that reads
   from it may present a field as verified.

   WHY A MODULE AND NOT A FORM. The block has a VARIABLE SHAPE: the first
   question is the party type, and the answer decides which fields are asked.
   Three things need that table at once, and they disagree the moment there is
   more than one copy of it:

     the render order, because a form has to draw the fields in some order;
     the completeness check, which decides whether Save is tappable;
     the request body, which must carry the type's own fields and no others.

   FIELDS below is all three. It is read by missingFields() and by toPayload()
   rather than restated in either, so adding a field to a type puts it on the
   form, makes it required unless OPTIONAL says otherwise, and sends it, from
   one edit in one place.

   THE SAME SHAPE SERVES BOTH SIDES. A creator block is a sole trader in
   practice and a business block is usually a registered company, but the shape
   is one shape, so one renderer serves both screens and an agency account can
   state a company without a second form existing. */

export type PartyType = "registered_company" | "sole_trader" | "association";

/* The order the three are offered in. Registered company first because it is
   the commonest answer on the business side, NOT because it is the expected
   one: per the spec, businesses on Kolabo are not limited to registered ones,
   and a sole trader must be as easy to complete as a company and must not read
   as a lesser option. The copy in lib/partyStrings.ts carries that weight; the
   order here is only an order. */
export const PARTY_TYPES: PartyType[] = ["registered_company", "sole_trader", "association"];

export type PartyField =
  | "legal_name"
  | "legal_form"
  | "registration_number"
  | "tax_identifier"
  | "address"
  | "country"
  | "representative_name"
  | "representative_capacity";

/* What the API returns. `display_label` is present here because a GET carries
   it, and it is the only field with no entry in FIELDS below, which is what
   stops it ever reaching a payload: it is DERIVED SERVER SIDE from legal_name
   for every type, and a client that sent one would be deciding how a party is
   named on a contract it does not write. */
export type PartyDetails = {
  party_type: PartyType;
  display_label?: string | null;
  legal_name?: string | null;
  legal_form?: string | null;
  registration_number?: string | null;
  tax_identifier?: string | null;
  address?: string | null;
  country?: string | null;
  representative_name?: string | null;
  representative_capacity?: string | null;
};

/* Per type: the fields asked, in the order they are drawn.

   `address` is one free-text field rather than a structured set of lines. That
   is the spec's choice and it is the right one for these markets, where a
   usable address is often a landmark and a quarter rather than a street number
   that exists. */
export const FIELDS: Record<PartyType, PartyField[]> = {
  registered_company: [
    "legal_name",
    "legal_form",
    "registration_number",
    "tax_identifier",
    "address",
    "country",
    "representative_name",
    "representative_capacity",
  ],
  /* A natural person contracting in their own name. No registration number and
     no representative, because they represent themselves: asking either would
     be asking somebody unregistered to prove a registration, which is the
     exact reading the spec says this branch must not have. */
  sole_trader: ["legal_name", "address", "country", "tax_identifier"],
  /* No legal form: an association's form is what it is called. It keeps the
     representative pair, because an association signs through a person. */
  association: [
    "legal_name",
    "registration_number",
    "address",
    "country",
    "representative_name",
    "representative_capacity",
  ],
};

/* The exceptions. Everything in FIELDS is required unless it is listed here.

   ONE FIELD IS STRICTER HERE THAN THE API MAY BE. The spec lists
   tax_identifier among a registered company's fields without marking it
   optional, and marks it optional only on the sole trader branch, so that is
   what this follows. But the spec's own test list names only the registration
   number as required for a company, so the backend may well accept an empty
   tax identifier.

   Being stricter costs a field somebody fills that the API would have taken
   empty. Being laxer costs a refusal after a round trip, which on a handset on
   a slow connection is the worse of the two. If the backend turns out to
   accept it empty, add it to registered_company here and nothing else in this
   module or the form changes. */
export const OPTIONAL: Record<PartyType, PartyField[]> = {
  registered_company: [],
  sole_trader: ["tax_identifier"],
  association: [],
};

export function isOptional(type: PartyType, field: PartyField): boolean {
  return OPTIONAL[type].includes(field);
}

/* The form's state: every field, always, whichever type is selected.

   Deliberately not narrowed to the selected type. Somebody who fills a company
   block, switches to sole trader to read what it asks, and switches back should
   find their typing where they left it, and a state shaped to the current type
   would have thrown it away on the first switch. toPayload() is what keeps the
   extra values out of the request. */
export type PartyValues = Record<PartyField, string>;

export const EMPTY_VALUES: PartyValues = {
  legal_name: "",
  legal_form: "",
  registration_number: "",
  tax_identifier: "",
  address: "",
  country: "",
  representative_name: "",
  representative_capacity: "",
};

/* A GET response into form state. Null and absent both become "", because a
   controlled TextInput cannot hold null and an uncontrolled one loses the
   value on the next render. */
export function valuesFrom(details: PartyDetails | null | undefined): PartyValues {
  if (!details) return { ...EMPTY_VALUES };
  const out = { ...EMPTY_VALUES };
  for (const field of Object.keys(EMPTY_VALUES) as PartyField[]) {
    out[field] = details[field] ?? "";
  }
  return out;
}

/* What is still blank, in render order, so the form can both disable Save and
   point at the right fields. Whitespace is not an answer: a name of three
   spaces would print as a party of three spaces on a contract. */
export function missingFields(type: PartyType, values: PartyValues): PartyField[] {
  return FIELDS[type].filter((field) => !isOptional(type, field) && values[field].trim() === "");
}

export function isComplete(type: PartyType, values: PartyValues): boolean {
  return missingFields(type, values).length === 0;
}

/* The PUT body, and the only thing that builds one.

   Two rules hold here that are invisible at the call site, which is why this
   is a function and not an inline object literal in the form:

     ONLY THE TYPE'S OWN FIELDS TRAVEL. A legal form typed before the reader
     switched to sole trader stays in the form state (see PartyValues) and is
     dropped from the request, rather than being stored against a party that
     has no legal form.

     display_label NEVER TRAVELS. It has no entry in FIELDS, so there is no
     path by which it can be added here by accident.

   Empty becomes null rather than "", so clearing an optional field clears the
   stored value instead of storing a blank string that would then print as a
   blank line on a contract. */
export function toPayload(type: PartyType, values: PartyValues): Record<string, string | null> {
  const body: Record<string, string | null> = { party_type: type };
  for (const field of FIELDS[type]) {
    const value = values[field].trim();
    body[field] = value === "" ? null : value;
  }
  return body;
}

/* The party-details block: which fields each form of party states, and the two
   calls that read and write them.

   A FEATURE-SCOPED lib file, for the reason lib/checkout.ts gives for being
   one: the field map below is read by one screen and one card, the two calls
   by those, and lib/types.ts is already 29 KB of shared API shapes. THE SHAPES
   THEMSELVES DO LIVE IN types.ts, because a contract carries two of them and
   the contract page reads a block without importing anything from here except
   the field order.

   NOTHING HERE VERIFIES ANYTHING, and `required` below is not verification. It
   says which blanks a form fills in before the server will accept the block,
   which is the same thing the blanks on a paper contract say. Kolabo records
   what each party states about itself and checks none of it. See the note on
   PartyType in lib/types.ts, and party.notVerified in lib/partyStrings.ts for
   the sentence that says so to the person filling it in. */
import { api } from "./api";
import type { PartyDetails, PartyDetailsInput, PartyType } from "./types";

/* Every key the PUT accepts except the discriminator. Typed off
   PartyDetailsInput rather than written out a second time, so a field renamed
   in types.ts fails to compile here instead of quietly addressing a key the
   server does not read. */
export type PartyField = keyof Omit<PartyDetailsInput, "party_type">;

export type PartyFieldSpec = {
  name: PartyField;
  /* The i18n key under party.*, SPELLED OUT RATHER THAN BUILT from the field
     name, because three branches label the same field differently: a company
     states its registered name, somebody trading in their own name states
     their own, an association states the association's. A key built from
     `name` would have needed a lookup table beside it to say the same thing,
     and the table would have been the real list. */
  labelKey: string;
  /* The line under the field, present where one earns its place. Mostly it
     names the local document a number comes from, because "registration
     number" means an RCCM entry to one reader and something else to the next. */
  hintKey: string | null;
  required: boolean;
};

/* The three forms a party can take, in the order the form offers them.

   THE ORDER IS NOT A RANKING and must not be allowed to become one. The
   founder's rule is that businesses on Kolabo are not limited to registered
   ones, so the sole_trader branch gets the same controls and the same
   prominence as the other two, and party.equalForms says in both languages
   that the three are equal here. What makes that true is the identical
   treatment below, not the sequence. */
export const PARTY_TYPES: readonly PartyType[] = [
  "registered_company",
  "sole_trader",
  "association"
];

/* A company or a firm entered in a register. The longest branch, because a
   registered entity really does have more to state: the register it is in, the
   number it is in there under, its tax identifier, and the human being who
   signs for it, who is not the same thing as the entity. */
const REGISTERED_COMPANY: readonly PartyFieldSpec[] = [
  { name: "legal_name", labelKey: "legalNameCompany", hintKey: null, required: true },
  { name: "legal_form", labelKey: "legalForm", hintKey: "legalFormHint", required: true },
  { name: "registration_number", labelKey: "registrationNumber", hintKey: "registrationNumberHint", required: true },
  { name: "tax_identifier", labelKey: "taxIdentifier", hintKey: "taxIdentifierHint", required: true },
  { name: "address", labelKey: "address", hintKey: "addressHint", required: true },
  { name: "country", labelKey: "country", hintKey: null, required: true },
  { name: "representative_name", labelKey: "representativeName", hintKey: "representativeNameHint", required: true },
  { name: "representative_capacity", labelKey: "representativeCapacity", hintKey: "representativeCapacityHint", required: true }
];

/* Somebody contracting under their own name, with no registered entity behind
   them. Three required fields and one optional one, and that is not a thinner
   version of the branch above: it is the whole truth about this party. There
   is no registration number, so none is asked for, and there is nobody
   representing anybody, so no representative is asked for either. A form that
   demanded either would be asking for a document that does not exist. */
const SOLE_TRADER: readonly PartyFieldSpec[] = [
  { name: "legal_name", labelKey: "legalNamePerson", hintKey: null, required: true },
  { name: "address", labelKey: "address", hintKey: "addressHint", required: true },
  { name: "country", labelKey: "country", hintKey: null, required: true },
  /* Optional, and the only optional field in the file. Plenty of people
     trading in their own name in the pilot markets hold no tax identifier, and
     one that is demanded would be invented. */
  { name: "tax_identifier", labelKey: "taxIdentifier", hintKey: "taxIdentifierOptionalHint", required: false }
];

/* A declared association, an NGO or an equivalent body. Registered and
   represented like a company, but with no legal form to choose from and no tax
   identifier asked for: the ones in these markets are entered in a register of
   associations rather than of companies. */
const ASSOCIATION: readonly PartyFieldSpec[] = [
  { name: "legal_name", labelKey: "legalNameAssociation", hintKey: null, required: true },
  { name: "registration_number", labelKey: "registrationNumber", hintKey: "registrationNumberHint", required: true },
  { name: "address", labelKey: "address", hintKey: "addressHint", required: true },
  { name: "country", labelKey: "country", hintKey: null, required: true },
  { name: "representative_name", labelKey: "representativeName", hintKey: "representativeNameHint", required: true },
  { name: "representative_capacity", labelKey: "representativeCapacity", hintKey: "representativeCapacityHint", required: true }
];

/* WHICH FIELDS BELONG TO WHICH FORM, read by three places that would otherwise
   each hold their own opinion: the form renders this, the contract page's block
   iterates it to decide which rows a stored block has, and partyBody below
   sends exactly the keys it names. A field added to a branch therefore appears
   on the form, in the request and on the contract in one edit. */
export const PARTY_FIELDS: Record<PartyType, readonly PartyFieldSpec[]> = {
  registered_company: REGISTERED_COMPANY,
  sole_trader: SOLE_TRADER,
  association: ASSOCIATION
};

/* Whether the chosen branch has everything it needs.

   Mirrors what the server checks rather than replacing it: a request that
   skipped the form is refused with party_details_invalid, and
   lib/errorMessages.ts has that sentence in both languages. What this buys is
   a disabled button instead of a refusal after eight fields have been typed. */
export function partyIsComplete(type: PartyType, values: Record<string, string>): boolean {
  return PARTY_FIELDS[type].every(
    (field) => !field.required || (values[field.name] ?? "").trim() !== ""
  );
}

/* The request body for the chosen branch, and ONLY for the chosen branch.

   A field belonging to another form is not sent as null, it is not sent at
   all: the block is read whole and printed on a contract, so a key carrying an
   empty string is a blank line under a heading nobody filled in. The same goes
   for an optional field left empty.

   display_label IS NOT BUILT HERE, deliberately. The server derives it from
   legal_name at capture for every party_type. A client that sent one would be
   naming the other party on a contract, and the point of deriving it is that
   there is exactly one rule for that name rather than one per app. */
export function partyBody(type: PartyType, values: Record<string, string>): PartyDetailsInput {
  const body: Record<string, string> = { party_type: type };
  for (const field of PARTY_FIELDS[type]) {
    const value = (values[field.name] ?? "").trim();
    if (value) body[field.name] = value;
  }
  /* The one place this file leaves the type system, and it is narrow.
     PARTY_FIELDS decides which keys land in the record and its `name` is typed
     as a key of PartyDetailsInput, so the two cannot drift without a compile
     error up at PartyFieldSpec. partyIsComplete is what guarantees the
     required keys are present before a caller gets here. */
  return body as unknown as PartyDetailsInput;
}

/* A saved block, flattened back into the form's state.

   Every field of every branch, not just the saved branch's: switching the
   first question must not wipe the address somebody already typed, and the
   three fields common to all three forms are exactly the ones worth keeping. */
export function partyValues(details: PartyDetails | null): Record<string, string> {
  if (!details) return {};
  return {
    legal_name: details.legal_name ?? "",
    legal_form: details.legal_form ?? "",
    registration_number: details.registration_number ?? "",
    tax_identifier: details.tax_identifier ?? "",
    address: details.address ?? "",
    country: details.country ?? "",
    representative_name: details.representative_name ?? "",
    representative_capacity: details.representative_capacity ?? ""
  };
}

/* NULL RATHER THAN A 404 for somebody who has never filled this in, so a first
   visit is an empty form and not an error banner. Same arrangement as
   getPayoutMethod in lib/checkout.ts, and for the same reason: the absence of
   a block is a normal state that most accounts start in. */
export function getMyPartyDetails(token: string | null): Promise<PartyDetails | null> {
  return api<PartyDetails | null>("/profiles/me/party-details", { token });
}

/* Answers the block as stored, which is how the form learns the derived
   display_label without a second read. */
export function saveMyPartyDetails(
  token: string | null,
  body: PartyDetailsInput
): Promise<PartyDetails> {
  return api<PartyDetails>("/profiles/me/party-details", { method: "PUT", token, body });
}

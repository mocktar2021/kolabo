/* The content licence: what the brand may do with the creator's content, as
   the brand states it before a contract exists.

   Mirrors article 10 of the collaboration contract model
   (claude/kolabo-contrat-collaboration-modele-fr.md), which makes the Parties
   retain one of three options and leaves the rest of the clause to be filled
   in by them. The founder's decision is that the brand states the choice
   BEFORE the contract is created, that all three options are offered, and that
   Kolabo captures it. The platform records what the brand declares and checks
   none of it, exactly as a paper contract would, so nothing in this module or
   in the copy that reads from it may present a stated value as verified.

   THE FIELD NAMES ARE PINNED and shared with the backend and the web client.
   They are not renamed here for a nicer camelCase: a rename on one client is
   a field the other two silently stop reading, and the symptom is a contract
   printed without the clause rather than a failing build.

   WHY A MODULE AND NOT JUST A FORM, the same reason lib/partyDetails.ts
   gives: the first question decides which further questions are asked, and
   three things need that table at once.

     the render order on the brand's form;
     the completeness check that gates its submit button;
     the request body, which must carry the option's own fields and no others.

   A FOURTH READER, and on a phone the one that matters most: the sentence a
   creator reads before accepting. A creator prices option 2 differently from
   option 1, so the terms have to be on screen next to the button that accepts
   them. licenceSentences() builds that sentence from the same table, so an
   option whose fields change cannot go on describing itself the old way.

   `t` IS AN ARGUMENT, not an import, exactly as lib/errorMessages.ts takes
   one. It keeps this module free of imports, so the sentence a creator will
   actually read can be asserted in a unit test without booting i18next. On a
   client with no UI tests that is the only place the wording is checked at
   all. */

/* Written as the strings the contract uses, not as names. The contract says
   "Option retenue : [ 1 / 2 / 3 ]" and the backend stores that character, so
   a client that invented "redistribution" as a friendlier value would be
   storing something the document cannot print. */
export type LicenceOption = "1" | "2" | "3";

/* The order the three are offered in, which is the contract's own order:
   narrowest grant first, outright assignment last. It is an order and nothing
   more. Per the founder all three are offered equally, and the copy in
   lib/licenceStrings.ts is what carries that weight. */
export const LICENCE_OPTIONS: LicenceOption[] = ["1", "2", "3"];

export type LicenceField =
  | "licence_duration"
  | "licence_territories"
  | "licence_media"
  | "licence_consideration";

/* The shape as it travels on a campaign or an order. Every field is optional
   and nullable because all five are, for two separate reasons that happen to
   agree: option 1 asks for none of the four, and a row written before this
   feature existed carries none of the five. A screen reading an older row
   must render "not stated" rather than crash, which is why nothing here is
   required. */
export type LicenceTerms = {
  licence_option?: string | null;
  licence_duration?: string | null;
  licence_territories?: string | null;
  licence_media?: string | null;
  licence_consideration?: string | null;
};

/* Per option: the fields the contract asks for, in the order they are drawn.

   Option 1 asks for nothing further. The creator publishes on their own
   accounts and the brand has no redistribution right at all, so there is no
   duration to state and no territory to name.

   Option 2 is the clause with three blanks in it: a duration, the
   territories, and the media. All three are required, because the sentence
   the creator reads is what they price against and a licence of unstated
   length is not a licence anybody can put a number on.

   Option 3 names a duration and the territories. Its consideration is
   genuinely optional: the contract says a separate consideration MAY be
   agreed, so an empty one means none was, not that something is missing. */
export const FIELDS: Record<LicenceOption, LicenceField[]> = {
  "1": [],
  "2": ["licence_duration", "licence_territories", "licence_media"],
  "3": ["licence_duration", "licence_territories", "licence_consideration"],
};

/* The exceptions. Everything in FIELDS is required unless it is listed here. */
export const OPTIONAL: Record<LicenceOption, LicenceField[]> = {
  "1": [],
  "2": [],
  "3": ["licence_consideration"],
};

export function isOptional(option: LicenceOption, field: LicenceField): boolean {
  return OPTIONAL[option].includes(field);
}

/* Whether the brand is claiming anything beyond the creator's own accounts.
   Both of the surfaces that read it use it for the same thing: deciding
   whether the pricing warning is worth a line of screen. Under option 1 there
   is nothing extra to price and the warning would be noise. */
export function redistributes(option: LicenceOption | null): boolean {
  return option === "2" || option === "3";
}

/* The form's state: every field, always, whichever option is selected.

   Deliberately not narrowed to the selected option, the same call
   lib/partyDetails.ts makes. A brand that fills in a duration and a list of
   territories under option 2, taps option 3 to read what it asks, and taps
   back should find its typing where it left it. toPayload() is what keeps the
   values an option does not ask for out of the request. */
export type LicenceValues = Record<LicenceField, string>;

export const EMPTY_VALUES: LicenceValues = {
  licence_duration: "",
  licence_territories: "",
  licence_media: "",
  licence_consideration: "",
};

/* The stated option, or null when nothing usable is stated.

   AN UNRECOGNISED VALUE DEGRADES TO null rather than being passed through.
   The three options are the only ones article 10 offers, so a fourth value
   is a row this client cannot describe, and the honest answer on screen is
   the same one it gives an empty field: the brand has not stated terms this
   app can read. Guessing which option a stranger meant would put a sentence
   about paid advertising in front of a creator on no evidence. */
export function optionOf(terms: LicenceTerms | null | undefined): LicenceOption | null {
  const raw = terms?.licence_option;
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return (LICENCE_OPTIONS as string[]).includes(trimmed) ? (trimmed as LicenceOption) : null;
}

/* A payload into form state. Null and absent both become "", because a
   controlled TextInput cannot hold null and an uncontrolled one loses what is
   typed into it on the next render. */
export function valuesFrom(terms: LicenceTerms | null | undefined): LicenceValues {
  if (!terms) return { ...EMPTY_VALUES };
  const out = { ...EMPTY_VALUES };
  for (const field of Object.keys(EMPTY_VALUES) as LicenceField[]) {
    out[field] = terms[field] ?? "";
  }
  return out;
}

/* What is still blank, in render order, so the form can both withhold its
   submit button and point at the right field. Whitespace is not an answer: a
   duration of three spaces would print as a blank in the middle of article 10
   and read as filled in. */
export function missingFields(option: LicenceOption, values: LicenceValues): LicenceField[] {
  return FIELDS[option].filter((field) => !isOptional(option, field) && values[field].trim() === "");
}

export function isComplete(option: LicenceOption, values: LicenceValues): boolean {
  return missingFields(option, values).length === 0;
}

/* The body, and the only thing that builds one.

   EVERY ONE OF THE FOUR FIELDS TRAVELS ON EVERY REQUEST, carrying null when
   the selected option does not ask for it. That is the one place this differs
   from lib/partyDetails.toPayload, which omits a field its type does not ask
   for, and the difference is deliberate. A party block is replaced whole by a
   PUT. These five columns hang off a campaign that is also edited in pieces,
   so an omitted field is a field left at whatever it was: a brand that
   narrowed its claim from option 2 to option 1 would keep a stale twelve
   months and a stale territory list, and those would print on the contract
   underneath a sentence saying it has no redistribution right. Sending null
   says what was meant.

   Empty becomes null rather than "", so a cleared field is cleared rather
   than stored as a blank string that then prints as a blank line. */
export function toPayload(option: LicenceOption, values: LicenceValues): Record<string, string | null> {
  const asked = FIELDS[option];
  const body: Record<string, string | null> = { licence_option: option };
  for (const field of Object.keys(EMPTY_VALUES) as LicenceField[]) {
    const value = asked.includes(field) ? values[field].trim() : "";
    body[field] = value === "" ? null : value;
  }
  return body;
}

/* The brand's form state before anything is chosen.

   "" IS A REAL STATE AND NOT A DEFAULT OPTION. Nothing is pre-selected, and
   that is the choice this module makes on purpose. Pre-selecting option 2
   would claim a paid-advertising licence from a brand that never read the
   question. Pre-selecting option 1 would be safe for the creator but would
   still answer article 10 on the brand's behalf, and the clause is the one
   the contract hands to the Parties rather than to the platform. So the form
   asks, and will not submit until it has an answer. */
export type LicenceDraft = { option: LicenceOption | ""; values: LicenceValues };

export const EMPTY_DRAFT: LicenceDraft = { option: "", values: { ...EMPTY_VALUES } };

export function draftIsComplete(draft: LicenceDraft): boolean {
  if (draft.option === "") return false;
  return isComplete(draft.option, draft.values);
}

/* The draft as request fields, or null while no option has been chosen. A
   caller that gets null has nothing to send and nothing to merge: the body it
   is building should carry none of the five keys rather than five nulls,
   because five nulls is a brand stating that it claims nothing, which is
   option 1, which is not what an unanswered form means. */
export function draftPayload(draft: LicenceDraft): Record<string, string | null> | null {
  if (draft.option === "") return null;
  return toPayload(draft.option, draft.values);
}

/* i18next's t, narrowed to what this file needs. Taken as an argument rather
   than imported, so this module keeps its no-imports property. */
export type Translate = (key: string, opts?: Record<string, unknown>) => string;

/* One key per field, written out rather than built by stripping the
   `licence_` prefix off the field name. A key assembled from a value is a key
   no search finds: somebody renaming a line of copy should be able to grep
   licence.f_territories and land here. */
const FIELD_KEY: Record<LicenceField, string> = {
  licence_duration: "licence.f_duration",
  licence_territories: "licence.f_territories",
  licence_media: "licence.f_media",
  licence_consideration: "licence.f_consideration",
};

/* What a creator reads before accepting, in plain language, as one or more
   finished sentences.

   THE HAPPY PATH IS ONE SENTENCE and it names the stated values inside it,
   because that is how the fact reads out loud: this brand may run your video
   as a paid advert for twelve months in Benin and Togo. A labelled table of
   four rows says the same thing while letting the reader skip it, and the
   whole point is that this one is not skippable.

   THE STATED VALUES ARE NEVER TRANSLATED AND NEVER REWORDED. They are free
   text written by the brand and printed verbatim into the contract, so they
   are interpolated exactly as they arrived, in whatever language they were
   written. i18n.ts sets escapeValue false, so a French duration with an
   apostrophe in it survives the trip.

   WHEN A REQUIRED VALUE IS MISSING the sentence degrades instead of being
   assembled around a hole. Interpolating an empty duration would produce "for
   , in Benin", which reads like a bug and tells the creator nothing; worse,
   an invented filler would read as a term somebody agreed. So the headline
   drops to the part that is still true, whatever was stated is listed
   underneath, and a closing line says outright that something is missing and
   to ask for it before accepting. The backend requires those fields, so this
   branch should be unreachable; it exists because the cost of being wrong
   about that is a creator accepting terms nobody wrote down.

   RETURNS AN EMPTY LIST when no option is stated. The caller decides what to
   say about that, because "the brand has not said" is a different piece of
   news from any of the three options and belongs in its own sentence. */
export function licenceSentences(terms: LicenceTerms | null | undefined, t: Translate): string[] {
  const option = optionOf(terms);
  if (!option) return [];

  const values = valuesFrom(terms);

  /* Option 1 has no blanks to fill, so it is one sentence and always the same
      one. It still has to be SAID: a creator who reads nothing about the
      licence cannot tell "no redistribution right" from "nobody mentioned
      it", and those two end in different places. */
  if (option === "1") return [t("licence.o1")];

  const complete = isComplete(option, values);
  const out: string[] = [];

  if (option === "2") {
    out.push(
      complete
        ? t("licence.o2_full", {
            duration: values.licence_duration.trim(),
            territories: values.licence_territories.trim(),
            media: values.licence_media.trim(),
          })
        : t("licence.o2_head")
    );
  } else {
    out.push(
      complete
        ? t("licence.o3_full", {
            duration: values.licence_duration.trim(),
            territories: values.licence_territories.trim(),
          })
        : t("licence.o3_head")
    );
    /* The consideration gets its own line whether or not the rest is
       complete, and never joins the headline. It is optional, so folding it
       into the sentence would need a second template for the case where none
       was agreed, and a sum of money is the line a creator rereads anyway. */
    const extra = values.licence_consideration.trim();
    if (extra) out.push(t(FIELD_KEY.licence_consideration, { value: extra }));
  }

  if (!complete) {
    for (const field of FIELDS[option]) {
      if (isOptional(option, field)) continue;
      const value = values[field].trim();
      if (value) out.push(t(FIELD_KEY[field], { value }));
    }
    out.push(t("licence.incomplete"));
  }

  return out;
}

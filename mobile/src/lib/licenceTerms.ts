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

   AND SO IS THE NESTING. The five names live inside ONE `licence_terms`
   object, on the way in and on the way out, because that is what the API
   takes and serves: campaigns/schemas.py declares LicenceTermsIn as a nested
   object on CampaignCreate, CampaignPatch, OrderIn and CartItemIn, hands it
   back as one dict on CampaignOut, ProposalOut and ContractDetailOut, and
   stores it as a single JSON column. campaigns/editing.py then compares what
   a PATCH sends against what that column holds, whole, to decide whether this
   locked term changed: one comparison rather than five. This module wrote and
   read the five keys FLAT at the top level of the carrier, which the real API
   would have refused on the brand's form and read as undefined on every
   creator-facing screen, so a licence that was stated printed as "not stated".

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

/* The block as it ARRIVES. Every field is optional and nullable because all
   five are, for two separate reasons that happen to agree: option 1 asks for
   none of the four, and a row written before this feature existed carries
   none of the five. A screen reading an older row must render "not stated"
   rather than crash, which is why nothing here is required. */
export type StoredLicenceBlock = {
  licence_option?: string | null;
  licence_duration?: string | null;
  licence_territories?: string | null;
  licence_media?: string | null;
  licence_consideration?: string | null;
};

/* ANYTHING THAT CARRIES ONE: a campaign, an open brief, the campaign nested on
   an invitation, a proposal, a contract.

   ONE OPTIONAL NESTED KEY AND NOT FIVE FLAT ONES, which is the shape of the
   API. It is intersected onto Campaign (lib/campaignTypes), OpenBrief
   (lib/boardTypes) and Proposal rather than spelled out again on each, so the
   pinned name is declared exactly once in this client.

   Optional because a payload from a backend that is not sending the key yet
   has to compile and has to render honestly, and nullable because the column
   really is null on every row written before the capture existed.

   NO INDEX SIGNATURE HERE, deliberately, where the web client's LicenceCarrier
   needs one. That type is structural and accepts payloads whose own types
   never name the key, so without a catch-all it is a WEAK TYPE and TypeScript
   refuses every one of them (TS2559). Here the carriers INTERSECT this type,
   so they declare the key and the weak-type check is satisfied. Adding a
   catch-all would hand Campaign and OpenBrief an index signature as well, and
   `campaign.titel` would quietly become `unknown` instead of an error. */
export type LicenceTerms = { licence_terms?: StoredLicenceBlock | null };

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
   values an option does not ask for out of the request.

   FLAT HERE AND NESTED ON THE WIRE, on purpose: this is what four TextInputs
   are bound to, and a nested draft would make every onChangeText reach through
   a key that means nothing to a form. toPayload is the one place the two
   shapes meet. */
export type LicenceValues = Record<LicenceField, string>;

export const EMPTY_VALUES: LicenceValues = {
  licence_duration: "",
  licence_territories: "",
  licence_media: "",
  licence_consideration: "",
};

/* The stated option, or null when nothing usable is stated.

   READ OFF `terms.licence_terms` AND NEVER OFF THE CARRIER'S OWN KEYS. The
   block is nested on every payload that carries it; reading the carrier
   directly is what this module used to do, and against the real API it
   answered null for every licence ever stated.

   AN UNRECOGNISED VALUE DEGRADES TO null rather than being passed through.
   The three options are the only ones article 10 offers, so a fourth value
   is a row this client cannot describe, and the honest answer on screen is
   the same one it gives an empty field: the brand has not stated terms this
   app can read. Guessing which option a stranger meant would put a sentence
   about paid advertising in front of a creator on no evidence. */
export function optionOf(terms: LicenceTerms | null | undefined): LicenceOption | null {
  const raw = terms?.licence_terms?.licence_option;
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return (LICENCE_OPTIONS as string[]).includes(trimmed) ? (trimmed as LicenceOption) : null;
}

/* A payload into form state. Null and absent both become "", because a
   controlled TextInput cannot hold null and an uncontrolled one loses what is
   typed into it on the next render. Reads the nested block, like optionOf: a
   carrier with no block is every field empty. */
export function valuesFrom(terms: LicenceTerms | null | undefined): LicenceValues {
  const block = terms?.licence_terms;
  if (!block) return { ...EMPTY_VALUES };
  const out = { ...EMPTY_VALUES };
  for (const field of Object.keys(EMPTY_VALUES) as LicenceField[]) {
    out[field] = block[field] ?? "";
  }
  return out;
}

/* WHICH OF TWO CARRIERS A SCREEN SHOULD READ THE LICENCE FROM: the offer's
   block when it states one, the brief's otherwise.

   THIS IS THE BACKEND'S PRECEDENCE AND NOT A PREFERENCE. A brief's licence is
   written on the campaign, beside the budget and the deliverables. A DIRECT
   ORDER'S is written on the brand's own proposal row, because there the
   proposal IS the offer (campaigns.service._place_order writes version 1
   authored by the business) and the campaign behind it is a wrapper nobody
   reads terms from. So a row that states one wins, and a brief's proposals
   state nothing. contracts.service._licence_snapshot resolves it in exactly
   that order when the contract is written, which means a client resolving it
   any other way would show a creator one licence and then have a different one
   signed into the contract they accepted.

   The ARGUMENT ORDER is the precedence, so a call site reads as the rule. Both
   sides are optional because both legitimately go missing: a brief carries no
   proposal until somebody prices it, and an older payload carries no block.

   THE TEST IS "STATES AN OPTION" AND NOT "STATES ONE THIS BUILD KNOWS", which
   is the difference between degrading and lying. The backend asks only whether
   the row HAS a block (`proposal.licence_terms or campaign.licence_terms`) and
   validated_block never stores one without an option in it, so on real data
   the two rules agree. If an option this client has never heard of ever does
   arrive on an order, optionOf is right to answer null and the notice is right
   to say the terms cannot be read here, but falling back to the BRIEF at that
   point would print one party's clause in place of another's. Showing less
   beats showing somebody else's licence. It is also exactly what web's
   licenceRowFor does, via statedLicence, so the two clients cannot disagree
   about which row a screen is reading. */
function statesAnOption(terms: LicenceTerms): boolean {
  const raw = terms.licence_terms?.licence_option;
  return typeof raw === "string" && raw.trim() !== "";
}

export function licenceTermsFor(
  offer: LicenceTerms | null | undefined,
  brief: LicenceTerms | null | undefined
): LicenceTerms | null {
  if (offer && statesAnOption(offer)) return offer;
  return brief ?? null;
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

/* The block as it is SENT: all five keys, the option narrowed to the three the
   document prints. */
export type LicenceTermsBlock = {
  licence_option: LicenceOption;
  licence_duration: string | null;
  licence_territories: string | null;
  licence_media: string | null;
  licence_consideration: string | null;
};

/* And the block under the one key every request carries it on. A type of its
   own rather than an inline object, because this is the thing callers spread
   into a body: `{ ...draftPayload(draft) }` has to produce `licence_terms`,
   and naming the wrapper is what makes a caller that spreads the BLOCK instead
   fail to compile rather than post five keys the API ignores. */
export type LicenceTermsBody = { licence_terms: LicenceTermsBlock };

/* One stated value, or null when this option does not ask for it or the brand
   left it blank. Empty becomes null rather than "", so a cleared field is
   cleared rather than stored as a blank string that then prints as a blank
   line in the middle of the clause. */
function statedValue(
  option: LicenceOption,
  values: LicenceValues,
  field: LicenceField
): string | null {
  if (!FIELDS[option].includes(field)) return null;
  const value = values[field].trim();
  return value === "" ? null : value;
}

/* The body, and the only thing that builds one.

   ONE NESTED `licence_terms` KEY, because that is what the API takes on a
   brief (CampaignCreate), on a correction to one (CampaignPatch), on a direct
   order (OrderIn) and on every line of a basket (CartItemIn). See the note at
   the top of this file for why the backend wants it whole.

   EVERY ONE OF THE FOUR FIELDS TRAVELS INSIDE IT ON EVERY REQUEST, carrying
   null when the selected option does not ask for it. That is the one place
   this differs from lib/partyDetails.toPayload, which omits a field its type
   does not ask for, and the difference is deliberate. A party block is
   replaced whole by a PUT. This block hangs off a campaign that is also edited
   in pieces, so an omitted field is a field left at whatever it was: a brand
   that narrowed its claim from option 2 to option 1 would keep a stale twelve
   months and a stale territory list, and those would print on the contract
   underneath a sentence saying it has no redistribution right. Sending null
   says what was meant. */
export function toPayload(option: LicenceOption, values: LicenceValues): LicenceTermsBody {
  return {
    licence_terms: {
      licence_option: option,
      licence_duration: statedValue(option, values, "licence_duration"),
      licence_territories: statedValue(option, values, "licence_territories"),
      licence_media: statedValue(option, values, "licence_media"),
      licence_consideration: statedValue(option, values, "licence_consideration"),
    },
  };
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

/* The draft as a request body, or null while no option has been chosen. A
   caller that gets null has nothing to send and nothing to merge: the body it
   is building should carry no `licence_terms` key at all rather than a block
   of five nulls, because five nulls is a brand stating that it claims nothing,
   which is option 1, which is not what an unanswered form means. */
export function draftPayload(draft: LicenceDraft): LicenceTermsBody | null {
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

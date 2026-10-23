/* THE CONTENT LICENCE: which of the three options the brand states, and what
   each option asks it to spell out.

   WHY THIS EXISTS AT ALL. Article 10 of the collaboration contract approved by
   the founder's counsel offers three options for how the brand may use what
   the creator makes, and leaves "Option retenue : [ 1 / 2 / 3 ]" to be filled
   in per contract. Nobody was filling it in, because nothing ever asked. The
   founder settled it: the brand states the option BEFORE the contract exists,
   all three are offered, and Kolabo captures what was said.

   WHY BEFORE AND NOT AT SIGNATURE, which is the whole point of the feature. A
   creator prices option 2 differently from option 1: one is a post on their own
   account, the other is a paid advertisement the brand may run for a year.
   Asking at signature would mean the creator priced one job and signed another,
   and the only honest answer at that point is to reopen the negotiation. So the
   licence is part of the terms a creator reads before accepting, in the same
   breath as the rate and the timeline.

   A FEATURE-SCOPED lib file, for the reason lib/checkout.ts and lib/cart.tsx
   give for being ones: the field map below is read by one brand-facing form and
   one read-only panel, and lib/types.ts is already 35 KB of shared API shapes.

   THE BLOCK TRAVELS NESTED, UNDER ONE `licence_terms` KEY, IN BOTH DIRECTIONS.
   That is the backend's shape and it is not negotiable from here:
   campaigns/schemas.py declares LicenceTermsIn as a nested object on
   CampaignCreate, CampaignPatch, OrderIn and CartItemIn, serves it back as one
   dict on CampaignOut, ProposalOut and ContractDetailOut, and stores it as a
   single JSON column. campaigns/editing.py then compares what a PATCH sends
   against what that column holds to decide whether this locked term changed,
   which is ONE comparison against one value; five flat keys would make it five
   against five, and would put the brand's licence in a different shape on the
   way in from the one it has everywhere else. This client sent and read the
   five keys flat, which the real API would have refused on every form and read
   as undefined on every creator-facing screen.

   THE SHAPES STAY HERE AND NOT IN types.ts, DELIBERATELY, and nesting makes
   that cheaper rather than dearer. The block rides on a campaign, on an open
   brief, on the campaign nested on an invitation, on a proposal and on a
   contract, which is five types in that file. LicenceCarrier below is a
   STRUCTURAL type naming the one key they all carry, so any of those payloads
   is accepted without that file naming the block at all, and a build whose API
   has not started sending it yet still compiles and still renders honestly. The
   same arrangement CartCheckoutOrder has for the same reason. Folding the key
   into Campaign later costs one edit and changes nothing here.

   EVERY VALUE BELOW IS FREE TEXT STATED BY THE PARTIES AND PRINTED VERBATIM.
   There is no droplist of durations and no droplist of territories, and adding
   one would be Kolabo writing a contract clause on a brand's behalf: "6 mois"
   and "jusqu'au retrait de la campagne" are both real answers, and so is "Benin
   et Togo" alongside "monde entier". Nothing here translates a stated value
   either, in either direction. What the brand wrote is what the contract says,
   in the language it was written in. */

/* The option, as the contract itself numbers them. A string and not a number
   because that is what article 10 prints, because the pinned API contract says
   so, and because "1" never arrives as a falsy 0 from a form control. */
export type LicenceOption = "1" | "2" | "3";

/* In the order article 10 lists them, which is also least to most: the creator
   keeps everything, the brand may run it, the rights move. THE ORDER IS NOT A
   RECOMMENDATION and the form must not mark one as the usual choice, but unlike
   the three forms of party in lib/party.ts these three are NOT equal and must
   not be presented as though they were. They are three different deals at three
   different prices, and a brand that picks the cheapest one by accident has
   bought a post it may not advertise with. */
export const LICENCE_OPTIONS: readonly LicenceOption[] = ["1", "2", "3"];

/* The four fields that spell an option out. Named as the API names them, so
   nothing has to translate between a form key and a request key, and so a
   rename shows up as a compile error rather than as a field the server quietly
   never reads. */
export type LicenceField =
  | "licence_duration"
  | "licence_territories"
  | "licence_media"
  | "licence_consideration";

export type LicenceFieldSpec = {
  name: LicenceField;
  /* The i18n key under licence.*, spelled out rather than built from the field
     name. Same reasoning as PartyFieldSpec.labelKey in lib/party.ts: a key
     derived from `name` would have needed a lookup table beside it to say the
     same thing, and the table would then be the real list. */
  labelKey: string;
  /* The line under the field, present on all four because all four are a blank
     box asking for a contract clause: "territoires" means nothing until
     somebody has seen that "monde entier" is an answer. */
  hintKey: string;
  required: boolean;
};

const DURATION: LicenceFieldSpec = {
  name: "licence_duration",
  labelKey: "duration",
  hintKey: "durationHint",
  required: true
};

const TERRITORIES: LicenceFieldSpec = {
  name: "licence_territories",
  labelKey: "territories",
  hintKey: "territoriesHint",
  required: true
};

const MEDIA: LicenceFieldSpec = {
  name: "licence_media",
  labelKey: "media",
  hintKey: "mediaHint",
  required: true
};

/* THE ONLY OPTIONAL FIELD IN THE FILE, and it is optional because article 10
   says a separate consideration PEUT be agreed rather than must. An assignment
   of rights settled inside the agreed price is a real bargain, and a required
   box here would make brands invent a number to get past it. */
const CONSIDERATION: LicenceFieldSpec = {
  name: "licence_consideration",
  labelKey: "consideration",
  hintKey: "considerationHint",
  required: false
};

/* Option 1 asks for nothing further, and that is the whole clause rather than a
   thinner version of the other two: the creator posts on their own accounts and
   the brand may share the original. There is no period to state because nothing
   is being licensed, and no territory because nothing is being run anywhere. A
   form that asked for either would be asking about rights that were not
   granted. An empty array rather than an absent key, so every reader can
   iterate without first asking whether there is anything to iterate. */
const NOTHING_FURTHER: readonly LicenceFieldSpec[] = [];

/* Option 2, the one the annex to the model contract calls the most frequent
   case in practice, because a brand that pays for content usually wants to
   advertise with it. Three required fields, and all three are required by the
   clause itself: it licenses reproduction for a stated period, on stated
   territories and on stated media, so a blank in any of the three leaves a
   licence with no limit written into it. */
const REDISTRIBUTION: readonly LicenceFieldSpec[] = [DURATION, TERRITORIES, MEDIA];

/* Option 3, an assignment of the economic rights. Period and territories are
   required for the same reason they are under option 2; there is no media field
   because the clause does not limit by support, which is precisely what makes
   it the broader bargain. */
const ASSIGNMENT: readonly LicenceFieldSpec[] = [DURATION, TERRITORIES, CONSIDERATION];

/* WHICH FIELDS BELONG TO WHICH OPTION, read by the three places that would
   otherwise each hold their own opinion: the brand's form renders this,
   licenceBody below sends exactly the keys it names, and the read-only panel
   iterates it to decide which rows a stated licence has. A field added to an
   option therefore appears on the form, in the request and on every screen that
   prints it in one edit. */
export const LICENCE_FIELDS: Record<LicenceOption, readonly LicenceFieldSpec[]> = {
  "1": NOTHING_FURTHER,
  "2": REDISTRIBUTION,
  "3": ASSIGNMENT
};

/* All four, in article 10's own order, for the one case where the option is not
   one this build knows about. See statedLicence below: a licence stated as
   something other than 1, 2 or 3 still has its stated values printed, because
   the brand wrote them and the creator has to be able to read them. */
export const ALL_LICENCE_FIELDS: readonly LicenceFieldSpec[] = [
  DURATION,
  TERRITORIES,
  MEDIA,
  CONSIDERATION
];

/* The brand's form state.

   NULL MEANS UNANSWERED and the further fields stay hidden until it is not,
   which is the pattern pages/PartyDetails.tsx established and the reason there
   is no default option: a default would both show the wrong fields and nominate
   a normal case, and here nominating a normal case would be nominating a price.

   `values` is flat and keyed by request field name, and is deliberately NOT
   cleared when the option changes. Period and territories belong to options 2
   and 3 alike, and retyping a territory list because somebody moved from a
   licence to an assignment is how a form gets abandoned halfway. licenceBody
   below is what makes sure the fields of the option NOT chosen never travel.

   FLAT HERE AND NESTED ON THE WIRE, on purpose. This is form state read by one
   radio group and at most three text boxes, and a nested draft would make every
   onChange in components/LicenceFields.tsx reach through a key that means
   nothing to a form. licenceBody is the one place the two shapes meet. */
export type LicenceDraft = {
  option: LicenceOption | null;
  values: Record<string, string>;
};

/* A module constant rather than a fresh object, so a reset to it twice does not
   retrigger anything that depends on the reference. Same arrangement as
   EMPTY_TARGETING in components/TargetingFields.tsx. */
export const EMPTY_LICENCE: LicenceDraft = { option: null, values: {} };

/* Whether the chosen option has everything article 10 needs spelled out.

   Mirrors what the server checks rather than replacing it: an incomplete
   statement is refused with licence_terms_invalid, and lib/errorMessages.ts has
   that sentence in both languages. What this buys is a disabled button and a
   line saying what is missing, instead of a refusal arriving after the brand
   has written a brief. */
export function licenceIsComplete(draft: LicenceDraft): boolean {
  if (draft.option === null) return false;
  return LICENCE_FIELDS[draft.option].every(
    (field) => !field.required || (draft.values[field.name] ?? "").trim() !== ""
  );
}

/* The five fields exactly as they travel inside the block, in and out. The
   pinned contract for this feature, shared with the backend and the mobile app,
   and nothing may rename a key here on its own. */
export type LicenceTermsBlock = {
  licence_option: LicenceOption;
  licence_duration: string | null;
  licence_territories: string | null;
  licence_media: string | null;
  licence_consideration: string | null;
};

/* And the block under the one key every request carries it on. A type of its
   own rather than an inline object, because this is the thing callers spread
   into a body: `{ ...licenceBody(draft) }` has to produce `licence_terms`, and
   naming the wrapper is what makes a caller that spreads the BLOCK instead fail
   to compile rather than post five keys the API ignores. */
export type LicenceTermsBody = { licence_terms: LicenceTermsBlock };

/* The request body for the chosen option, and only for the chosen option.

   ONE NESTED KEY, because that is what the API takes on a brief
   (CampaignCreate), on a correction to one (CampaignPatch), on a direct order
   (OrderIn) and on every line of a basket (CartItemIn). See the note at the top
   of this file: campaigns/editing.py compares the block it is sent against the
   column whole, so the shape is a decision rather than a style.

   ALL FIVE KEYS ARE ALWAYS PRESENT INSIDE IT AND THE UNUSED ONES ARE EXPLICIT
   NULLS, which is the opposite of what partyBody in lib/party.ts does, and the
   difference is deliberate. A party block is read whole and printed as a
   paragraph, so a key carrying an empty string becomes a blank line under a
   heading nobody filled in. These five are one clause with a fixed shape: the
   contract always prints an option, and "no media limit was stated" is a FACT
   about the licence rather than a field somebody forgot. A null says it; an
   absent key leaves a campaign that is edited in pieces holding whatever that
   field was before, which would then print on the contract under a sentence
   saying the brand has no such right.

   A value belonging to another option is not sent as an empty string, it is
   sent as null: a media limit typed before the brand moved to option 3 must not
   travel with an assignment that does not limit by support.

   Null rather than a draft for an unanswered option, so a caller cannot
   accidentally post a licence with no option on it. licenceIsComplete is what
   every caller gates on first. */
export function licenceBody(draft: LicenceDraft): LicenceTermsBody | null {
  if (draft.option === null) return null;
  const block: LicenceTermsBlock = {
    licence_option: draft.option,
    licence_duration: null,
    licence_territories: null,
    licence_media: null,
    licence_consideration: null
  };
  for (const field of LICENCE_FIELDS[draft.option]) {
    const value = (draft.values[field.name] ?? "").trim();
    if (value) block[field.name] = value;
  }
  return { licence_terms: block };
}

/* A stored block as it arrives, which is the same five names with none of them
   guaranteed. Every field is optional AND nullable for two separate reasons
   that happen to agree: option 1 states none of the four, and a row written
   before this feature existed carries none of the five. */
export type StoredLicenceBlock = {
  licence_option?: string | null;
  licence_duration?: string | null;
  licence_territories?: string | null;
  licence_media?: string | null;
  licence_consideration?: string | null;
};

/* Anything that may carry a stated licence: a campaign, an open brief, the
   campaign nested on an invitation, a proposal, a contract.

   ONE OPTIONAL NESTED KEY, AND THAT IS THE POINT OF THE TYPE. It lets a screen
   hand over whatever payload it already holds without lib/types.ts naming the
   block on five separate types, and it means a backend that is not sending it
   yet produces a panel that says so rather than a compile error or a crash. An
   absent key, a null key and a block with no option in it are the same thing to
   every reader below, which is also what they are to somebody reading the
   screen.

   THE INDEX SIGNATURE IS LOAD-BEARING AND IS NOT A SHRUG. Without it this is
   what TypeScript calls a WEAK TYPE, every property optional, and it refuses an
   argument that has no property in common with it: `statedLicence(campaign)`
   fails with TS2559 on exactly the builds this type exists to support, which
   are the ones whose Campaign does not declare a licence field yet. That is the
   weak-type check doing its job on most types and defeating this one, because
   here "this payload does not name the key" is the normal state rather than a
   mistaken argument. The index signature says out loud what the callers are:
   whole API payloads that carry a great deal besides a licence. Nesting made
   this MORE necessary, not less: there is now one key to have in common instead
   of five.

   It costs nothing in safety where it matters. `licence_terms` is DECLARED, so
   it keeps its own type and a misspelling in this file reads as `unknown` and
   fails to compile at stated() rather than silently returning null. */
export type LicenceCarrier = {
  licence_terms?: StoredLicenceBlock | null;
  [key: string]: unknown;
};

/* A licence as a screen prints it.

   `option` IS THE RAW VALUE AND `known` IS THE NARROWED ONE, and keeping them
   apart is what lets an option this build has never heard of degrade to less
   information rather than to a wrong explanation. Same defence as an
   unrecognised party_type in components/ContractParties.tsx and an unrecognised
   social account status in lib/types.ts: on a screen where somebody is about to
   agree to something, printing nothing is bad and printing a confident wrong
   sentence is worse. */
export type StatedLicence = {
  option: string;
  known: LicenceOption | null;
  values: Record<LicenceField, string | null>;
};

function knownOption(option: string): LicenceOption | null {
  return LICENCE_OPTIONS.find((candidate) => candidate === option) ?? null;
}

/* Trimmed, and empty becomes null.

   The server trims a stated value rather than collapsing it, exactly as it does
   a party's address, because this text is printed as written and its line
   breaks are the brand's. This only has to decide whether there is anything
   there at all: a value of spaces is not a territory.

   TYPED NARROWLY ON PURPOSE, which is what keeps the index signature above
   honest: a field name misspelled in statedLicence resolves through the index
   signature to `unknown`, and `unknown` does not fit here. */
function stated(raw: string | null | undefined): string | null {
  if (typeof raw !== "string") return null;
  const value = raw.trim();
  return value === "" ? null : value;
}

/* What the row says about the licence, or null when it says nothing.

   READ OFF `row.licence_terms` AND NEVER OFF THE ROW'S OWN KEYS. The API puts
   the block under that one key on every payload that carries it; reading the
   row directly is what this client used to do, and against the real API it
   produced "not stated" on every screen for a licence that was stated.

   NULL MEANS NOTHING WAS STATED, which is a real and ordinary state rather than
   a fault: every campaign and every contract written before this feature
   existed is in it, and there is nothing to backfill from. The panel has its own
   sentence for it on each surface, because what to do about it differs: a
   creator reading a brief should ask the brand before accepting, while a
   contract already generated has article 10 of its own document to fall back
   on. Neither of those is an error banner. */
export function statedLicence(row: LicenceCarrier | null | undefined): StatedLicence | null {
  const block = row?.licence_terms;
  const option = stated(block?.licence_option);
  if (option === null) return null;
  return {
    option,
    known: knownOption(option),
    values: {
      licence_duration: stated(block?.licence_duration),
      licence_territories: stated(block?.licence_territories),
      licence_media: stated(block?.licence_media),
      licence_consideration: stated(block?.licence_consideration)
    }
  };
}

/* WHICH OF TWO ROWS A SCREEN SHOULD PRINT THE LICENCE FROM: the offer's block
   when it states one, the brief's otherwise.

   THIS IS THE BACKEND'S PRECEDENCE AND IT IS NOT A PREFERENCE. A brief's
   licence is written on the campaign, beside the budget and the deliverables,
   because that is where a brand states the rest of its terms. A DIRECT ORDER'S
   is written on the brand's own proposal row, because there the proposal IS the
   offer (campaigns.service._place_order writes version 1 authored by the
   business) and the campaign behind it is a wrapper nobody reads terms from. So
   a row that states one wins, and a brief's proposals state nothing.
   contracts.service._licence_snapshot resolves it in exactly that order at
   generation, which means a client that resolved it any other way would show a
   creator one licence and then write a different one into the contract they
   accepted.

   Kept here rather than in the two screens that need it, for the reason
   _licence_snapshot gives for being one function: this is the rule every future
   reader of these columns has to apply, and copies of it are chances to read a
   brief's licence onto an order that overrode it.

   The ARGUMENT ORDER is the precedence, so a call site reads as the rule. Both
   sides are optional because both legitimately go missing: a brief carries no
   proposal until somebody prices it, and a payload from an older backend
   carries no block at all. */
export function licenceRowFor(
  offer: LicenceCarrier | null | undefined,
  brief: LicenceCarrier | null | undefined
): LicenceCarrier | null {
  if (offer && statedLicence(offer) !== null) return offer;
  return brief ?? null;
}

/* Which rows to print for a stated licence: the chosen option's own fields, or
   all four when the option is one this build does not recognise. Kept here
   rather than in the panel so the panel has no opinion of its own about which
   field belongs to which option. */
export function licenceRows(licence: StatedLicence): readonly LicenceFieldSpec[] {
  return licence.known === null ? ALL_LICENCE_FIELDS : LICENCE_FIELDS[licence.known];
}

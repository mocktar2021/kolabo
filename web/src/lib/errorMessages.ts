/* What the API's refusals say, in French and in English.

   The backend answers a refusal with an English `detail` sentence and a stable
   `code` beside it (backend/app/core/errors.py). This file holds one sentence
   per code per language, and errorText() below picks the right one. Same
   arrangement as notificationBodies.ts, and for the same reason: no imports at
   all, so errorMessages.test.ts can read both maps and check them against the
   codes the backend actually emits without booting i18next.

   A CODE NAMES THE RULE, NOT THE SENTENCE. Rewording the English must never
   change the code, and two call sites enforcing the same rule share one even
   when their prose differs. That is what lets these sentences be rewritten in
   either language without touching Python.

   Codes are migrated one backend module at a time — 200-odd refusals do not
   move in one commit — so most of the API still answers with English prose and
   no code at all. errorText falls back to that prose, which is exactly what
   the app showed before any of this existed. Nothing gets worse on the way. */

/* The sentence shown when there is nothing else: a code we do not know, no
   code at all, and no English either (a network failure, a CORS refusal, a
   response that was not JSON). Also replaces the bare "Error" literal that
   pages used to fall back to, which was itself untranslated. */
export const GENERIC_KEY = "apiError.generic";

export const error_fr = {
  generic: "Une erreur est survenue. Réessayez dans un instant.",

  deliverable_attachments_max: "Vous pouvez joindre au maximum {{max}} fichiers.",
  deliverable_attachment_not_found: "Pièce jointe introuvable.",
  deliverable_attachment_not_yours: "Vous ne pouvez joindre que des fichiers que vous avez importés.",
  deliverable_contract_not_found: "Contrat introuvable.",
  deliverable_not_a_party: "Vous n'êtes pas partie à ce contrat.",
  deliverable_submit_creator_only: "Seul le créateur de ce contrat peut envoyer un livrable.",
  deliverable_contract_not_signed: "Un livrable ne peut être envoyé que sur un contrat entièrement signé.",
  deliverable_escrow_not_funded: "Aucun fonds n'est encore bloqué en séquestre sur ce contrat : il n'y a donc rien à livrer. Le livrable s'envoie une fois que la marque a payé.",
  deliverable_escrow_not_held: "Le séquestre n'est plus bloqué : aucun livrable ne peut être envoyé.",
  deliverable_submission_open_already: "Vous avez déjà envoyé un livrable sur ce contrat et la marque n'a pas encore répondu. Attendez sa réponse ou retirez d'abord votre envoi.",
  deliverable_note_too_long: "Une note fait au plus {{max}} caractères.",
  deliverable_submission_empty: "Un envoi doit contenir le lien de la publication, un fichier, ou les deux. Envoyez ce que la marque doit regarder.",
  deliverable_submission_not_found: "Envoi introuvable.",
  deliverable_review_business_only: "Seule l'entreprise de ce contrat peut valider un livrable.",
  deliverable_already_answered: "Cet envoi a déjà reçu une réponse.",
  deliverable_release_escrow_not_held: "Le séquestre n'est pas bloqué : il ne peut pas être libéré.",
  deliverable_changes_need_note: "Dites ce qui doit changer, pour que le créateur puisse corriger.",
  deliverable_withdraw_own_only: "Seul le créateur qui a envoyé ce livrable peut le retirer.",

  escrow_contract_not_found: "Contrat introuvable.",
  escrow_not_your_contract: "Ce contrat n'est pas le vôtre.",
  escrow_contract_not_signed: "Le contrat doit être entièrement signé avant d'être financé.",
  escrow_already_funded: "Ce contrat est déjà financé.",
  escrow_not_found: "Séquestre introuvable.",
  escrow_none_for_contract: "Aucun séquestre pour ce contrat.",
  escrow_not_a_party: "Vous n'êtes pas partie à ce séquestre.",
  escrow_not_held: "Le séquestre n'est pas bloqué.",
  escrow_release_business_only: "Seule l'entreprise peut confirmer la livraison.",

  dispute_not_found: "Litige introuvable.",
  dispute_closed: "Ce litige est clos.",
  dispute_already_open: "Ce séquestre a déjà un litige ouvert.",
  dispute_escrow_not_held: "Seul un séquestre bloqué peut faire l'objet d'un litige.",
  dispute_escrow_not_disputed: "Ce séquestre n'est pas en litige.",
  dispute_frozen_without_case: "Ce séquestre est gelé sans litige ouvert. Signalez-le avant de trancher.",
  dispute_withdraw_own_only: "Seule la partie qui a ouvert le litige peut le retirer.",
  /* {{reasons}} is a list of machine values the client sends back, not prose:
     translating them would produce a list no endpoint accepts. A client that
     hits this has a bug, not a language problem. */
  dispute_reason_unknown: "Le motif doit être l'un des suivants : {{reasons}}",
  dispute_statement_too_short: "Expliquez ce qui s'est passé en au moins {{min}} caractères.",
  dispute_statement_too_long: "Une déclaration fait au plus {{max}} caractères.",
  dispute_message_empty: "Un message ne peut pas être vide.",
  dispute_message_too_long: "Un message fait au plus {{max}} caractères.",
  dispute_evidence_max: "Vous pouvez joindre au maximum {{max}} images.",
  dispute_evidence_not_found: "Image introuvable.",
  dispute_evidence_not_yours: "Vous ne pouvez joindre que des images que vous avez importées.",
  dispute_amount_negative: "Aucun des deux montants ne peut être négatif.",
  /* Shown to an admin settling a split that does not add up. The arithmetic is
     the useful part, not the rule — hence five values rather than a sentence
     about conservation of money. */
  dispute_amounts_must_balance: "{{released}} libérés et {{refunded}} remboursés font {{total}}, mais le séquestre contient {{amount}} {{currency}}. L'argent ne doit être ni créé ni détruit.",

  /* The contact guard's refusal, and the only body whose values are words
     rather than numbers. {{what}} and {{surface}} are composed by
     contactDetails() below from the tokens the backend sends, because French
     does not build a list the way English does and a sentence assembled in
     Python could only ever be assembled in one language. */
  contact_details_found: "Ce {{surface}} semble contenir {{what}}. Kolabo garde la conversation, le contrat et l'argent au même endroit : un accord conclu ailleurs n'a ni contrat ni séquestre derrière lui, donc aucune des deux parties n'a de recours si ça tourne mal. Retirez-le et renvoyez votre {{surface}} — rien n'a été enregistré et rien n'a été modifié.",
  kind_email: "une adresse e-mail",
  kind_phone: "un numéro de téléphone",
  kind_handle: "un identifiant de messagerie",
  /* Grammatical gender is why these are nouns with their article attached and
     why the sentence above says "Ce {{surface}}" rather than agreeing with
     each one: "cette déclaration" would need the template to change with the
     value. Kept masculine and neutral instead — correct for "message" and
     "livrable", and readable for the others. */
  surface_message: "message",
  surface_statement: "texte",
  surface_proposal_note: "commentaire de proposition",
  /* The last separator in a list of two or three. Everything before it is a
     comma in both languages; only the final join differs. */
  list_and: "et"
};

export const error_en = {
  generic: "Something went wrong. Try again in a moment.",

  deliverable_attachments_max: "At most {{max}} files can be attached.",
  deliverable_attachment_not_found: "Attachment not found.",
  deliverable_attachment_not_yours: "You can only attach files you uploaded.",
  deliverable_contract_not_found: "Contract not found.",
  deliverable_not_a_party: "You are not a party to this contract.",
  deliverable_submit_creator_only: "Only the creator on this contract can submit work.",
  deliverable_contract_not_signed: "Work can only be submitted on a fully signed contract.",
  deliverable_escrow_not_funded: "This contract has no money in escrow yet, so there is nothing to deliver against. Work is submitted once the brand has funded it.",
  deliverable_escrow_not_held: "This escrow is no longer held, so work cannot be submitted against it.",
  deliverable_submission_open_already: "You have already submitted work on this contract and the brand has not answered yet. Wait for their review, or withdraw the submission first.",
  deliverable_note_too_long: "A note is at most {{max}} characters.",
  deliverable_submission_empty: "A submission needs the link to the published post, a file, or both. Send what the brand is meant to look at.",
  deliverable_submission_not_found: "Submission not found.",
  deliverable_review_business_only: "Only the business on this contract can review submitted work.",
  deliverable_already_answered: "This submission has already been answered.",
  deliverable_release_escrow_not_held: "This escrow is not held, so it cannot be released.",
  deliverable_changes_need_note: "Say what needs to change, so the creator can fix it.",
  deliverable_withdraw_own_only: "Only the creator who submitted this work can withdraw it.",

  escrow_contract_not_found: "Contract not found.",
  escrow_not_your_contract: "This contract is not yours.",
  escrow_contract_not_signed: "The contract must be fully signed before it can be funded.",
  escrow_already_funded: "This contract is already funded.",
  escrow_not_found: "Escrow not found.",
  escrow_none_for_contract: "No escrow for this contract.",
  escrow_not_a_party: "You are not a party to this escrow.",
  escrow_not_held: "This escrow is not held.",
  escrow_release_business_only: "Only the business can confirm delivery.",

  dispute_not_found: "Dispute not found.",
  dispute_closed: "This dispute is closed.",
  dispute_already_open: "This escrow already has an open dispute.",
  dispute_escrow_not_held: "Only a held escrow can be disputed.",
  dispute_escrow_not_disputed: "This escrow is not under dispute.",
  dispute_frozen_without_case: "This escrow is frozen with no open dispute attached. Report it before settling.",
  dispute_withdraw_own_only: "Only the party who raised the dispute can withdraw it.",
  dispute_reason_unknown: "The reason must be one of: {{reasons}}",
  dispute_statement_too_short: "Say what went wrong in at least {{min}} characters.",
  dispute_statement_too_long: "A statement is at most {{max}} characters.",
  dispute_message_empty: "A message cannot be empty.",
  dispute_message_too_long: "A message is at most {{max}} characters.",
  dispute_evidence_max: "At most {{max}} images can be attached.",
  dispute_evidence_not_found: "Evidence image not found.",
  dispute_evidence_not_yours: "You can only attach images you uploaded.",
  dispute_amount_negative: "Neither amount can be negative.",
  dispute_amounts_must_balance: "{{released}} released and {{refunded}} refunded add up to {{total}}, but the escrow holds {{amount}} {{currency}}. Money must not be invented or destroyed.",

  contact_details_found: "This {{surface}} looks like it contains {{what}}. Kolabo keeps the conversation, the contract and the money in one place: a deal agreed elsewhere has no contract and no escrow behind it, so neither side has any recourse if it goes wrong. Take it out and send the {{surface}} again — nothing was saved and nothing was edited.",
  kind_email: "an email address",
  kind_phone: "a phone number",
  kind_handle: "a messaging app handle",
  surface_message: "message",
  surface_statement: "statement",
  surface_proposal_note: "proposal note",
  list_and: "and"
};

/* i18next's t, narrowed to what this file needs. Taken as an argument rather
   than imported so this module keeps its no-imports property. */
type Translate = (key: string, opts?: Record<string, unknown>) => string;

/* Anything thrown by lib/api.ts, or by fetch, or by a component. Read
   structurally rather than with `instanceof ApiError` — importing ApiError
   would be an import, and a caller that hands us a plain Error (or a string,
   or null) still deserves an answer rather than a crash. */
type MaybeApiError = { code?: unknown; values?: unknown; message?: unknown };

/* Handed to i18next as the defaultValue so a missing key is unmistakable.
   Deliberately not a sentence and not empty: it has to be something no
   translation in either language could ever equal by accident, and something
   that is obviously wrong if it ever does reach a screen. */
const MISS = "::apiError-miss::";

/* Values that are WORDS, not numbers, and so need translating before they are
   interpolated.

   Every other code sends a ceiling or an amount, which goes straight into the
   template. The contact guard sends a list of kinds and a surface — tokens
   naming a concept, not values — and a French sentence needs French nouns and
   a French "et" in the right place. Composing that in Python was impossible
   (the backend does not know the reader's language) and composing it inside
   the template is impossible too (a template interpolates, it does not join).
   So one small step in between, keyed by code.

   PREPARE is a map rather than a branch so the next code that needs this adds
   an entry instead of an `if`. If a code has no entry its values are passed
   through untouched, which is the case for all of them but this one. */
function contactDetails(values: Record<string, unknown>, t: Translate): Record<string, unknown> {
  const kinds = Array.isArray(values.kinds) ? values.kinds.map(String) : [];
  /* An unknown kind falls back to the token. It would be a backend that grew a
     fourth kind without telling anyone, and a stray English word beats a hole
     in the sentence. */
  const names = kinds.map((k) => t(`apiError.kind_${k}`, { defaultValue: k }));
  const last = names.pop() ?? "";
  const what = names.length ? `${names.join(", ")} ${t("apiError.list_and")} ${last}` : last;

  /* "proposal note" -> surface_proposal_note. The backend keeps the spaced
     form because it is also the noun in its own English sentence; normalising
     here is cheaper than carrying two spellings of the same token. */
  const raw = typeof values.surface === "string" ? values.surface : "";
  const surface = t(`apiError.surface_${raw.trim().replace(/\s+/g, "_")}`, { defaultValue: raw });

  return { what, surface };
}

const PREPARE: Record<string, (values: Record<string, unknown>, t: Translate) => Record<string, unknown>> = {
  contact_details_found: contactDetails
};

/* The sentence to show a human for a failed request.

   Order of preference, and the reasoning for each step:

     1. the localised sentence for the code, if the backend sent one and this
        file knows it;
     2. the backend's English `detail`, if there is one. Worse than French for
        a French reader, but it is SPECIFIC — "you have already submitted work
        and the brand has not answered" beats "something went wrong" even in
        the wrong language, because it says what to do next;
     3. the generic sentence, for a network failure or a response that was not
        JSON, where there is nothing specific to say.

   Step 2 is why this migration can be gradual and why it is safe: an
   un-migrated endpoint behaves exactly as it did before this file existed. */
export function errorText(err: unknown, t: Translate): string {
  const e = (err ?? {}) as MaybeApiError;

  if (typeof e.code === "string" && e.code) {
    const values = e.values && typeof e.values === "object" ? (e.values as Record<string, unknown>) : {};
    /* A sentinel rather than "" or the English text, because this has to
       distinguish "no sentence for that code" from "a sentence that happens
       to be falsy", and because i18next returns the KEY ITSELF on a miss —
       without a defaultValue an unknown code puts the literal string
       "apiError.deliverable_whatever" on a user's screen. MISS cannot collide
       with any translation, so an unknown code always falls through to the
       backend's English below, which is the whole reason this migration can
       be gradual. */
    const prepare = PREPARE[e.code];
    const ready = prepare ? prepare(values, t) : values;
    const text = t(`apiError.${e.code}`, { ...ready, defaultValue: MISS });
    if (text !== MISS && text) return text;
  }

  if (typeof e.message === "string" && e.message) return e.message;

  return t(GENERIC_KEY);
}

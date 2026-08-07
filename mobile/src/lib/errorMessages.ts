/* What the API's refusals say, in French and in English — the mobile port of
   web/src/lib/errorMessages.ts.

   The backend answers a refusal with an English `detail` sentence and a stable
   `code` (backend/app/core/errors.py). This holds one sentence per code per
   language; errorText() picks the right one. No imports, so it can be unit
   tested without booting i18next, and i18n.ts folds these two maps in under the
   `apiError` namespace.

   PARITY: the sentences below are copied verbatim from the web catalog so a
   refusal reads identically on both clients. This is the auth-flow subset —
   the rest of the codes get ported as the matching screens land, exactly the
   way the backend migration itself proceeded one module at a time. A code with
   no entry here falls through to the backend's English `message`, which is what
   the app showed before any of this existed. */

export const GENERIC_KEY = "apiError.generic";

export const error_fr: Record<string, string> = {
  generic: "Une erreur est survenue. Réessayez dans un instant.",

  auth_user_not_found: "Utilisateur introuvable.",
  auth_referral_code_failed: "Impossible de générer un code de parrainage. Réessayez.",
  auth_role_unknown: "Le rôle doit être l'un des suivants : {{roles}}",
  auth_country_unavailable: "Kolabo n'est pas encore disponible dans ce pays.",
  auth_phone_taken: "Ce numéro est déjà utilisé par un autre compte.",
  auth_no_pending_verification: "Aucune vérification en attente pour ce numéro.",
  auth_code_expired: "Ce code de vérification a expiré. Demandez-en un nouveau.",
  auth_code_invalid: "Code de vérification invalide.",
  auth_bad_credentials: "Numéro ou mot de passe incorrect.",
  auth_not_verified: "Ce compte n'est pas encore vérifié. Confirmez le code envoyé par SMS.",
  auth_password_incorrect: "Mot de passe actuel incorrect.",
  auth_account_has_history:
    "Ce compte a un historique de transactions et ne peut pas être fermé ici. Contactez le support.",
  auth_token_missing: "Vous n'êtes plus connecté(e). Reconnectez-vous.",
  auth_token_invalid: "Votre session a expiré. Reconnectez-vous.",
  auth_account_nothing_to_change: "Indiquez un nouveau numéro, un nouveau mot de passe, ou les deux.",
  auth_reset_too_many: "Trop de demandes de réinitialisation. Réessayez plus tard.",
  auth_reset_code_invalid: "Ce code de réinitialisation est invalide ou expiré.",

  profile_not_found: "Profil introuvable.",
  profile_under_age: "Vous devez avoir au moins {{min}} ans pour créer un profil de créateur.",
  profile_platform_unsupported: "Cette plateforme n'est pas prise en charge.",
  profile_social_method_unknown: "La méthode de connexion doit être « oauth » ou « manual ».",
  profile_proof_url_required: "Une connexion manuelle demande un lien de preuve.",
  profile_social_not_found: "Compte social introuvable.",
  profile_social_not_yours: "Ce compte social n'est pas le vôtre.",
  profile_duration_pair: "La durée et son unité vont ensemble : indiquez les deux, ou aucun des deux.",
  package_not_found: "Pack introuvable.",
  profile_package_not_yours: "Ce pack n'est pas le vôtre.",
  deliverable_not_on_platform: "« {{type}} » n'existe pas sur {{platform}}. Possibilités : {{allowed}}",
  price_below_floor: "Le prix minimum en {{currency}} est de {{floor}}.",
  profile_image_type_unsupported: "Seules les images JPEG, PNG, WEBP ou GIF sont acceptées.",
  profile_file_empty: "Ce fichier est vide.",
  profile_image_not_found: "Image introuvable.",

  contract_not_found: "Contrat introuvable.",
  contract_not_a_party: "Vous n'êtes pas partie à ce contrat.",
  contract_signed_immutable: "Ce contrat est entièrement signé : il ne peut plus être modifié.",
  contract_you_already_signed: "Vous avez déjà signé.",
  contract_already_cancelled: "Ce contrat est déjà annulé.",
  contract_cancel_signed: "Ce contrat est signé par les deux parties. Elles s'y sont engagées, et ce n'est pas quelque chose qu'une seule peut annuler.",
  contract_cancel_funded: "Ce contrat a de l'argent bloqué en séquestre. Y mettre fin, c'est décider qui doit quoi : cela passe par le litige et le remboursement, pas par une annulation.",

  escrow_contract_not_found: "Contrat introuvable.",
  escrow_not_your_contract: "Ce contrat n'est pas le vôtre.",
  escrow_contract_not_signed: "Le contrat doit être entièrement signé avant d'être financé.",
  escrow_already_funded: "Ce contrat est déjà financé.",
  escrow_not_found: "Séquestre introuvable.",
  escrow_none_for_contract: "Aucun séquestre pour ce contrat.",
  escrow_not_a_party: "Vous n'êtes pas partie à ce séquestre.",
  escrow_not_held: "Le séquestre n'est pas bloqué.",
  escrow_release_business_only: "Seule l'entreprise peut confirmer la livraison.",
  escrow_release_needs_submission:
    "Il n'y a encore rien à confirmer : le créateur n'a pas envoyé de livrable pour ce séquestre. Une fois qu'il l'aura envoyé, confirmer la livraison valide cet envoi et libère le paiement.",

  deliverable_attachments_max: "Vous pouvez joindre au maximum {{max}} fichiers.",
  deliverable_contract_not_found: "Contrat introuvable.",
  deliverable_not_a_party: "Vous n'êtes pas partie à ce contrat.",
  deliverable_submit_creator_only: "Seul le créateur de ce contrat peut envoyer un livrable.",
  deliverable_contract_not_signed: "Un livrable ne peut être envoyé que sur un contrat entièrement signé.",
  deliverable_escrow_not_funded:
    "Aucun fonds n'est encore bloqué en séquestre sur ce contrat : il n'y a donc rien à livrer. Le livrable s'envoie une fois que la marque a payé.",
  deliverable_escrow_not_held: "Le séquestre n'est plus bloqué : aucun livrable ne peut être envoyé.",
  deliverable_submission_open_already:
    "Vous avez déjà envoyé un livrable sur ce contrat et la marque n'a pas encore répondu. Attendez sa réponse ou retirez d'abord votre envoi.",
  deliverable_note_too_long: "Une note fait au plus {{max}} caractères.",
  deliverable_submission_empty:
    "Un envoi doit contenir le lien de la publication, un fichier, ou les deux. Envoyez ce que la marque doit regarder.",
  deliverable_submission_not_found: "Envoi introuvable.",
  deliverable_review_business_only: "Seule l'entreprise de ce contrat peut valider un livrable.",
  deliverable_already_answered: "Cet envoi a déjà reçu une réponse.",
  deliverable_release_escrow_not_held: "Le séquestre n'est pas bloqué : il ne peut pas être libéré.",
  deliverable_changes_need_note: "Dites ce qui doit changer, pour que le créateur puisse corriger.",
  deliverable_withdraw_own_only: "Seul le créateur qui a envoyé ce livrable peut le retirer.",

  dispute_not_found: "Litige introuvable.",
  dispute_closed: "Ce litige est clos.",
  dispute_already_open: "Ce séquestre a déjà un litige ouvert.",
  dispute_escrow_not_held: "Seul un séquestre bloqué peut faire l'objet d'un litige.",
  dispute_escrow_not_disputed: "Ce séquestre n'est pas en litige.",
  dispute_frozen_without_case: "Ce séquestre est gelé sans litige ouvert. Signalez-le avant de trancher.",
  dispute_withdraw_own_only: "Seule la partie qui a ouvert le litige peut le retirer.",
  dispute_reason_unknown: "Le motif doit être l'un des suivants : {{reasons}}",
  dispute_statement_too_short: "Expliquez ce qui s'est passé en au moins {{min}} caractères.",
  dispute_statement_too_long: "Une déclaration fait au plus {{max}} caractères.",
  dispute_message_empty: "Un message ne peut pas être vide.",
  dispute_message_too_long: "Un message fait au plus {{max}} caractères.",
  dispute_evidence_max: "Vous pouvez joindre au maximum {{max}} images.",
  dispute_evidence_not_found: "Image introuvable.",
  dispute_evidence_not_yours: "Vous ne pouvez joindre que des images que vous avez importées.",
};

export const error_en: Record<string, string> = {
  generic: "Something went wrong. Try again in a moment.",

  auth_user_not_found: "User not found.",
  auth_referral_code_failed: "A referral code could not be generated. Please try again.",
  auth_role_unknown: "The role must be one of: {{roles}}",
  auth_country_unavailable: "Kolabo is not available in this country yet.",
  auth_phone_taken: "That number is already used by another account.",
  auth_no_pending_verification: "There is no pending verification for this number.",
  auth_code_expired: "That verification code has expired. Request a new one.",
  auth_code_invalid: "Invalid verification code.",
  auth_bad_credentials: "Wrong number or password.",
  auth_not_verified: "This account is not verified yet. Confirm the code sent by SMS.",
  auth_password_incorrect: "Current password is incorrect.",
  auth_account_has_history:
    "This account has transaction history and cannot be closed here. Contact support.",
  auth_token_missing: "You are not signed in any more. Please sign in again.",
  auth_token_invalid: "Your session has expired. Please sign in again.",
  auth_account_nothing_to_change: "Send a new phone number, a new password, or both.",
  auth_reset_too_many: "Too many reset requests. Try again later.",
  auth_reset_code_invalid: "That reset code is invalid or expired.",

  profile_not_found: "Profile not found.",
  profile_under_age: "You must be at least {{min}} to create a creator profile.",
  profile_platform_unsupported: "That platform is not supported.",
  profile_social_method_unknown: 'The connection method must be "oauth" or "manual".',
  profile_proof_url_required: "A manual connection needs a proof link.",
  profile_social_not_found: "Social account not found.",
  profile_social_not_yours: "That social account is not yours.",
  profile_duration_pair: "A duration and its unit go together: give both, or neither.",
  package_not_found: "Package not found.",
  profile_package_not_yours: "That package is not yours.",
  deliverable_not_on_platform: '"{{type}}" is not available on {{platform}}. Allowed: {{allowed}}',
  price_below_floor: "The minimum price in {{currency}} is {{floor}}.",
  profile_image_type_unsupported: "Only JPEG, PNG, WEBP and GIF images are accepted.",
  profile_file_empty: "That file is empty.",
  profile_image_not_found: "Image not found.",

  contract_not_found: "Contract not found.",
  contract_not_a_party: "You are not a party to this contract.",
  contract_signed_immutable: "This contract is fully signed and can no longer be changed.",
  contract_you_already_signed: "You have already signed.",
  contract_already_cancelled: "This contract is already cancelled.",
  contract_cancel_signed: "This contract is fully signed. Both parties agreed to it, and it is not something either side can cancel alone.",
  contract_cancel_funded: "This contract has money in escrow. Ending it is a question about who is owed what, which is the dispute and refund path, not a cancellation.",

  escrow_contract_not_found: "Contract not found.",
  escrow_not_your_contract: "This contract is not yours.",
  escrow_contract_not_signed: "The contract must be fully signed before it can be funded.",
  escrow_already_funded: "This contract is already funded.",
  escrow_not_found: "Escrow not found.",
  escrow_none_for_contract: "No escrow for this contract.",
  escrow_not_a_party: "You are not a party to this escrow.",
  escrow_not_held: "This escrow is not held.",
  escrow_release_business_only: "Only the business can confirm delivery.",
  escrow_release_needs_submission:
    "There is nothing to confirm yet: the creator has not submitted any work against this escrow. Once they submit it, confirming delivery approves that submission and releases the payment.",

  deliverable_attachments_max: "At most {{max}} files can be attached.",
  deliverable_contract_not_found: "Contract not found.",
  deliverable_not_a_party: "You are not a party to this contract.",
  deliverable_submit_creator_only: "Only the creator on this contract can submit work.",
  deliverable_contract_not_signed: "Work can only be submitted on a fully signed contract.",
  deliverable_escrow_not_funded:
    "This contract has no money in escrow yet, so there is nothing to deliver against. Work is submitted once the brand has funded it.",
  deliverable_escrow_not_held: "This escrow is no longer held, so work cannot be submitted against it.",
  deliverable_submission_open_already:
    "You have already submitted work on this contract and the brand has not answered yet. Wait for their review, or withdraw the submission first.",
  deliverable_note_too_long: "A note is at most {{max}} characters.",
  deliverable_submission_empty:
    "A submission needs the link to the published post, a file, or both. Send what the brand is meant to look at.",
  deliverable_submission_not_found: "Submission not found.",
  deliverable_review_business_only: "Only the business on this contract can review submitted work.",
  deliverable_already_answered: "This submission has already been answered.",
  deliverable_release_escrow_not_held: "This escrow is not held, so it cannot be released.",
  deliverable_changes_need_note: "Say what needs to change, so the creator can fix it.",
  deliverable_withdraw_own_only: "Only the creator who submitted this work can withdraw it.",

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
};

/* i18next's t, narrowed to what this file needs — taken as an argument rather
   than imported so this module keeps its no-imports property. */
type Translate = (key: string, opts?: Record<string, unknown>) => string;

/* Anything thrown by api.ts, or by fetch. Read structurally so a plain Error,
   a string, or null still gets an answer rather than a crash. */
type MaybeApiError = { code?: unknown; values?: unknown; message?: unknown };

/* A sentinel handed to i18next as the defaultValue: it must be something no
   translation could equal, so an unknown code is distinguishable from a real
   (possibly falsy) sentence and falls through to the backend's English. */
const MISS = "::apiError-miss::";

/* The sentence to show a human for a failed request. Order of preference:
   1) the localised sentence for the code, if we know it;
   2) the backend's English `detail`/`message` — specific beats generic even in
      the wrong language, because it says what to do next;
   3) the generic sentence, for a network failure or a non-JSON response. */
export function errorText(err: unknown, t: Translate): string {
  const e = (err ?? {}) as MaybeApiError;

  if (typeof e.code === "string" && e.code) {
    const values =
      e.values && typeof e.values === "object" ? (e.values as Record<string, unknown>) : {};
    const text = t(`apiError.${e.code}`, { ...values, defaultValue: MISS });
    if (text !== MISS && text) return text;
  }

  if (typeof e.message === "string" && e.message) return e.message;

  return t(GENERIC_KEY);
}

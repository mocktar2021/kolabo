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

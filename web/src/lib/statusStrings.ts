/* Supplemental contract copy, registered as a resource bundle that deep-merges
   into the contract.* group — the same arrangement notificationStrings uses for
   nav.* and socialStrings for profile.* — so the 40 KB i18n.ts stays untouched.

   status_cancelled / status_void are the two statuses i18n.ts's contract block
   never got keys for: without them a cancelled contract rendered the raw enum
   "cancelled" on the French screen (and in the contract-list filter chip,
   beside a translated "Signé", which is what surfaced it). void is defined on
   the model but unused today; keyed anyway so it can never leak either.

   untitled / party are the contract-card fallbacks: a campaign with no title,
   and a counterparty who has written no profile yet — never a user id or a
   phone number standing in for a name. */
import i18n from "../i18n";

i18n.addResourceBundle(
  "fr",
  "translation",
  { contract: { status_cancelled: "Annulé", status_void: "Nul", untitled: "Sans titre", party: "Partenaire" } },
  true,
  true
);
i18n.addResourceBundle(
  "en",
  "translation",
  { contract: { status_cancelled: "Cancelled", status_void: "Void", untitled: "Untitled", party: "Partner" } },
  true,
  true
);

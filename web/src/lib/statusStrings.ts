/* The two contract statuses i18n.ts's contract block never got keys for:
   cancelled and void. Registered as a resource bundle that deep-merges into
   the contract.* group, the same arrangement notificationStrings uses for
   nav.* and socialStrings for profile.* — so the 40 KB i18n.ts stays
   untouched. Without these a cancelled contract rendered the raw enum
   "cancelled" on the French screen (and in the contract-list filter chip,
   where the mismatch beside "Signé" is what surfaced it). void is defined on
   the model but unused today; keyed anyway so it can never leak either. */
import i18n from "../i18n";

i18n.addResourceBundle("fr", "translation", { contract: { status_cancelled: "Annulé", status_void: "Nul" } }, true, true);
i18n.addResourceBundle("en", "translation", { contract: { status_cancelled: "Cancelled", status_void: "Void" } }, true, true);

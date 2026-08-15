/* Supplemental status copy, registered as a resource bundle that deep-merges
   into the groups i18n.ts owns — the same arrangement notificationStrings uses
   for nav.* and socialStrings for profile.* — so the 40 KB i18n.ts stays
   untouched. Registered from main.tsx, after ./i18n, so both groups exist by
   the time these keys join them.

   ONE FILE, TWO GROUPS, ONE BUG. Everything here is a status whose block was
   short a key, and the symptom is always the same: the raw enum leaking onto a
   screen in the language it was never written for.

   contract.status_cancelled / status_void are the two statuses i18n.ts's
   contract block never got keys for: without them a cancelled contract
   rendered the raw enum "cancelled" on the French screen (and in the
   contract-list filter chip, beside a translated "Signé", which is what
   surfaced it). void is defined on the model but unused today; keyed anyway so
   it can never leak either.

   campaign.status_completed is the same gap on the campaign block, opened by
   the server learning to finish a brief (campaigns.completion writes
   `completed` when every contract on it has ended and one of those endings was
   the money moving). Its three siblings — draft, published, cancelled — live
   in i18n.ts; this one is here because it arrived after them, exactly as the
   two contract statuses above did. NOTHING IN CI CATCHES THIS CLASS: the
   backend scanners read error codes and notification keys, and a missing label
   is not a type error, so it builds green and only a French reader finds out.

   untitled / party are the contract-card fallbacks: a campaign with no title,
   and a counterparty who has written no profile yet — never a user id or a
   phone number standing in for a name. */
import i18n from "../i18n";

i18n.addResourceBundle(
  "fr",
  "translation",
  {
    contract: { status_cancelled: "Annulé", status_void: "Nul", untitled: "Sans titre", party: "Partenaire" },
    /* Feminine, to agree with "campagne" like Publiée and Annulée beside it. */
    campaign: { status_completed: "Terminée" }
  },
  true,
  true
);
i18n.addResourceBundle(
  "en",
  "translation",
  {
    contract: { status_cancelled: "Cancelled", status_void: "Void", untitled: "Untitled", party: "Partner" },
    campaign: { status_completed: "Completed" }
  },
  true,
  true
);

/* When each round of a negotiation was sent, for the thread on the creator's
   invitations page, registered as a resource bundle so the 40 KB i18n.ts
   stays focused on core app copy — the same arrangement statusStrings uses
   for contract.*, socialStrings for profile.* and notificationStrings for
   nav.*.

   The keys deep-merge into the invitation.* group i18n.ts owns:
   addResourceBundle runs with deep=true and overwrite=true, and main.tsx
   imports this after "./i18n", so they join that group rather than replacing
   it.

   ONLY THE TIMESTAMPS ARE NEW. Who wrote a version already has copy —
   campaign.authorBrand and campaign.authorCreator, which the brand's
   ProposalThread renders on the other side of the same exchange — and the
   thread reuses those rather than wording the same two labels twice.

   The wording mirrors notif.* rather than inventing a second phrasing for
   "il y a 2 h": the bell and the thread are the two places this product says
   how long ago something happened, and they should say it the same way. The
   verb is the only addition, because a bare "il y a 2 h" under a rate reads
   as the age of the row rather than as the moment somebody made the offer. */
import i18n from "../i18n";

const fr = {
  sentJustNow: "Envoyé à l'instant",
  sentMinutesAgo: "Envoyé il y a {{n}} min",
  sentHoursAgo: "Envoyé il y a {{n}} h",
  sentDaysAgo: "Envoyé il y a {{n}} j"
};

const en = {
  sentJustNow: "Sent just now",
  sentMinutesAgo: "Sent {{n}} min ago",
  sentHoursAgo: "Sent {{n}} h ago",
  sentDaysAgo: "Sent {{n}} d ago"
};

i18n.addResourceBundle("fr", "translation", { invitation: fr }, true, true);
i18n.addResourceBundle("en", "translation", { invitation: en }, true, true);

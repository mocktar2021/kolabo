/* Saying no to a proposal, from the brand's side of the campaign page.

   Registered as a resource bundle so the 40 KB i18n.ts stays focused on core
   app copy — the same arrangement negotiationStrings uses for invitation.*,
   statusStrings for contract.* and socialStrings for profile.*.

   The keys deep-merge into the campaign.* group i18n.ts owns, which already
   holds accept, reply and the rest of the proposal thread's labels:
   addResourceBundle runs with deep=true and overwrite=true, and main.tsx
   imports this after "./i18n", so they join that group rather than replacing
   it.

   A SEPARATE BUNDLE FROM undoStrings, even though the two screens sit inches
   apart. That file is one rule read from three places — you may retract what
   you OFFERED until the other side has spent something on it — and rejecting
   is the opposite act: nobody is taking back their own offer here, the brand
   is answering somebody else's. models.py keeps withdrawn, declined and
   rejected apart for exactly that reason, and copy that blurred them would be
   the first place the distinction went.

   THE CONFIRMATION HAS TO SAY WHAT IS IRREVERSIBLE, because the button does
   not look it. `rejected` is one of the three terminal resolutions
   submit_proposal refuses to reopen, so the creator cannot answer with a new
   version on this brief — that is a door closing, and a buyer who wanted to
   push back on a price rather than end the conversation should be reaching for
   Reply instead. It also says what does NOT change, because the fear that
   stops somebody clearing their proposals list is that they are cancelling the
   brief. */
import i18n from "../i18n";

const fr = {
  /* Court, parce qu'il se place à côté d'« Accepter » et « Répondre ». La
     phrase entière est dans la confirmation, où il y a la place de la lire. */
  reject: "Rejeter",
  rejectConfirm:
    "Rejeter cette proposition ? Le créateur en sera informé, sans motif et sans reproche. C'est définitif pour cette négociation : elle sera close et il ne pourra plus vous envoyer de nouvelle version sur ce brief. Si vous vouliez seulement discuter le prix ou le délai, répondez-lui plutôt. Les autres propositions ne bougent pas et le brief reste ouvert.",
  rejectYes: "Rejeter la proposition",
  rejectNo: "La laisser ouverte"
};

const en = {
  reject: "Reject",
  rejectConfirm:
    "Reject this proposal? The creator is told, with no reason attached and no blame. This is final for this negotiation: it closes, and they cannot send you a new version on this brief. If you only wanted to push back on the price or the timeline, reply instead. The other proposals are untouched and the brief stays open.",
  rejectYes: "Reject the proposal",
  rejectNo: "Leave it open"
};

i18n.addResourceBundle("fr", "translation", { campaign: fr }, true, true);
i18n.addResourceBundle("en", "translation", { campaign: en }, true, true);

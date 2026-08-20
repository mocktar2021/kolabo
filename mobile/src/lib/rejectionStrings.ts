import i18n from "../i18n";

/* Saying no to a proposal, from the brand's side of the campaign screen.

   REGISTERED AT RUNTIME, like parityStrings.ts and packageStrings.ts and for
   the same reason: src/strings.ts is 60 KB and a four-key change lands in it
   invisibly. The consequence is the thing to remember — the screen that reads
   these keys must import this module FOR ITS SIDE EFFECT or it renders the
   raw key at the reader. One does: components/campaigns/ProposalThread. The
   keys deep-merge into the campaign.* group strings.ts already owns, which
   holds accept, reply and the rest of the thread's labels — addResourceBundle
   runs with deep=true and overwrite=true — so they join that group rather
   than replacing it.

   COPIED WORD FOR WORD from web/src/lib/rejectionStrings.ts, both languages,
   the way parityStrings copies deliverableStrings and undoStrings. The same
   act reading differently on two clients is itself a defect, and a
   confirmation is the worst place to have one: this sentence is the last
   thing somebody reads before closing a negotiation for good, so a phone
   reader given a shorter version would be deciding on less than a browser
   reader. A sentence here is rewritten in BOTH files or in neither.

   THE CONFIRMATION HAS TO SAY WHAT IS IRREVERSIBLE, because the control does
   not look it. `rejected` is one of the three terminal resolutions
   submit_proposal refuses to reopen, so that creator cannot come back with a
   new version on this brief — that is a door closing, and a buyer who only
   wanted to push back on a price should be reaching for Reply instead. It
   also says what does NOT change, because the fear that stops somebody
   clearing their proposals list is that they are cancelling the brief.

   French first, like the other bundles: three of the five launch markets are
   francophone. */

const fr = {
  /* Court, parce qu'il se lit sous « Accepter » et « Répondre ». La phrase
     entière est dans la confirmation, où il y a la place de la lire. */
  reject: "Rejeter",
  rejectConfirm:
    "Rejeter cette proposition ? Le créateur en sera informé, sans motif et sans reproche. C'est définitif pour cette négociation : elle sera close et il ne pourra plus vous envoyer de nouvelle version sur ce brief. Si vous vouliez seulement discuter le prix ou le délai, répondez-lui plutôt. Les autres propositions ne bougent pas et le brief reste ouvert.",
  rejectYes: "Rejeter la proposition",
  rejectNo: "La laisser ouverte",
};

const en = {
  reject: "Reject",
  rejectConfirm:
    "Reject this proposal? The creator is told, with no reason attached and no blame. This is final for this negotiation: it closes, and they cannot send you a new version on this brief. If you only wanted to push back on the price or the timeline, reply instead. The other proposals are untouched and the brief stays open.",
  rejectYes: "Reject the proposal",
  rejectNo: "Leave it open",
};

i18n.addResourceBundle("fr", "translation", { campaign: fr }, true, true);
i18n.addResourceBundle("en", "translation", { campaign: en }, true, true);

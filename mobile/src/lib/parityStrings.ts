import i18n from "../i18n";

/* Copy for the three signed-in controls the phone did not have: attaching a
   file to a deliverable, calling off a contract nobody has signed yet, and the
   payout section on the earnings screen.

   REGISTERED AT RUNTIME, like paymentStrings.ts and packageStrings.ts and for
   the same reason: src/strings.ts is 60 KB and a twenty-key change lands in it
   invisibly. The consequence is the thing to remember — every screen that uses
   a key below must import this module FOR ITS SIDE EFFECT, or it renders the
   raw key at the reader. Three screens do: DeliverablesPanel,
   ContractDetailScreen and EarningsScreen.

   THREE GROUPS IN ONE FILE because they are one change — the three places the
   phone could see something the browser could do — and splitting twenty keys
   across three modules would be three imports to forget instead of one.
   Anything that outgrows a control belongs back in strings.ts with the rest of
   its group.

   ONE KEY BELOW IS AN OVERRIDE, NOT AN ADDITION. deliv.needSomething already
   exists in strings.ts and says "Add the link to the post." — which was true
   only while mobile had no picker. addResourceBundle runs deep and overwrite,
   so the sentence here replaces it, and the form now states the rule the
   server actually enforces: a submission needs a link, a file, or both (see
   EMPTY_DETAIL in backend/app/modules/deliverables/service.py). Web has said
   this all along.

   The deliv and undo sentences are copied word for word from
   web/src/lib/deliverableStrings.ts and web/src/lib/undoStrings.ts, so the
   same confirmation reads identically on both clients — divergence between two
   clients' wording for one act is itself a defect. The payout group is new
   copy: web puts its payout route in the earnings header and explains the
   awaiting-wallet state only in a code comment, so there was no sentence to
   port.

   French first, like the other bundles: three of the five launch markets are
   francophone. */

const fr = {
  deliv: {
    attachments: "Pièces jointes",
    /* Remplace la phrase de strings.ts : le téléphone peut désormais joindre
       un fichier, donc la règle affichée redevient celle du serveur. */
    needSomething: "Ajoutez le lien de la publication, un fichier, ou les deux.",
  },

  /* Annuler un contrat que personne n'a encore entièrement signé. Les deux
     refus possibles — signé, ou financé — arrivent du backend avec leur code
     (contract_cancel_signed, contract_cancel_funded) et sont déjà traduits
     dans lib/errorMessages.ts : rien à réécrire ici. */
  undo: {
    contractTitle: "Annuler ce contrat",
    contractExplain: "Tant que les deux signatures ne sont pas là et qu'aucun argent n'est bloqué, chacune des deux parties peut mettre fin à ce contrat. Le dire ici vaut mieux que de ne plus répondre : un contrat à moitié signé reste dans la liste de l'autre indéfiniment.",
    contractCancel: "Annuler le contrat",
    contractConfirm: "Annuler ce contrat ? L'autre partie en sera informée et le contrat passera au statut « annulé ». Il n'y a rien à rembourser (aucun argent n'a été bloqué), mais l'accord est terminé : pour retravailler ensemble, il faudra repartir d'une nouvelle proposition.",
    contractYes: "Annuler le contrat",
    contractNo: "Le garder",
  },

  payout: {
    title: "Versements",
    hint: "L'argent libéré d'un séquestre part sur votre portefeuille Mobile Money. Le versement est automatique : vous n'avez rien à réclamer.",
    walletSaved: "Portefeuille enregistré",
    change: "Modifier le portefeuille",
    add: "Ajouter mon portefeuille",
    none: "Aucun portefeuille enregistré pour l'instant. Ajoutez-le avant votre premier paiement : nous n'avons aucun autre moyen de vous envoyer l'argent.",
    awaitingTitle: "Votre argent vous attend",
    releasedLabel: "Libéré pour vous",
    awaiting: "Cet argent est à vous. Mais aucun portefeuille Mobile Money n'est enregistré, donc nous n'avons nulle part où l'envoyer. Ajoutez-le : le versement partira tout seul au prochain envoi, sans que vous ayez à le redemander.",
    unknown: "Impossible de vérifier votre portefeuille de versement pour l'instant.",
  },
};

const en = {
  deliv: {
    attachments: "Attachments",
    needSomething: "Add the link to the post, a file, or both.",
  },

  undo: {
    contractTitle: "Cancel this contract",
    contractExplain: "While both signatures are not in and no money is held, either party can end this contract. Saying so here beats going quiet: a half-signed contract sits in the other person's list indefinitely.",
    contractCancel: "Cancel the contract",
    contractConfirm: "Cancel this contract? The other party is told and the contract moves to \"cancelled\". There is nothing to refund (no money was ever held), but the agreement is over: working together again means starting from a new proposal.",
    contractYes: "Cancel the contract",
    contractNo: "Keep it",
  },

  payout: {
    title: "Payouts",
    hint: "Money released from an escrow is sent to your Mobile Money wallet. The payout is automatic: there is nothing to claim.",
    walletSaved: "Saved wallet",
    change: "Change the wallet",
    add: "Add my payout wallet",
    none: "No wallet saved yet. Add one before your first payment: we have no other way to send you the money.",
    awaitingTitle: "Your money is waiting",
    releasedLabel: "Released to you",
    awaiting: "This money is yours. But no Mobile Money wallet is on file, so we have nowhere to send it. Add one and the payout goes out on its own at the next run. You do not have to ask for it again.",
    unknown: "We could not check your payout wallet just now.",
  },
};

i18n.addResourceBundle("fr", "translation", fr, true, true);
i18n.addResourceBundle("en", "translation", en, true, true);

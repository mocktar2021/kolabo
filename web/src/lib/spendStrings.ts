/* Buyer-side statement copy, registered as a resource bundle so the 40 KB
   i18n.ts stays focused on the core app copy — the same arrangement the cart,
   the disputes queue, the admin console, the account settings and the
   earnings screen use.

   nav.payments and dash.* are deep-merged into the groups i18n.ts owns,
   exactly as nav.earnings is in earningsStrings.ts: addResourceBundle runs
   with deep=true and overwrite=true, and main.tsx imports this after
   "./i18n", so the keys join the existing groups rather than replacing
   them. */
import i18n from "../i18n";

const fr = {
  title: "Mes paiements",
  sub: "Ce que vous avez dépensé, ce qui est engagé, et ce qui vous est revenu.",

  spent: "Dépensé",
  pending: "En attente",
  disputed: "En litige",
  refunded: "Remboursé",

  /* Quatre états et pas trois. "Remboursé" existe ici et n'existe pas chez
     le créateur : l'argent revenu est une vraie ligne du registre de
     l'acheteur — il l'a payé, il l'a récupéré — alors que pour le créateur
     c'est de l'argent qui n'est jamais arrivé. */
  spentHint: "Versé au créateur. La somme entière, telle que vous l'avez payée.",
  pendingHint: "Déjà payé et bloqué en séquestre, en attendant la livraison.",
  disputedHint: "Gelé le temps qu'un litige soit tranché. Une partie peut vous revenir.",
  refundedHint: "Revenu chez vous, en totalité ou après un partage.",

  /* La différence visible avec l'écran du créateur, dite une fois : la
     commission Kolabo est prélevée sur ce que le créateur reçoit, pas sur ce
     que vous payez. Une marque qui a financé 100 000 a payé 100 000, et une
     colonne "net" ici l'inviterait à croire qu'on lui a facturé quelque chose
     en plus. */
  gross: "Aucun de ces montants n'est amputé d'une commission : la commission Kolabo est prélevée sur ce que le créateur reçoit, jamais sur ce que vous payez. Ce que vous voyez ici est ce qui est parti de votre portefeuille.",

  currencyGroup: "Montants en {{currency}}",
  currencyRule: "Vos marchés sont comptés séparément : deux devises, deux budgets. Aucun total ne les additionne.",

  statement: "Relevé des paiements",
  colDate: "Date",
  colCampaign: "Campagne",
  colCreator: "Créateur",
  colAmount: "Montant",
  colStatus: "Statut",
  /* Porté sur la ligne et pas seulement dans les totaux : sinon un partage
     affiche 60 000 dépensés sur un contrat financé à 100 000, et les 40 000
     revenus apparaissent dans un total sans aucune ligne à laquelle les
     rattacher. */
  rowRefunded: "dont {{amount}} remboursé",
  noDate: "Sans date",
  untitled: "Campagne sans titre",
  unknownCreator: "Créateur",

  /* La contrepartie, telle qu'elle s'appelle de ce côté du séquestre. Sur
     l'écran du créateur le même filtre s'appelle "Client" : c'est toujours
     "l'autre partie", et qui c'est dépend de qui regarde. */
  creatorLabel: "Créateur",
  creatorAll: "Tous les créateurs",

  empty: "Aucun paiement pour l'instant.",
  emptyHint: "Un paiement apparaît ici quand vous bloquez l'argent en séquestre : après la signature du contrat, pas à la commande.",
  loadFailed: "Impossible de charger vos paiements pour l'instant."
};

const en = {
  title: "My payments",
  sub: "What you have spent, what is committed, and what has come back to you.",

  spent: "Spent",
  pending: "Pending",
  disputed: "In dispute",
  refunded: "Refunded",

  spentHint: "Released to the creator. The full amount, exactly as you paid it.",
  pendingHint: "Already paid and held in escrow, waiting on delivery.",
  disputedHint: "Frozen until a dispute is decided. Some of it may come back to you.",
  refundedHint: "Returned to you, in full or after a split.",

  gross: "None of these figures has a commission taken off: the Kolabo commission comes out of what the creator receives, never out of what you pay. What you see here is what left your wallet.",

  currencyGroup: "Amounts in {{currency}}",
  currencyRule: "Your markets are counted separately: two currencies, two budgets. No total adds them together.",

  statement: "Payment statement",
  colDate: "Date",
  colCampaign: "Campaign",
  colCreator: "Creator",
  colAmount: "Amount",
  colStatus: "Status",
  rowRefunded: "including {{amount}} refunded",
  noDate: "No date",
  untitled: "Untitled campaign",
  unknownCreator: "Creator",

  creatorLabel: "Creator",
  creatorAll: "All creators",

  empty: "No payments yet.",
  emptyHint: "A payment appears here when you hold the money in escrow: after the contract is signed, not when you order.",
  loadFailed: "Your payments could not be loaded right now."
};

const frDash = {
  paymentsTitle: "Mes paiements",
  paymentsDesc: "Ce que vous avez dépensé, ce qui est engagé, et ce qui vous est revenu."
};

const enDash = {
  paymentsTitle: "My payments",
  paymentsDesc: "What you have spent, what is committed, and what has come back to you."
};

i18n.addResourceBundle("fr", "translation", { spend: fr, dash: frDash, nav: { payments: "Paiements" } }, true, true);
i18n.addResourceBundle("en", "translation", { spend: en, dash: enDash, nav: { payments: "Payments" } }, true, true);

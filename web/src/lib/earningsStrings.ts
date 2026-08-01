/* Earnings screen copy, registered as a resource bundle so the 40 KB i18n.ts
   stays focused on the core app copy — the same arrangement the cart, the
   disputes queue, the admin console and the account settings use.

   nav.earnings is deep-merged into the nav group i18n.ts owns, exactly as
   nav.account is in accountStrings.ts: addResourceBundle runs with deep=true
   and overwrite=true, and main.tsx imports this after "./i18n", so the key
   joins the existing menu rather than replacing it. */
import i18n from "../i18n";

const fr = {
  title: "Mes gains",
  sub: "Ce qui vous a été versé, ce qui arrive, et ce qui est bloqué par un litige.",

  earned: "Gagné",
  pending: "En attente",
  disputed: "En litige",
  /* Trois états et pas deux. "En attente" est une promesse datable : la
     marque a déjà payé, le séquestre se libère à la livraison. "En litige"
     n'a aucune date et peut repartir chez l'acheteur — les confondre
     mettrait à l'écran un montant qui dit "comptez dessus" alors qu'il veut
     dire "défendez-le". */
  earnedHint: "Versé, c'est à vous.",
  pendingHint: "Payé par la marque, bloqué en séquestre jusqu'à la livraison.",
  disputedHint: "Gelé le temps qu'un litige soit tranché.",

  /* Dit une fois, sous les tuiles, et sans pourcentage écrit en dur : la
     définition de la commission vit côté serveur (commission_for), et un
     taux recopié ici serait la copie qui dérive. Le tableau montre les trois
     colonnes, ce qui est la vraie réponse à "vous avez pris combien ?". */
  commission: "Tous les montants ci-dessus sont nets : la commission Kolabo est déduite au moment où l'argent vous est versé. Chaque ligne du relevé montre le brut, la commission et le net, pour que rien ne soit seulement soustrait.",

  currencyGroup: "Montants en {{currency}}",
  /* La règle, dite à l'écran dès qu'il y a deux devises : on n'additionne
     jamais deux marchés. */
  currencyRule: "Vos marchés sont comptés séparément : deux devises, deux soldes. Aucun total ne les additionne.",

  statement: "Relevé des paiements",
  colDate: "Date",
  colWhat: "Campagne et client",
  colStatus: "Statut",
  colGross: "Brut",
  colCommission: "Commission",
  colNet: "Net",
  noDate: "—",
  untitled: "Campagne sans titre",
  unknownBrand: "Marque",
  viewContract: "Voir le contrat",

  yearLabel: "Année",
  yearAll: "Toutes les années",

  empty: "Aucun paiement pour l'instant.",
  emptyHint: "Un paiement apparaît ici quand une marque bloque l'argent en séquestre — après la signature, pas à la signature.",
  loadFailed: "Impossible de charger vos gains pour l'instant."
};

const en = {
  title: "My earnings",
  sub: "What has been paid out to you, what is on its way, and what a dispute has frozen.",

  earned: "Earned",
  pending: "Pending",
  disputed: "In dispute",
  earnedHint: "Released. It is yours.",
  pendingHint: "Paid by the brand, held in escrow until delivery.",
  disputedHint: "Frozen until a dispute is decided.",

  commission: "Every figure above is net: the Kolabo commission comes off at the moment the money is released to you. Each line of the statement shows gross, commission and net, so nothing is merely subtracted.",

  currencyGroup: "Amounts in {{currency}}",
  currencyRule: "Your markets are counted separately: two currencies, two balances. No total adds them together.",

  statement: "Payment statement",
  colDate: "Date",
  colWhat: "Campaign and client",
  colStatus: "Status",
  colGross: "Gross",
  colCommission: "Commission",
  colNet: "Net",
  noDate: "—",
  untitled: "Untitled campaign",
  unknownBrand: "Brand",
  viewContract: "View the contract",

  yearLabel: "Year",
  yearAll: "All years",

  empty: "No payments yet.",
  emptyHint: "A payment appears here when a brand holds the money in escrow — after signing, not at signing.",
  loadFailed: "Your earnings could not be loaded right now."
};

i18n.addResourceBundle("fr", "translation", { earn: fr, nav: { earnings: "Gains" } }, true, true);
i18n.addResourceBundle("en", "translation", { earn: en, nav: { earnings: "Earnings" } }, true, true);

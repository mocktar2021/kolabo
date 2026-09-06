import i18n from "../i18n";

/* Copy for the hosted checkout and the payout-method form, ported word for
   word from web/src/lib/paymentStrings.ts so a payer reads the same sentences
   on both clients.

   A DELIBERATE DEVIATION FROM THE strings.ts CONVENTION. Every other key in
   this app lives in src/strings.ts, which i18n.ts spreads into the resource
   bundle once at boot. That file is 55 KB, and adding a self-contained
   feature's forty keys to it would bury this diff inside the one file every
   reviewer already scrolls past. Registering the pay.* group at runtime with
   addResourceBundle keeps the payment copy next to the payment code and the
   review readable; the tradeoff is that a screen using these keys must import
   this module for its side effect, which the two payment screens do at the
   top of their imports. Anything that outgrows one feature belongs back in
   strings.ts.

   French first, like the web bundle: it is the pilot default and three of the
   five launch markets are francophone. */

const fr = {
  title: "Paiement sécurisé",
  subtitle: "Votre argent est conservé en séquestre jusqu'à la validation du travail.",
  amount: "Montant à payer",
  contract: "Contrat",
  payNow: "Payer par Mobile Money",
  opening: "Ouverture du paiement…",
  waiting: "En attente de votre paiement",
  waitingHint:
    "Validez le paiement sur votre téléphone. Cette page se met à jour automatiquement. Ne la fermez pas.",
  reopen: "Rouvrir la page de paiement",
  succeeded: "Paiement confirmé",
  succeededHint: "Les fonds sont en séquestre. Le créateur peut commencer le travail.",
  backToContract: "Retour au contrat",
  failed: "Le paiement n'a pas abouti",
  failedHint: "Aucun montant n'a été débité. Vous pouvez réessayer.",
  retry: "Réessayer",
  canceled: "Paiement annulé",
  /* The amount-mismatch case. Deliberately does NOT say "payment failed": money
     may well have left the payer's wallet, and telling them nothing happened
     would be a lie about their money. */
  mismatch: "Montant inattendu",
  mismatchHint:
    "Le montant reçu ne correspond pas au contrat. Nous avons suspendu l'opération par sécurité. Contactez le support avec la référence ci-dessous.",
  reference: "Référence",
  unavailable: "Paiements indisponibles",
  unavailableHint:
    "Les paiements en ligne ne sont pas encore ouverts dans votre pays. Nous vous préviendrons dès que c'est disponible.",
  sandbox: "Mode test : aucun argent réel n'est débité.",

  payoutTitle: "Où souhaitez-vous être payé ?",
  payoutHint:
    "Nous envoyons vos gains sur ce portefeuille Mobile Money. Choisissez le réseau : nous ne le devinons pas à partir du numéro.",
  payoutCountry: "Pays",
  payoutNetwork: "Réseau",
  payoutPhone: "Numéro Mobile Money",
  payoutName: "Nom du titulaire du compte",
  payoutSave: "Enregistrer",
  payoutSaved: "Vos coordonnées de paiement sont enregistrées.",
  payoutCurrent: "Portefeuille enregistré",
  payoutMissing: "Ajoutez vos coordonnées Mobile Money pour recevoir vos paiements.",
};

const en = {
  title: "Secure payment",
  subtitle: "Your money is held in escrow until the work is approved.",
  amount: "Amount to pay",
  contract: "Contract",
  payNow: "Pay with Mobile Money",
  opening: "Opening payment…",
  waiting: "Waiting for your payment",
  waitingHint:
    "Approve the payment on your phone. This page updates on its own. Please don't close it.",
  reopen: "Reopen the payment page",
  succeeded: "Payment confirmed",
  succeededHint: "The funds are in escrow. The creator can start the work.",
  backToContract: "Back to the contract",
  failed: "The payment didn't go through",
  failedHint: "Nothing was charged. You can try again.",
  retry: "Try again",
  canceled: "Payment cancelled",
  mismatch: "Unexpected amount",
  mismatchHint:
    "The amount received doesn't match the contract, so we've paused this for safety. Please contact support with the reference below.",
  reference: "Reference",
  unavailable: "Payments unavailable",
  unavailableHint:
    "Online payments aren't open in your country yet. We'll let you know as soon as they are.",
  sandbox: "Test mode: no real money is charged.",

  payoutTitle: "Where should we pay you?",
  payoutHint:
    "We send your earnings to this Mobile Money wallet. Pick the network. We don't guess it from the number.",
  payoutCountry: "Country",
  payoutNetwork: "Network",
  payoutPhone: "Mobile Money number",
  payoutName: "Account holder name",
  payoutSave: "Save",
  payoutSaved: "Your payout details are saved.",
  payoutCurrent: "Saved wallet",
  payoutMissing: "Add your Mobile Money details so we can send your payments.",
};

i18n.addResourceBundle("fr", "translation", { pay: fr }, true, true);
i18n.addResourceBundle("en", "translation", { pay: en }, true, true);

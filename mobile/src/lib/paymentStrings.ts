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
  /* Le refus que l'opérateur renvoie le plus souvent, et le seul dont la
     cause soit réparable par la marque elle-même. Le message générique est
     vrai et inutile ici : il invite à réessayer, et une marque qui réessaie
     avec le même numéro échoue une deuxième fois. Les codes non reconnus
     gardent le message générique plutôt que d'être devinés. */
  failedPayerNotFound:
    "L'opérateur n'a pas reconnu ce numéro. Vérifiez qu'il est au format international, sans le +, avec l'indicatif du pays et sans espaces.",
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

  /* The funding form, shown only when the gateway pushes a request to a
     handset instead of opening a page. A redirect flow never sees these. */
  fundHow: "Payer par Mobile Money",
  fundHowHint:
    "Choisissez votre réseau et le numéro à débiter. Nous enverrons une demande de paiement sur ce téléphone.",
  fundNetwork: "Réseau Mobile Money",
  fundPhone: "Numéro à débiter",
  /* LE FORMAT EST DIT AVANT, pas après. KOL-149 : deux paiements réels ont
     échoué le 31 octobre sur un numéro saisi en local, et le refus de
     l'opérateur ne dit rien d'utile à quelqu'un qui regarde un numéro qui
     est le sien et qui lui semble juste.

     UN SEUL EXEMPLE, ET C'EST VOULU. 229 est l'indicatif confirmé par un
     paiement réellement encaissé. Les trois autres marchés n'ont pas été
     vérifiés contre une source à jour, et un exemple faux dans un champ de
     paiement apprend la mauvaise habitude au lieu de corriger l'erreur. */
  fundPhoneHint:
    "Le numéro du portefeuille qui paie. Il peut être différent du numéro de votre compte. Saisissez-le au format international, sans le +, indicatif du pays compris : un numéro béninois commence par 229.",
  /* DIT AVANT DE PAYER, pas après. Le 31 octobre, un financement de 500 XOF
     a débité 509 : l'opérateur ajoute ses frais par-dessus le montant
     demandé et les facture au payeur. KOL-153. */
  fundOperatorFee:
    "Votre opérateur ajoute ses propres frais au montant ci-dessus, au moment du paiement. Ces frais lui reviennent et non à Kolabo, donc le total débité de votre portefeuille sera un peu plus élevé.",
  fundSubmit: "Envoyer la demande",
  fundPickNetwork: "Choisissez votre réseau Mobile Money.",
  fundNeedPhone: "Saisissez le numéro à débiter.",
  /* The pending state for a prompt. Deliberately different wording from
     `waiting`, which is written for somebody who has just come back from a
     payment page: here nothing opened and the only instruction that helps is
     where to look. */
  promptSent: "Demande envoyée sur votre téléphone",
  promptSentHint:
    "Ouvrez la demande de paiement sur votre téléphone et saisissez votre code. Cet écran se met à jour automatiquement. Ne le fermez pas.",
  promptSentTo: "Envoyée au",
  promptChange: "Changer de réseau ou de numéro",

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
  failedPayerNotFound:
    "The operator did not recognise that number. Check that it is in international format, without the plus sign, with the country code and no spaces.",
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

  fundHow: "Pay with Mobile Money",
  fundHowHint:
    "Choose your network and the number to charge. We'll send a payment request to that phone.",
  fundNetwork: "Mobile Money network",
  fundPhone: "Number to charge",
  fundPhoneHint:
    "The wallet that pays. It can be different from the number on your account. Enter it in international format, without the plus sign and including the country code: a Benin number starts with 229.",
  fundOperatorFee:
    "Your operator adds its own fee on top of the amount above when you pay. That fee goes to them and not to Kolabo, so the total taken from your wallet will be slightly higher.",
  fundSubmit: "Send the request",
  fundPickNetwork: "Choose your Mobile Money network.",
  fundNeedPhone: "Enter the number to charge.",
  promptSent: "Request sent to your phone",
  promptSentHint:
    "Open the payment request on your phone and enter your PIN. This screen updates on its own. Please don't close it.",
  promptSentTo: "Sent to",
  promptChange: "Change network or number",

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

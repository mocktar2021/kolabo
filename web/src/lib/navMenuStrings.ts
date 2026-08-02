/* Copy for the account menu in the nav and for the dashboard cards that were
   missing from it, registered as a resource bundle so the 40 KB i18n.ts stays
   focused on the core app copy — the same arrangement the cart, the disputes
   queue, the admin console, the account settings and the earnings screen use.

   The dash.* keys are deep-merged into the group i18n.ts owns, exactly as
   nav.earnings is in earningsStrings.ts: addResourceBundle runs with
   deep=true and overwrite=true, and main.tsx imports this after "./i18n", so
   the keys join the existing group rather than replacing it. */
import i18n from "../i18n";

const frMenu = {
  /* The label is on the button rather than inside it: the control is an
     avatar and three dashes, which say nothing to a screen reader. */
  account: "Menu du compte"
};

const enMenu = {
  account: "Account menu"
};

/* The cards a role could reach from the nav but not from the dashboard.

   Messages and litiges are offered to BOTH sides, and are asked no role
   question at all — the same decision the nav makes for the same reason: a
   contract has exactly two parties, and either of them may be the one who has
   not replied or the one with a claim on the money held between them. */
const frDash = {
  messagesTitle: "Messages",
  messagesDesc: "Vos conversations avec l'autre partie, contrat par contrat, sans quitter la plateforme.",

  disputesTitle: "Litiges",
  disputesDesc: "Les réclamations ouvertes sur un paiement, et celles qui attendent votre réponse.",

  /* Créateurs uniquement. Une marque qui ouvre /payments/earnings reçoit des
     totaux vides : ce qu'un acheteur veut, c'est la dépense, et c'est une
     autre question avec le signe opposé. */
  earningsTitle: "Mes gains",
  earningsDesc: "Ce qui vous a été versé, ce qui arrive, et ce qui est bloqué par un litige."
};

const enDash = {
  messagesTitle: "Messages",
  messagesDesc: "Your conversations with the other party, contract by contract, without leaving the platform.",

  disputesTitle: "Disputes",
  disputesDesc: "Claims opened on a payment, and the ones waiting on your answer.",

  earningsTitle: "My earnings",
  earningsDesc: "What has been paid out to you, what is on its way, and what a dispute has frozen."
};

i18n.addResourceBundle("fr", "translation", { menu: frMenu, dash: frDash }, true, true);
i18n.addResourceBundle("en", "translation", { menu: enMenu, dash: enDash }, true, true);

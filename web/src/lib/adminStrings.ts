/* Admin strings, registered as a resource bundle like every other section of
   the app. Bilingual for the same reason the rest is: the pilot desk is in
   Cotonou and the operator reads French. */
import i18n from "../i18n";

const fr = {
  disputesTitle: "File des litiges",
  disputesSub:
    "Les cas dont la fenêtre de réponse est close viennent en premier, du plus ancien au plus récent.",
  /* The placeholder credential. The wording says what it is rather than
     dressing it up as a login — an operator who thinks this is authentication
     will treat the id as a secret, and it is not one. */
  idLabel: "Identifiant administrateur",
  idHint:
    "Provisoire : l'authentification administrateur n'existe pas encore, l'identifiant est envoyé tel quel à l'API.",
  idSave: "Enregistrer",
  idMissing: "Renseignez un identifiant administrateur pour charger la file.",
  empty: "Aucun litige à traiter.",
  brand: "Marque",
  creator: "Créateur",
  unnamed: "Sans nom",
  messages: "{{n}} message(s)",
  openedAgo: "Ouvert il y a {{age}}",
  ageDays: "{{n}} j",
  ageHours: "{{n}} h",
  openCase: "Ouvrir le cas",
  closeCase: "Fermer",
  resolveTitle: "Trancher",
  released: "Libéré au créateur",
  refunded: "Remboursé à la marque",
  /* The remainder is the whole safety mechanism made visible. The server
     refuses a split that does not add up exactly, so the form shows what is
     still unallocated instead of letting somebody discover it as a 400. */
  remainder: "Reste à répartir : {{n}} {{currency}}",
  balanced: "Les deux montants couvrent exactement le séquestre.",
  fullRelease: "Tout libérer",
  fullRefund: "Tout rembourser",
  note: "Note de décision",
  notePlaceholder: "Ce qui a été décidé et pourquoi. Les deux parties la liront.",
  submit: "Enregistrer la décision",
  /* Said next to the figures because the split changes the fee. */
  commission: "Commission ({{pct}} %) : {{n}} {{currency}}",
  netToCreator: "Le créateur reçoit {{n}} {{currency}}",
  commissionHint:
    "La commission ne porte que sur la part libérée : les frais suivent le travail."
};

const en = {
  disputesTitle: "Dispute queue",
  disputesSub: "Cases whose response window has closed come first, oldest first.",
  idLabel: "Admin id",
  idHint:
    "Temporary: admin authentication does not exist yet, the id is sent to the API as typed.",
  idSave: "Save",
  idMissing: "Enter an admin id to load the queue.",
  empty: "Nothing in the queue.",
  brand: "Brand",
  creator: "Creator",
  unnamed: "Unnamed",
  messages: "{{n}} message(s)",
  openedAgo: "Opened {{age}} ago",
  ageDays: "{{n}} d",
  ageHours: "{{n}} h",
  openCase: "Open the case",
  closeCase: "Close",
  resolveTitle: "Decide",
  released: "Released to the creator",
  refunded: "Refunded to the brand",
  remainder: "Still to allocate: {{n}} {{currency}}",
  balanced: "The two amounts cover the escrow exactly.",
  fullRelease: "Release everything",
  fullRefund: "Refund everything",
  note: "Decision note",
  notePlaceholder: "What was decided and why. Both parties will read it.",
  submit: "Record the decision",
  commission: "Commission ({{pct}} %): {{n}} {{currency}}",
  netToCreator: "The creator receives {{n}} {{currency}}",
  commissionHint:
    "Commission is charged on the released part only: the fee follows the work."
};

i18n.addResourceBundle("fr", "translation", { admin: fr }, true, true);
i18n.addResourceBundle("en", "translation", { admin: en }, true, true);

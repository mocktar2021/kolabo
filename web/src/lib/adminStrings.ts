/* Admin strings, registered as a resource bundle like every other section of
   the app. Bilingual for the same reason the rest is: the pilot desk is in
   Cotonou and the operator reads French. */
import i18n from "../i18n";

const fr = {
  disputesTitle: "File des litiges",
  disputesSub:
    "Les cas dont la fenêtre de réponse est close viennent en premier, du plus ancien au plus récent.",
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

/* The one nav label this bundle owns. It joins the nav.* group i18n.ts owns,
   which is the reason main.tsx imports this file after "./i18n":
   addResourceBundle deep-merges, so the key joins that group rather than
   replacing it. Kept short because it sits in a row that already wraps on a
   laptop, and distinct from dispute.nav, which is the same person's own
   disputes rather than everybody's. */
const frNav = { adminDisputes: "File admin" };
const enNav = { adminDisputes: "Admin queue" };

i18n.addResourceBundle("fr", "translation", { admin: fr, nav: frNav }, true, true);
i18n.addResourceBundle("en", "translation", { admin: en, nav: enNav }, true, true);

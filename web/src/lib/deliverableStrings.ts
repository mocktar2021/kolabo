/* Copy for the deliverables panel on the contract page, registered as a
   resource bundle so the 40 KB i18n.ts stays focused on the core app copy —
   the same arrangement the cart, the open board, the disputes queue, the admin
   console, the notifications bell and the two money screens use.

   THE CONSEQUENCE STRINGS ARE THE ONES THAT MATTER HERE. Approving releases
   the escrow, and a brand that learns that afterwards has paid for work it
   meant to send back. So `approveWarning` is said next to the button and not
   in a tooltip, the same call the dispute form makes with its own
   consequence line. */
import i18n from "../i18n";

const fr = {
  title: "Livrables",
  sub: "Le travail remis pour ce contrat, et votre réponse.",

  // Empty states, per side. Each says what happens next rather than just
  // reporting an absence.
  emptyCreator: "Vous n'avez encore rien remis pour ce contrat.",
  emptyBrand: "Le créateur n'a encore rien remis.",
  emptyBrandHint: "Vous serez prévenu dès qu'un livrable est soumis. C'est ici que vous le validez et libérez le paiement.",
  notFunded: "Le travail se remet une fois le paiement bloqué en séquestre.",

  // The submit form.
  submitTitle: "Remettre le travail",
  linkLabel: "Lien vers la publication",
  linkPlaceholder: "https://instagram.com/p/…",
  noteLabel: "Note (facultatif)",
  notePlaceholder: "Ce que vous avez publié, où, et quand.",
  needSomething: "Ajoutez le lien de la publication, un fichier, ou les deux.",
  submit: "Envoyer pour validation",
  submitHint: "La marque est prévenue et dispose de {{n}} jours pour répondre. Sans réponse de sa part, le séquestre est libéré automatiquement.",
  withdraw: "Retirer",
  withdrawHint: "Tant que la marque n'a pas répondu, vous pouvez retirer ce livrable et en renvoyer un autre.",

  // The brand's two answers.
  reviewTitle: "Valider le travail",
  approve: "Valider et payer",
  approveWarning: "La validation libère le séquestre : le paiement part immédiatement au créateur, commission déduite. C'est définitif.",
  requestChanges: "Demander des modifications",
  reviewNoteLabel: "Ce qui doit changer",
  reviewNotePlaceholder: "Dites précisément ce qui ne va pas, pour que le créateur puisse le corriger.",
  reviewNoteRequired: "Indiquez ce qui doit changer.",
  sendRequest: "Envoyer la demande",
  cancel: "Annuler",
  changesKeepEscrow: "Demander des modifications ne débloque pas l'argent et n'ouvre pas de litige : le séquestre reste bloqué et le créateur peut renvoyer son travail.",

  // Rows.
  awaitingReview: "En attente de votre validation",
  awaitingReviewCreator: "En attente de la validation de la marque",
  viewPost: "Voir la publication",
  reviewNoteShown: "Modifications demandées :",
  attachments: "Pièces jointes",
  history: "Historique",

  status_submitted: "Soumis",
  status_approved: "Validé",
  status_changes_requested: "Modifications demandées",
  status_withdrawn: "Retiré"
};

const en = {
  title: "Deliverables",
  sub: "The work handed in for this contract, and your answer to it.",

  emptyCreator: "You have not submitted anything for this contract yet.",
  emptyBrand: "The creator has not submitted anything yet.",
  emptyBrandHint: "You will be notified as soon as work is submitted. You approve it and release the payment here.",
  notFunded: "Work is submitted once the payment is held in escrow.",

  submitTitle: "Submit the work",
  linkLabel: "Link to the published post",
  linkPlaceholder: "https://instagram.com/p/…",
  noteLabel: "Note (optional)",
  notePlaceholder: "What you published, where, and when.",
  needSomething: "Add the link to the post, a file, or both.",
  submit: "Send for review",
  submitHint: "The brand is notified and has {{n}} days to answer. If they do not, the escrow releases automatically.",
  withdraw: "Withdraw",
  withdrawHint: "While the brand has not answered, you can withdraw this and send a different one.",

  reviewTitle: "Review the work",
  approve: "Approve and pay",
  approveWarning: "Approving releases the escrow: the payment goes to the creator immediately, commission deducted. This cannot be undone.",
  requestChanges: "Request changes",
  reviewNoteLabel: "What needs to change",
  reviewNotePlaceholder: "Say exactly what is wrong, so the creator can fix it.",
  reviewNoteRequired: "Say what needs to change.",
  sendRequest: "Send the request",
  cancel: "Cancel",
  changesKeepEscrow: "Requesting changes does not move the money and does not open a dispute: the escrow stays held and the creator can submit again.",

  awaitingReview: "Waiting for your review",
  awaitingReviewCreator: "Waiting for the brand to review",
  viewPost: "View the post",
  reviewNoteShown: "Changes requested:",
  attachments: "Attachments",
  history: "History",

  status_submitted: "Submitted",
  status_approved: "Approved",
  status_changes_requested: "Changes requested",
  status_withdrawn: "Withdrawn"
};

i18n.addResourceBundle("fr", "translation", { deliv: fr }, true, true);
i18n.addResourceBundle("en", "translation", { deliv: en }, true, true);

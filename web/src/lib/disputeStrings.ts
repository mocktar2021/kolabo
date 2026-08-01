/* Dispute strings, registered as a resource bundle so the main i18n file
   stays focused on the core app copy — the same arrangement the onboarding
   wizard, the marketing pages, the cart and messaging use. */
import i18n from "../i18n";

const fr = {
  /* "Signaler un problème" rather than "Ouvrir un litige". The person
     clicking this has a problem; they do not yet have a litige, and calling
     it one before they have described it makes the first, cheapest step —
     saying what went wrong — feel like an escalation they have to be sure
     about. The word litige is used everywhere after the form. */
  open: "Signaler un problème",
  formTitle: "Signaler un problème",
  reason: "Motif",
  reason_not_delivered: "Contenu non livré",
  reason_late: "Livraison en retard",
  reason_wrong_content: "Contenu non conforme",
  reason_quality: "Qualité insuffisante",
  reason_payment_issue: "Problème de paiement",
  reason_other: "Autre",
  statement: "Ce qui s'est passé",
  statementPlaceholder: "Les dates, ce qui était convenu, ce qui a été livré.",
  counter: "{{n}} / {{max}} caractères",
  statementTooShort: "Décrivez le problème en {{n}} caractères au minimum.",
  evidence: "Captures d'écran (optionnel)",
  evidenceAdd: "Ajouter des images",
  evidenceRemove: "Retirer",
  evidenceUploading: "Envoi {{done}} / {{total}}",
  evidenceMax: "{{n}} images au maximum.",
  evidenceFailed: "L'envoi de l'image a échoué.",
  /* THE PRODUCT RULE, said before the click and not after it. Raising a
     dispute freezes the money for both sides and hands the other party an
     exclusive 72 h window — it is not a complaint form, and somebody who
     learns that afterwards has already frozen a payout they were about to
     receive. The two consequences are the two things they cannot undo. */
  consequence:
    "Les fonds restent bloqués pendant l'examen. L'autre partie a 72 h pour répondre.",
  submit: "Ouvrir le litige",
  cancel: "Annuler",
  existing: "Un litige est ouvert sur ce séquestre.",
  view: "Voir le litige",
  status_awaiting_response: "En attente de réponse",
  status_awaiting_admin: "En examen",
  status_resolved: "Résolu",
  status_withdrawn: "Retiré",

  /* The list and the case. */
  nav: "Litiges",
  navAria: "Litiges, {{n}} en attente de votre réponse",
  listTitle: "Mes litiges",
  listSub: "Les litiges sur vos séquestres, du plus récent au plus ancien.",
  listEmpty: "Vous n'avez aucun litige.",
  counterparty: "Partie adverse",
  unknownParty: "Autre partie",
  amount: "Montant",
  openedOn: "Ouvert le {{date}}",
  /* The countdown belongs to the party who has to answer, so it is only
     shown while the window is still open. Past it the case is queued and the
     clock has stopped meaning anything. */
  respondInHours: "Réponse attendue sous {{n}} h",
  respondInMinutes: "Réponse attendue sous {{n}} min",
  respondOverdue: "Délai de réponse dépassé",
  notFound: "Litige introuvable.",
  back: "Retour aux litiges",
  opening: "Déclaration initiale",
  thread: "Échanges",
  noMessages: "Aucun message pour l'instant.",
  you: "Vous",
  composerPlaceholder: "Écrivez votre réponse",
  send: "Envoyer",
  withdraw: "Retirer le litige",
  /* Where the money goes, said before the click. Withdrawing is not
     abandoning the escrow: it goes back to held and back on its normal
     release schedule, which is the fact that makes settling amicably safe. */
  withdrawExplain: "Les fonds repartent en séquestre normal.",
  withdrawYes: "Confirmer le retrait",
  withdrawNo: "Annuler",
  outcome: "Décision",
  outcomeReleased: "Libéré au créateur",
  outcomeRefunded: "Remboursé à la marque",
  outcomeNote: "Note de l'équipe Kolabo"
};

const en = {
  /* "Report a problem" rather than "Open a dispute", for the reason the
     French copy spells out: the word dispute belongs after the form, not on
     the button that leads to it. */
  open: "Report a problem",
  formTitle: "Report a problem",
  reason: "Reason",
  reason_not_delivered: "Content not delivered",
  reason_late: "Delivered late",
  reason_wrong_content: "Content does not match",
  reason_quality: "Quality is not good enough",
  reason_payment_issue: "Payment issue",
  reason_other: "Other",
  statement: "What happened",
  statementPlaceholder: "The dates, what was agreed, what was delivered.",
  counter: "{{n}} / {{max}} characters",
  statementTooShort: "Describe the problem in at least {{n}} characters.",
  evidence: "Screenshots (optional)",
  evidenceAdd: "Add images",
  evidenceRemove: "Remove",
  evidenceUploading: "Uploading {{done}} / {{total}}",
  evidenceMax: "At most {{n}} images.",
  evidenceFailed: "The image could not be uploaded.",
  consequence:
    "The funds stay frozen while the case is reviewed. The other party has 72 h to answer.",
  submit: "Open the dispute",
  cancel: "Cancel",
  existing: "A dispute is open on this escrow.",
  view: "View the dispute",
  status_awaiting_response: "Awaiting a response",
  status_awaiting_admin: "Under review",
  status_resolved: "Resolved",
  status_withdrawn: "Withdrawn",

  /* The list and the case. */
  nav: "Disputes",
  navAria: "Disputes, {{n}} awaiting your answer",
  listTitle: "My disputes",
  listSub: "Disputes on your escrows, newest first.",
  listEmpty: "You have no disputes.",
  counterparty: "Counterparty",
  unknownParty: "Other party",
  amount: "Amount",
  openedOn: "Opened on {{date}}",
  respondInHours: "An answer is due within {{n}} h",
  respondInMinutes: "An answer is due within {{n}} min",
  respondOverdue: "The response window has closed",
  notFound: "Dispute not found.",
  back: "Back to disputes",
  opening: "Opening statement",
  thread: "Messages",
  noMessages: "No messages yet.",
  you: "You",
  composerPlaceholder: "Write your reply",
  send: "Send",
  withdraw: "Withdraw the dispute",
  withdrawExplain: "The funds go back into normal escrow.",
  withdrawYes: "Confirm the withdrawal",
  withdrawNo: "Cancel",
  outcome: "Decision",
  outcomeReleased: "Released to the creator",
  outcomeRefunded: "Refunded to the brand",
  outcomeNote: "Note from the Kolabo team"
};

i18n.addResourceBundle("fr", "translation", { dispute: fr }, true, true);
i18n.addResourceBundle("en", "translation", { dispute: en }, true, true);

/* Taking back an offer nobody has answered yet: the three places the product
   lets somebody undo, in one bundle so the 40 KB i18n.ts stays focused on the
   core app copy — the same arrangement the cart, the disputes queue, the
   account settings and the earnings screen use.

   ONE NAMESPACE FOR THREE SCREENS, deliberately, because they are one rule
   read from three places: you may retract what you offered until the other
   side has spent effort or money on it. The backend keeps the campaign half
   in campaigns/withdrawals.py and the contract half in
   contracts/cancellation.py; the wording has to agree across both, and
   sentences that live in one file cannot quietly drift apart.

   WITHDRAWN IS NOT DECLINED, and the copy says so out loud. Declining records
   that somebody said no; withdrawing records that an offer was taken off the
   table before anyone answered. Putting a refusal on a record that never made
   one is the kind of small dishonesty that makes a reputation system
   worthless.

   THE REFUSAL SENTENCES ARE LEAVING THIS FILE, one module at a time. They were
   chosen by HTTP status — a page caught a 400 and picked a key — which caps a
   screen at one localised message per status and forces one sentence to cover
   several rules. contractFunded and contractRefused are already gone: the
   contracts module now sends a code per rule, so apiError.contract_* says
   which of "already cancelled", "already signed" and "money in escrow" it
   actually was. invitationRefused and proposalRefused are still here and go
   the same way when campaigns is converted. What stays for good is the copy
   below that is not a refusal: the buttons, the explanations and the
   confirmations, which are the product's own words rather than the API's. */
import i18n from "../i18n";

const fr = {
  // ---- The brand takes an invitation back (CampaignDetail) ----
  invitationWithdraw: "Retirer l'invitation",
  invitationConfirm: "Retirer cette invitation ? Le créateur en sera informé et le brief quittera sa liste. Rien n'est effacé : l'invitation passe au statut « retirée », qui n'est pas un refus. Personne n'a dit non ici.",
  invitationYes: "Retirer l'invitation",
  invitationNo: "La garder",

  // ---- The creator takes their own offer back (MyInvitations) ----
  proposalWithdraw: "Retirer ma proposition",
  proposalConfirm: "Retirer cette proposition ? La marque en sera informée et vos conditions quitteront la table. La version précédente ne revient pas : elle avait été remplacée par celle-ci, et la plateforme ne fait pas d'offre à votre place. Vous pourrez toujours en envoyer une nouvelle.",
  proposalYes: "Retirer ma proposition",
  proposalNo: "La laisser",

  // ---- Either party calls off an unsigned contract (ContractPage) ----
  contractTitle: "Annuler ce contrat",
  contractExplain: "Tant que les deux signatures ne sont pas là et qu'aucun argent n'est bloqué, chacune des deux parties peut mettre fin à ce contrat. Le dire ici vaut mieux que de ne plus répondre : un contrat à moitié signé reste dans la liste de l'autre indéfiniment.",
  contractCancel: "Annuler le contrat",
  contractConfirm: "Annuler ce contrat ? L'autre partie en sera informée et le contrat passera au statut « annulé ». Il n'y a rien à rembourser (aucun argent n'a été bloqué), mais l'accord est terminé : pour retravailler ensemble, il faudra repartir d'une nouvelle proposition.",
  contractYes: "Annuler le contrat",
  contractNo: "Le garder"
  /* Le refus lui-même vit désormais dans apiError.contract_* : voir
     lib/errorMessages.ts et le commentaire en tête de ce fichier. */
};

const en = {
  invitationWithdraw: "Withdraw the invitation",
  invitationConfirm: "Withdraw this invitation? The creator is told, and the brief leaves their list. Nothing is erased: the invitation moves to \"withdrawn\", which is not a refusal. Nobody said no here.",
  invitationYes: "Withdraw the invitation",
  invitationNo: "Keep it",

  proposalWithdraw: "Withdraw my proposal",
  proposalConfirm: "Withdraw this proposal? The brand is told and your terms leave the table. The previous version does not come back: it was superseded by this one, and the platform does not make an offer on your behalf. You can always send a new one.",
  proposalYes: "Withdraw my proposal",
  proposalNo: "Leave it",

  contractTitle: "Cancel this contract",
  contractExplain: "While both signatures are not in and no money is held, either party can end this contract. Saying so here beats going quiet: a half-signed contract sits in the other person's list indefinitely.",
  contractCancel: "Cancel the contract",
  contractConfirm: "Cancel this contract? The other party is told and the contract moves to \"cancelled\". There is nothing to refund (no money was ever held), but the agreement is over: working together again means starting from a new proposal.",
  contractYes: "Cancel the contract",
  contractNo: "Keep it"
};

i18n.addResourceBundle("fr", "translation", { undo: fr }, true, true);
i18n.addResourceBundle("en", "translation", { undo: en }, true, true);

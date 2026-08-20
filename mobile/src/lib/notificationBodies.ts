/* The localised NOTIFICATION BODIES, as data and nothing else — ported
   verbatim from web/src/lib/notificationBodies.ts, which is the file the
   backend-parity test reads. Every key a backend notify() writes exists in
   BOTH maps; the web test enforces that, and this mirror must be updated in
   the same commit as the web one whenever a key lands.

   HOW A BODY GETS HERE. The backend stores a {key, ...values} on the
   notification row; the client renders notif.body.<key> with the values
   interpolated (notificationBody in lib/notifications.ts). A row with no
   params — an old one, or a call site not migrated yet — falls back to the
   English `message` the backend also emails, so a missing key is never a
   blank row. */

export const body_fr = {
  escrow_funded_creator: "Des fonds sont bloqués en séquestre pour votre collaboration.",
  escrow_funded_brand: "Votre paiement est bloqué en séquestre.",
  escrow_released_creator: "Séquestre libéré, votre paiement est en route.",
  escrow_released_brand: "Séquestre libéré au créateur.",
  delivery_overdue_creator: "La date de livraison est passée et rien n'a été soumis. Le séquestre sera remboursé à la marque dans {{days}} jours si vous n'envoyez pas votre livrable.",
  delivery_overdue_brand: "La date de livraison est passée et rien n'a été soumis. Votre séquestre vous sera remboursé automatiquement dans {{days}} jours si rien n'arrive.",
  escrow_refunded_brand: "Rien n'a été livré : votre séquestre vous a été intégralement remboursé.",
  escrow_refunded_creator: "Le délai de livraison s'est écoulé sans aucun envoi : le séquestre a été remboursé à la marque.",
  dispute_opened_other: "Un litige a été ouvert sur votre séquestre. Vous avez {{hours}} h pour répondre ou le résoudre avant qu'il ne soit transmis à l'équipe Kolabo.",
  dispute_opened_self: "Votre litige a été ouvert et le séquestre est gelé. L'autre partie a {{hours}} h pour répondre.",
  dispute_escalated_both: "Les deux parties ont répondu ; le litige a été transmis à l'équipe Kolabo pour décision.",
  dispute_escalated_stale: "Le délai de réponse de votre séquestre en litige est écoulé. L'équipe Kolabo va l'examiner et trancher.",
  dispute_reply: "L'autre partie a répondu sur votre séquestre en litige.",
  dispute_withdrawn: "Le litige a été retiré. Le séquestre est de nouveau bloqué et suit son calendrier de libération normal.",
  dispute_resolved_creator: "Votre litige a été tranché : {{payout}} {{currency}} vous sont versés et {{refunded}} {{currency}} ont été remboursés à la marque.",
  dispute_resolved_brand: "Votre litige a été tranché : {{refunded}} {{currency}} vous sont remboursés et {{released}} {{currency}} ont été versés au créateur.",
  deliverable_submitted: "Un livrable a été soumis pour validation pour {{campaign}}.",
  deliverable_submitted_generic: "Un livrable a été soumis pour validation.",
  deliverable_changes_requested: "La marque demande des modifications sur le travail que vous avez soumis.",
  contract_ready: "Un contrat est prêt à signer pour {{campaign}}.",
  contract_signed: "Votre contrat est entièrement signé.",
  contract_cancelled: "Un contrat que vous n'aviez pas fini de signer a été annulé par l'autre partie.",
  message_campaign: "Nouveau message à propos de la campagne {{campaign}}.",
  message_generic: "Vous avez un nouveau message.",

  order_accepted: "Votre commande {{campaign}} a été acceptée. Le contrat est prêt à signer.",
  order_declined: "Votre commande {{campaign}} a été refusée. Vous n'avez pas été débité.",
  order_expired_creator: "La commande {{campaign}} a expiré faute de réponse dans le délai.",
  order_expired_brand: "Votre commande {{campaign}} a expiré sans réponse. Vous n'avez pas été débité.",
  campaign_cancelled: "La campagne {{campaign}} a été annulée par l'entreprise.",
  invitation_withdrawn: "L'invitation à {{campaign}} a été retirée par l'entreprise.",
  proposal_withdrawn: "Un créateur a retiré sa proposition pour {{campaign}}.",
  brief_filled: "Ce brief a été pourvu : votre proposition est maintenant close.",
  proposal_rejected: "Votre proposition n'a pas été retenue.",

  invitation_received: "Vous avez été invité(e) à la campagne {{campaign}}.",
  order_custom_offer: "Une marque vous a envoyé une offre personnalisée : {{title}}. Vous avez {{hours}} h pour accepter ou refuser.",
  order_package: "Une marque a commandé votre pack {{title}}. Vous avez {{hours}} h pour accepter ou refuser.",
  order_cart: "Une marque vous a commandé {{title}}. Vous avez {{hours}} h pour accepter ou refuser.",
  brief_application: "{{name}} a postulé à votre brief ouvert {{campaign}}.",
  brief_application_anon: "Un créateur a postulé à votre brief ouvert {{campaign}}.",
  proposal_submitted: "{{name}} a envoyé une proposition pour {{campaign}}.",
  proposal_submitted_anon: "Un créateur a envoyé une proposition pour {{campaign}}.",
  proposal_countered: "{{name}} a fait une contre-proposition pour {{campaign}}.",
  proposal_countered_anon: "Une entreprise a fait une contre-proposition pour {{campaign}}.",
  proposal_replied: "{{name}} a répondu à votre proposition pour {{campaign}}.",
  proposal_replied_anon: "Une entreprise a répondu à votre proposition pour {{campaign}}.",

  verification_document_approved: "Votre document {{document}} a été approuvé.",
  verification_document_rejected: "Votre document {{document}} a été refusé : {{reason}}",
  social_verified: "Votre compte {{platform}} @{{handle}} a été vérifié.",
  social_rejected: "Votre compte {{platform}} @{{handle}} a été refusé.",
  social_rejected_reason: "Votre compte {{platform}} @{{handle}} a été refusé : {{reason}}",
  report_reviewed: "Votre signalement a été examiné et le dossier est clos.",
  password_changed: "Votre mot de passe Kolabo a été modifié. Si ce n'était pas vous, contactez le support immédiatement.",

  /* Les deux moitiés d'un versement : la première demande quelque chose au
     créateur, la seconde n'est jamais qu'une bonne nouvelle. */
  payout_method_missing: "Ajoutez vos coordonnées Mobile Money pour recevoir vos paiements.",
  payout_sent: "Votre paiement a été envoyé sur votre portefeuille Mobile Money.",
};

export const body_en: typeof body_fr = {
  escrow_funded_creator: "Funds are held in escrow for your collaboration.",
  escrow_funded_brand: "Your payment is held in escrow.",
  escrow_released_creator: "Escrow released, your payout is on the way.",
  escrow_released_brand: "Escrow released to the creator.",
  delivery_overdue_creator: "The delivery date has passed with nothing submitted. The escrow is refunded to the brand in {{days}} days unless you submit your work.",
  delivery_overdue_brand: "The delivery date has passed with nothing submitted. Your escrow is refunded to you automatically in {{days}} days if nothing arrives.",
  escrow_refunded_brand: "Nothing was delivered, so your escrow has been refunded to you in full.",
  escrow_refunded_creator: "The delivery window closed with nothing submitted, so the escrow was refunded to the brand.",
  dispute_opened_other: "A dispute was opened on your escrow. You have {{hours}} hours to answer or resolve it before it goes to the Kolabo team.",
  dispute_opened_self: "Your dispute was opened and the escrow is frozen. The other party has {{hours}} hours to answer.",
  dispute_escalated_both: "Both parties have answered the dispute, so it has gone to the Kolabo team for a decision.",
  dispute_escalated_stale: "The response window on your disputed escrow has closed. The Kolabo team will now review it and decide.",
  dispute_reply: "The other party replied on your disputed escrow.",
  dispute_withdrawn: "The dispute was withdrawn. The escrow is held again and back on its normal release schedule.",
  dispute_resolved_creator: "Your dispute was decided: {{payout}} {{currency}} is on its way to you and {{refunded}} {{currency}} was refunded to the brand.",
  dispute_resolved_brand: "Your dispute was decided: {{refunded}} {{currency}} is being refunded to you and {{released}} {{currency}} was released to the creator.",
  deliverable_submitted: "Work was submitted for review on {{campaign}}.",
  deliverable_submitted_generic: "Work was submitted for review.",
  deliverable_changes_requested: "The brand asked for changes to the work you submitted.",
  contract_ready: "A contract is ready to sign for {{campaign}}.",
  contract_signed: "Your contract is fully signed.",
  contract_cancelled: "A contract you had not finished signing was cancelled by the other party.",
  message_campaign: "New message about the campaign {{campaign}}.",
  message_generic: "You have a new message.",

  order_accepted: "Your order for {{campaign}} was accepted. The contract is ready to sign.",
  order_declined: "Your order for {{campaign}} was declined. You were not charged.",
  order_expired_creator: "The order for {{campaign}} expired because it was not answered in time.",
  order_expired_brand: "Your order for {{campaign}} expired without an answer. You were not charged.",
  campaign_cancelled: "The campaign {{campaign}} was cancelled by the business.",
  invitation_withdrawn: "The invitation to {{campaign}} was withdrawn by the business.",
  proposal_withdrawn: "A creator withdrew their proposal for {{campaign}}.",
  brief_filled: "This brief has been filled, so your proposal is now closed.",
  proposal_rejected: "Your proposal was not selected.",

  invitation_received: "You were invited to the campaign {{campaign}}.",
  order_custom_offer: "A brand sent you a custom offer: {{title}}. You have {{hours}} hours to accept or decline.",
  order_package: "A brand ordered your package {{title}}. You have {{hours}} hours to accept or decline.",
  order_cart: "A brand ordered {{title}} from you. You have {{hours}} hours to accept or decline.",
  brief_application: "{{name}} applied to your open brief {{campaign}}.",
  brief_application_anon: "A creator applied to your open brief {{campaign}}.",
  proposal_submitted: "{{name}} sent a proposal for {{campaign}}.",
  proposal_submitted_anon: "A creator sent a proposal for {{campaign}}.",
  proposal_countered: "{{name}} countered your proposal for {{campaign}}.",
  proposal_countered_anon: "A business countered your proposal for {{campaign}}.",
  proposal_replied: "{{name}} replied to your proposal for {{campaign}}.",
  proposal_replied_anon: "A business replied to your proposal for {{campaign}}.",

  verification_document_approved: "Your {{document}} document was approved.",
  verification_document_rejected: "Your {{document}} document was rejected: {{reason}}",
  social_verified: "Your {{platform}} account @{{handle}} was verified.",
  social_rejected: "Your {{platform}} account @{{handle}} was rejected.",
  social_rejected_reason: "Your {{platform}} account @{{handle}} was rejected: {{reason}}",
  report_reviewed: "Your report has been reviewed and the case is closed.",
  password_changed: "Your Kolabo password was changed. If this was not you, contact support immediately.",

  /* The two halves of a payout, and they are not interchangeable: the first
     asks the creator for something and the second never does. */
  payout_method_missing: "Add your Mobile Money details so we can send you your payments.",
  payout_sent: "Your payment has been sent to your Mobile Money wallet.",
};

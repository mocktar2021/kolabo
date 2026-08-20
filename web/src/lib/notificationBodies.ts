/* The localised NOTIFICATION BODIES, as data and nothing else.

   Split out of notificationStrings.ts, which imports i18n and calls
   addResourceBundle at module load. That side effect is right for a strings
   file and wrong for a test subject: a test that wants to compare the two
   language maps should not have to boot i18next to do it. This module imports
   NOTHING, so notificationBodies.test.ts can hold both maps side by side and
   check they agree — see that file for what "agree" is made to mean.

   HOW A BODY GETS HERE. The backend stores a {key, ...values} on the
   notification row; the client renders notif.body.<key> with the values
   interpolated (notificationBody in notifications.ts). A row with no params —
   an old one, or a call site not migrated yet — falls back to the English
   `message` the backend also emails, so a missing key is never a blank row.
   Every key a backend notify() writes must exist in BOTH maps below; the test
   reads the backend sources and enforces exactly that. */

export const body_fr = {
  escrow_funded_creator: "Des fonds sont bloqués en séquestre pour votre collaboration.",
  escrow_funded_brand: "Votre paiement est bloqué en séquestre.",
  escrow_released_creator: "Séquestre libéré, votre paiement est en route.",
  escrow_released_brand: "Séquestre libéré au créateur.",
  /* Les deux bouts d'un versement Mobile Money : pas de portefeuille au
     dossier, donc rien ne peut partir, puis la confirmation une fois parti.
     Deux clés plutôt qu'une : la première demande une action au créateur, la
     seconde n'est jamais qu'une bonne nouvelle. */
  payout_method_missing: "Ajoutez vos coordonnées Mobile Money pour recevoir vos paiements.",
  payout_sent: "Votre paiement a été envoyé sur votre portefeuille Mobile Money.",
  /* Non-delivery: the delivery date passed with nothing submitted. Two
     stages, so both parties hear the warning before any money moves — see
     payments.service.run_non_delivery_refunds. */
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
  /* L'autre fin d'un brief : celui-ci a abouti, avec quelqu'un d'autre. Le ton
     est neutre à dessein — personne n'a refusé la proposition du créateur, le
     brief est simplement pourvu — et la phrase ne nomme pas la campagne, comme
     l'anglaise, parce que le lien ouvre déjà ses invitations. */
  brief_filled: "Ce brief a été pourvu : votre proposition est maintenant close.",
  /* La troisième façon dont une proposition se termine, et la seule où
     quelqu'un a décidé : la marque a dit non. Sans reproche et sans motif —
     il n'y a pas de champ pour en donner un — et sans nommer la campagne,
     comme brief_filled, parce que le lien ouvre déjà ses invitations. */
  proposal_rejected: "Votre proposition n'a pas été retenue.",

  invitation_received: "Vous avez été invité(e) à la campagne {{campaign}}.",
  order_custom_offer: "Une marque vous a envoyé une offre personnalisée : {{title}}. Vous avez {{hours}} h pour accepter ou refuser.",
  order_package: "Une marque a commandé votre pack {{title}}. Vous avez {{hours}} h pour accepter ou refuser.",
  order_cart: "Une marque vous a commandé {{title}}. Vous avez {{hours}} h pour accepter ou refuser.",
  /* Each of these has an _anon twin for the case where the person has no
     display name or the company has no name. The backend picks the twin
     rather than interpolating its English placeholder ("A creator"), which
     would otherwise sit in the middle of a French sentence — see
     campaigns.service._named. */
  brief_application: "{{name}} a postulé à votre brief ouvert {{campaign}}.",
  brief_application_anon: "Un créateur a postulé à votre brief ouvert {{campaign}}.",
  proposal_submitted: "{{name}} a envoyé une proposition pour {{campaign}}.",
  proposal_submitted_anon: "Un créateur a envoyé une proposition pour {{campaign}}.",
  proposal_countered: "{{name}} a fait une contre-proposition pour {{campaign}}.",
  proposal_countered_anon: "Une entreprise a fait une contre-proposition pour {{campaign}}.",
  proposal_replied: "{{name}} a répondu à votre proposition pour {{campaign}}.",
  proposal_replied_anon: "Une entreprise a répondu à votre proposition pour {{campaign}}.",

  /* {{document}} is the stored doc_type with its underscores removed
     ("business registration"), so it arrives in English. Naming WHICH document
     matters more than the seam does — a creator with two in the queue cannot
     act on "your document was rejected" — so it stays until the doc types get
     keys of their own. Noted rather than quietly dropped. */
  verification_document_approved: "Votre document {{document}} a été approuvé.",
  verification_document_rejected: "Votre document {{document}} a été refusé : {{reason}}",
  social_verified: "Votre compte {{platform}} @{{handle}} a été vérifié.",
  social_rejected: "Votre compte {{platform}} @{{handle}} a été refusé.",
  social_rejected_reason: "Votre compte {{platform}} @{{handle}} a été refusé : {{reason}}",
  /* No target type and no decision. The type is a database enum that would
     land as an English word mid-sentence, and the decision is deliberately
     never disclosed — see trust_safety.service.resolve_report. */
  report_reviewed: "Votre signalement a été examiné et le dossier est clos.",
  password_changed: "Votre mot de passe Kolabo a été modifié. Si ce n'était pas vous, contactez le support immédiatement."
};

export const body_en = {
  escrow_funded_creator: "Funds are held in escrow for your collaboration.",
  escrow_funded_brand: "Your payment is held in escrow.",
  escrow_released_creator: "Escrow released, your payout is on the way.",
  escrow_released_brand: "Escrow released to the creator.",
  /* The two ends of a Mobile Money payout: no wallet on file, so nothing can
     leave, and the confirmation once it has. Two keys rather than one because
     the first asks the creator for something and the second never does. */
  payout_method_missing: "Add your Mobile Money details so we can send you your payments.",
  payout_sent: "Your payment has been sent to your Mobile Money wallet.",
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
  /* The other way a brief ends: it worked, with somebody else. Neutral on
     purpose — nobody rejected this creator, the brief is simply filled — and
     it names no campaign, so the two languages ask for the same (empty) set of
     interpolation values. */
  brief_filled: "This brief has been filled, so your proposal is now closed.",
  /* The third way a proposal ends, and the only one somebody chose: the
     brand said no. No blame and no reason — there is no field to put one
     in — and no campaign named, like brief_filled, so the two languages ask
     for the same (empty) set of interpolation values. */
  proposal_rejected: "Your proposal was not selected.",

  invitation_received: "You were invited to the campaign {{campaign}}.",
  order_custom_offer: "A brand sent you a custom offer: {{title}}. You have {{hours}} hours to accept or decline.",
  order_package: "A brand ordered your package {{title}}. You have {{hours}} hours to accept or decline.",
  order_cart: "A brand ordered {{title}} from you. You have {{hours}} hours to accept or decline.",
  /* The _anon twins exist for the French side's benefit (see the note there),
     but they are written out in English too rather than reusing one template
     with an English default, so the two maps stay key-for-key identical and
     the parity test keeps meaning something. */
  brief_application: "{{name}} applied to your open brief {{campaign}}.",
  brief_application_anon: "A creator applied to your open brief {{campaign}}.",
  proposal_submitted: "{{name}} sent a proposal for {{campaign}}.",
  proposal_submitted_anon: "A creator sent a proposal for {{campaign}}.",
  proposal_countered: "{{name}} countered your proposal for {{campaign}}.",
  proposal_countered_anon: "A business countered your proposal for {{campaign}}.",
  proposal_replied: "{{name}} replied to your proposal for {{campaign}}.",
  proposal_replied_anon: "A business replied to your proposal for {{campaign}}.",

  /* See the note on the French side: {{document}} is the stored doc_type with
     its underscores removed, so it is the same English words in both. */
  verification_document_approved: "Your {{document}} document was approved.",
  verification_document_rejected: "Your {{document}} document was rejected: {{reason}}",
  social_verified: "Your {{platform}} account @{{handle}} was verified.",
  social_rejected: "Your {{platform}} account @{{handle}} was rejected.",
  social_rejected_reason: "Your {{platform}} account @{{handle}} was rejected: {{reason}}",
  /* Drops the target type the stored `message` carries, so that the two
     languages say the same thing; the decision is disclosed in neither — see
     trust_safety.service.resolve_report. */
  report_reviewed: "Your report has been reviewed and the case is closed.",
  password_changed: "Your Kolabo password was changed. If this was not you, contact support immediately."
};

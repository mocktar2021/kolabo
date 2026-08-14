/* What the API's refusals say, in French and in English — the mobile port of
   web/src/lib/errorMessages.ts.

   The backend answers a refusal with an English `detail` sentence and a stable
   `code` (backend/app/core/errors.py). This holds one sentence per code per
   language; errorText() picks the right one. No imports, so it can be unit
   tested without booting i18next, and i18n.ts folds these two maps in under the
   `apiError` namespace.

   PARITY: the sentences below are copied verbatim from the web catalog so a
   refusal reads identically on both clients. This is the auth-flow subset —
   the rest of the codes get ported as the matching screens land, exactly the
   way the backend migration itself proceeded one module at a time. A code with
   no entry here falls through to the backend's English `message`, which is what
   the app showed before any of this existed. */

export const GENERIC_KEY = "apiError.generic";

export const error_fr: Record<string, string> = {
  generic: "Une erreur est survenue. Réessayez dans un instant.",

  /* Pannes de transport : l'API n'a jamais répondu. Ce ne sont pas des codes
     du backend — api.ts les fabrique — mais ils passent par le même chemin,
     pour que l'écran n'ait rien de particulier à faire. */
  network_unreachable: "Impossible de joindre Kolabo. Vérifiez votre connexion et réessayez.",
  network_bad_response: "Réponse inattendue du serveur. Sur un Wi-Fi public, une page de connexion intercepte peut-être la connexion.",

  auth_user_not_found: "Utilisateur introuvable.",
  auth_referral_code_failed: "Impossible de générer un code de parrainage. Réessayez.",
  auth_role_unknown: "Le rôle doit être l'un des suivants : {{roles}}",
  auth_country_unavailable: "Kolabo n'est pas encore disponible dans ce pays.",
  auth_phone_taken: "Ce numéro est déjà utilisé par un autre compte.",
  auth_no_pending_verification: "Aucune vérification en attente pour ce numéro.",
  auth_code_expired: "Ce code de vérification a expiré. Demandez-en un nouveau.",
  auth_code_invalid: "Code de vérification invalide.",
  auth_bad_credentials: "Numéro ou mot de passe incorrect.",
  auth_not_verified: "Ce compte n'est pas encore vérifié. Confirmez le code envoyé par SMS.",
  auth_password_incorrect: "Mot de passe actuel incorrect.",
  auth_account_has_history:
    "Ce compte a un historique de transactions et ne peut pas être fermé ici. Contactez le support.",
  auth_token_missing: "Vous n'êtes plus connecté(e). Reconnectez-vous.",
  auth_token_invalid: "Votre session a expiré. Reconnectez-vous.",
  auth_account_nothing_to_change: "Indiquez un nouveau numéro, un nouveau mot de passe, ou les deux.",
  auth_reset_too_many: "Trop de demandes de réinitialisation. Réessayez plus tard.",
  auth_reset_code_invalid: "Ce code de réinitialisation est invalide ou expiré.",

  profile_not_found: "Profil introuvable.",
  profile_under_age: "Vous devez avoir au moins {{min}} ans pour créer un profil de créateur.",
  profile_platform_unsupported: "Cette plateforme n'est pas prise en charge.",
  profile_social_method_unknown: "La méthode de connexion doit être « oauth » ou « manual ».",
  profile_proof_url_required: "Une connexion manuelle demande un lien de preuve.",
  profile_social_not_found: "Compte social introuvable.",
  profile_social_not_yours: "Ce compte social n'est pas le vôtre.",
  profile_duration_pair: "La durée et son unité vont ensemble : indiquez les deux, ou aucun des deux.",
  package_not_found: "Pack introuvable.",
  profile_package_not_yours: "Ce pack n'est pas le vôtre.",
  deliverable_not_on_platform: "« {{type}} » n'existe pas sur {{platform}}. Possibilités : {{allowed}}",
  price_below_floor: "Le prix minimum en {{currency}} est de {{floor}}.",
  profile_image_type_unsupported: "Seules les images JPEG, PNG, WEBP ou GIF sont acceptées.",
  profile_file_empty: "Ce fichier est vide.",
  profile_file_too_large: "Ce fichier est trop volumineux. Les images doivent faire moins de {{max}} Mo.",
  profile_image_not_found: "Image introuvable.",

  contract_not_found: "Contrat introuvable.",
  contract_not_a_party: "Vous n'êtes pas partie à ce contrat.",
  contract_signed_immutable: "Ce contrat est entièrement signé : il ne peut plus être modifié.",
  contract_you_already_signed: "Vous avez déjà signé.",
  contract_sign_cancelled: "Ce contrat a été annulé et ne peut plus être signé. Convenez de nouvelles conditions et générez un nouveau contrat.",
  contract_already_cancelled: "Ce contrat est déjà annulé.",
  contract_cancel_signed: "Ce contrat est signé par les deux parties. Elles s'y sont engagées, et ce n'est pas quelque chose qu'une seule peut annuler.",
  contract_cancel_funded: "Ce contrat a de l'argent bloqué en séquestre. Y mettre fin, c'est décider qui doit quoi : cela passe par le litige et le remboursement, pas par une annulation.",

  escrow_contract_not_found: "Contrat introuvable.",
  escrow_not_your_contract: "Ce contrat n'est pas le vôtre.",
  escrow_contract_not_signed: "Le contrat doit être entièrement signé avant d'être financé.",
  escrow_already_funded: "Ce contrat est déjà financé.",
  escrow_not_found: "Séquestre introuvable.",
  escrow_none_for_contract: "Aucun séquestre pour ce contrat.",
  escrow_not_a_party: "Vous n'êtes pas partie à ce séquestre.",
  escrow_not_held: "Le séquestre n'est pas bloqué.",
  escrow_release_business_only: "Seule l'entreprise peut confirmer la livraison.",
  escrow_release_needs_submission:
    "Il n'y a encore rien à confirmer : le créateur n'a pas envoyé de livrable pour ce séquestre. Une fois qu'il l'aura envoyé, confirmer la livraison valide cet envoi et libère le paiement.",

  deliverable_attachments_max: "Vous pouvez joindre au maximum {{max}} fichiers.",
  deliverable_contract_not_found: "Contrat introuvable.",
  deliverable_not_a_party: "Vous n'êtes pas partie à ce contrat.",
  deliverable_submit_creator_only: "Seul le créateur de ce contrat peut envoyer un livrable.",
  deliverable_contract_not_signed: "Un livrable ne peut être envoyé que sur un contrat entièrement signé.",
  deliverable_escrow_not_funded:
    "Aucun fonds n'est encore bloqué en séquestre sur ce contrat : il n'y a donc rien à livrer. Le livrable s'envoie une fois que la marque a payé.",
  deliverable_escrow_not_held: "Le séquestre n'est plus bloqué : aucun livrable ne peut être envoyé.",
  deliverable_submission_open_already:
    "Vous avez déjà envoyé un livrable sur ce contrat et la marque n'a pas encore répondu. Attendez sa réponse ou retirez d'abord votre envoi.",
  deliverable_note_too_long: "Une note fait au plus {{max}} caractères.",
  deliverable_submission_empty:
    "Un envoi doit contenir le lien de la publication, un fichier, ou les deux. Envoyez ce que la marque doit regarder.",
  deliverable_submission_not_found: "Envoi introuvable.",
  deliverable_review_business_only: "Seule l'entreprise de ce contrat peut valider un livrable.",
  deliverable_already_answered: "Cet envoi a déjà reçu une réponse.",
  deliverable_release_escrow_not_held: "Le séquestre n'est pas bloqué : il ne peut pas être libéré.",
  deliverable_changes_need_note: "Dites ce qui doit changer, pour que le créateur puisse corriger.",
  deliverable_withdraw_own_only: "Seul le créateur qui a envoyé ce livrable peut le retirer.",

  dispute_not_found: "Litige introuvable.",
  dispute_closed: "Ce litige est clos.",
  dispute_already_open: "Ce séquestre a déjà un litige ouvert.",
  dispute_escrow_not_held: "Seul un séquestre bloqué peut faire l'objet d'un litige.",
  dispute_escrow_not_disputed: "Ce séquestre n'est pas en litige.",
  dispute_frozen_without_case: "Ce séquestre est gelé sans litige ouvert. Signalez-le avant de trancher.",
  dispute_withdraw_own_only: "Seule la partie qui a ouvert le litige peut le retirer.",
  dispute_reason_unknown: "Le motif doit être l'un des suivants : {{reasons}}",
  dispute_statement_too_short: "Expliquez ce qui s'est passé en au moins {{min}} caractères.",
  dispute_statement_too_long: "Une déclaration fait au plus {{max}} caractères.",
  dispute_message_empty: "Un message ne peut pas être vide.",
  dispute_message_too_long: "Un message fait au plus {{max}} caractères.",
  dispute_evidence_max: "Vous pouvez joindre au maximum {{max}} images.",
  dispute_evidence_not_found: "Image introuvable.",
  dispute_evidence_not_yours: "Vous ne pouvez joindre que des images que vous avez importées.",

  board_not_a_creator: "Seuls les créateurs peuvent parcourir les briefs ouverts. Un brief contient un budget et les projets d'une marque, donc le tableau reste derrière un compte créateur.",
  board_not_open: "Ce brief n'est pas ouvert aux candidatures. La marque y invite les créateurs directement.",
  board_direct_order: "Ceci est une commande directe adressée à un seul créateur, pas un brief ouvert : on ne peut pas y candidater.",
  board_already_applied: "Vous avez déjà une proposition en cours sur ce brief. Modifiez-la en envoyant une nouvelle version plutôt qu'en candidatant à nouveau.",
  campaign_not_found: "Campagne introuvable.",
  campaign_not_open: "Cette campagne n'accepte pas de propositions.",

  order_terms_both: "Envoyez soit un pack, soit des conditions personnalisées, pas les deux. Conditions reçues : {{supplied}}",
  order_terms_missing: "Une commande demande soit un pack, soit une offre personnalisée complète ({{fields}}).",
  order_terms_incomplete: "Cette offre personnalisée est incomplète. Il manque : {{missing}}",
  order_to_self: "Vous ne pouvez pas vous envoyer une offre à vous-même.",
  order_target_not_creator: "Une offre ne peut être envoyée qu'à un créateur.",
  order_package_inactive: "Ce pack n'est pas disponible pour le moment.",
  order_own_package: "Vous ne pouvez pas commander votre propre pack.",
  order_quantity_range: "La quantité de livrables doit être un nombre entier entre {{min}} et {{max}}.",
  order_rate_invalid: "Le tarif doit être un montant entier positif.",
  order_timeline_range: "Le délai doit être un nombre entier de jours entre {{min}} et {{max}}.",
  campaign_not_yours: "Cette campagne n'est pas la vôtre.",
  contract_proposal_not_found: "Proposition introuvable.",
  contract_campaign_not_found: "Campagne introuvable.",
  contract_already_exists: "Un contrat existe déjà pour cette proposition.",
  contract_proposal_not_submitted: "Seule une proposition en cours peut être acceptée.",
  contract_own_offer: "Vous ne pouvez pas accepter votre propre offre. C'est à l'autre partie de l'accepter.",
  contract_campaign_not_open: "Cette campagne n'est plus ouverte : aucun nouveau contrat ne peut en être créé.",
  contract_none_for_proposal: "Aucun contrat pour cette proposition.",

  proposal_not_found: "Proposition introuvable.",
  proposal_not_yours: "Cette proposition n'est pas la vôtre.",
  proposal_not_live: "Cette proposition n'est plus l'offre en cours : il n'y a plus rien à retirer.",
  proposal_closed: "Cette proposition est close et ne peut plus recevoir de réponse.",
  proposal_negotiation_closed: "Cette négociation est close et ne peut plus recevoir de réponse.",
  proposal_has_contract: "Un contrat existe déjà pour cette proposition. C'est le contrat qu'il faut annuler.",
  proposal_is_direct_order: "Ceci est une commande directe, pas une offre sur un brief. Refusez-la plutôt que de la retirer.",

  message_gate: "La messagerie s'ouvre en même temps que le contrat. Il n'y a pas de contrat entre vous et cette personne sur cette campagne.",
  message_self: "Choisissez un autre destinataire.",

  invitation_not_found: "Invitation introuvable.",
  invitation_not_open: "Cette invitation n'est plus ouverte et ne peut pas être retirée.",
  invitation_priced: "Ce créateur a déjà envoyé une proposition : il y a une offre sur la table, à laquelle il faut répondre plutôt qu'une invitation à retirer. Répondez-lui ou rejetez-la.",

  campaign_is_direct_order: "Une commande directe ne se modifie pas. Ses conditions sont une négociation : faites une contre-proposition, ou laissez le créateur la refuser.",
  campaign_cancelled_immutable: "Cette campagne est annulée et ne peut plus être modifiée.",
  campaign_already_cancelled: "Cette campagne est déjà annulée.",
  campaign_needs_title: "Une campagne a besoin d'un titre.",
  campaign_field_locked: "« {{field}} » ne peut plus être modifié : un créateur a déjà chiffré une proposition dessus. Annulez cette campagne et republiez-la si les conditions doivent changer.",
  campaign_has_activity: "Cette campagne a de l'activité : annulez-la plutôt que de la supprimer.",
  campaign_has_contract: "Cette campagne a un contrat. Défaire un accord signé passe par le litige et le remboursement, pas par une annulation.",

  order_not_found: "Commande introuvable.",
  order_not_direct: "Cette proposition n'est pas une commande directe.",
  order_not_yours: "Cette commande ne vous est pas adressée.",
  order_own_counter: "Ceci est votre propre contre-proposition. C'est à la marque de l'accepter.",
  order_not_open: "Cette commande n'est plus ouverte.",
  order_expired: "Cette commande a expiré.",

  /* Paiements. Sans ces phrases, un refus de paiement s'affichait en anglais
     sur mobile — et le refus arrive au moment où quelqu'un regarde son
     argent, donc c'est la dernière phrase qui doive être illisible. */
  escrow_business_not_found: "Nous n'avons pas retrouvé votre compte. Reconnectez-vous puis réessayez.",
  payments_gateway_unavailable: "Le service de paiement est momentanément injoignable. Rien n'a été débité — réessayez dans un instant.",
  payments_gateway_not_configured: "Les paiements ne sont pas encore activés sur la plateforme. Contactez le support.",
  payment_intent_not_found: "Ce paiement est introuvable. Si un montant a été débité, contactez le support avec la référence.",
  payment_intent_not_yours: "Ce paiement ne vous appartient pas.",
  payments_country_unknown: "Nous n'avons pas pu déterminer le pays de ce paiement. Complétez le pays de votre profil puis réessayez.",
  payments_country_unsupported: "Les paiements en ligne ne sont pas encore disponibles dans votre pays. Nous vous préviendrons dès l'ouverture.",
  payments_currency_unsupported: "Nous ne pouvons pas encore traiter cette devise dans votre pays. Contactez le support si cela vous semble être une erreur.",
  payout_country_unsupported: "Nous ne pouvons pas encore effectuer de versement vers votre pays. Nous vous préviendrons dès l'ouverture.",
  payout_mode_unsupported: "Ce réseau Mobile Money n'est pas disponible dans le pays choisi. Sélectionnez-en un dans la liste.",
  payout_phone_invalid: "Ce numéro ne ressemble pas à un numéro Mobile Money valide.",
  escrow_use_checkout: "Le financement direct n'est plus disponible. Ouvrez la page de paiement sécurisé pour financer ce contrat.",
};

export const error_en: Record<string, string> = {
  generic: "Something went wrong. Try again in a moment.",

  /* Transport failures: the API never answered. Not backend codes — api.ts
     mints them — but they travel the same path, so no screen needs to know
     the difference. */
  network_unreachable: "Can't reach Kolabo. Check your connection and try again.",
  network_bad_response: "The server sent back something unexpected. On public Wi-Fi, a sign-in page may be intercepting the connection.",

  auth_user_not_found: "User not found.",
  auth_referral_code_failed: "A referral code could not be generated. Please try again.",
  auth_role_unknown: "The role must be one of: {{roles}}",
  auth_country_unavailable: "Kolabo is not available in this country yet.",
  auth_phone_taken: "That number is already used by another account.",
  auth_no_pending_verification: "There is no pending verification for this number.",
  auth_code_expired: "That verification code has expired. Request a new one.",
  auth_code_invalid: "Invalid verification code.",
  auth_bad_credentials: "Wrong number or password.",
  auth_not_verified: "This account is not verified yet. Confirm the code sent by SMS.",
  auth_password_incorrect: "Current password is incorrect.",
  auth_account_has_history:
    "This account has transaction history and cannot be closed here. Contact support.",
  auth_token_missing: "You are not signed in any more. Please sign in again.",
  auth_token_invalid: "Your session has expired. Please sign in again.",
  auth_account_nothing_to_change: "Send a new phone number, a new password, or both.",
  auth_reset_too_many: "Too many reset requests. Try again later.",
  auth_reset_code_invalid: "That reset code is invalid or expired.",

  profile_not_found: "Profile not found.",
  profile_under_age: "You must be at least {{min}} to create a creator profile.",
  profile_platform_unsupported: "That platform is not supported.",
  profile_social_method_unknown: 'The connection method must be "oauth" or "manual".',
  profile_proof_url_required: "A manual connection needs a proof link.",
  profile_social_not_found: "Social account not found.",
  profile_social_not_yours: "That social account is not yours.",
  profile_duration_pair: "A duration and its unit go together: give both, or neither.",
  package_not_found: "Package not found.",
  profile_package_not_yours: "That package is not yours.",
  deliverable_not_on_platform: '"{{type}}" is not available on {{platform}}. Allowed: {{allowed}}',
  price_below_floor: "The minimum price in {{currency}} is {{floor}}.",
  profile_image_type_unsupported: "Only JPEG, PNG, WEBP and GIF images are accepted.",
  profile_file_empty: "That file is empty.",
  profile_file_too_large: "This file is too large. Images must be under {{max}} MB.",
  profile_image_not_found: "Image not found.",

  contract_not_found: "Contract not found.",
  contract_not_a_party: "You are not a party to this contract.",
  contract_signed_immutable: "This contract is fully signed and can no longer be changed.",
  contract_you_already_signed: "You have already signed.",
  contract_sign_cancelled: "This contract was cancelled and can no longer be signed. Agree new terms and generate a new contract.",
  contract_already_cancelled: "This contract is already cancelled.",
  contract_cancel_signed: "This contract is fully signed. Both parties agreed to it, and it is not something either side can cancel alone.",
  contract_cancel_funded: "This contract has money in escrow. Ending it is a question about who is owed what, which is the dispute and refund path, not a cancellation.",

  escrow_contract_not_found: "Contract not found.",
  escrow_not_your_contract: "This contract is not yours.",
  escrow_contract_not_signed: "The contract must be fully signed before it can be funded.",
  escrow_already_funded: "This contract is already funded.",
  escrow_not_found: "Escrow not found.",
  escrow_none_for_contract: "No escrow for this contract.",
  escrow_not_a_party: "You are not a party to this escrow.",
  escrow_not_held: "This escrow is not held.",
  escrow_release_business_only: "Only the business can confirm delivery.",
  escrow_release_needs_submission:
    "There is nothing to confirm yet: the creator has not submitted any work against this escrow. Once they submit it, confirming delivery approves that submission and releases the payment.",

  deliverable_attachments_max: "At most {{max}} files can be attached.",
  deliverable_contract_not_found: "Contract not found.",
  deliverable_not_a_party: "You are not a party to this contract.",
  deliverable_submit_creator_only: "Only the creator on this contract can submit work.",
  deliverable_contract_not_signed: "Work can only be submitted on a fully signed contract.",
  deliverable_escrow_not_funded:
    "This contract has no money in escrow yet, so there is nothing to deliver against. Work is submitted once the brand has funded it.",
  deliverable_escrow_not_held: "This escrow is no longer held, so work cannot be submitted against it.",
  deliverable_submission_open_already:
    "You have already submitted work on this contract and the brand has not answered yet. Wait for their review, or withdraw the submission first.",
  deliverable_note_too_long: "A note is at most {{max}} characters.",
  deliverable_submission_empty:
    "A submission needs the link to the published post, a file, or both. Send what the brand is meant to look at.",
  deliverable_submission_not_found: "Submission not found.",
  deliverable_review_business_only: "Only the business on this contract can review submitted work.",
  deliverable_already_answered: "This submission has already been answered.",
  deliverable_release_escrow_not_held: "This escrow is not held, so it cannot be released.",
  deliverable_changes_need_note: "Say what needs to change, so the creator can fix it.",
  deliverable_withdraw_own_only: "Only the creator who submitted this work can withdraw it.",

  dispute_not_found: "Dispute not found.",
  dispute_closed: "This dispute is closed.",
  dispute_already_open: "This escrow already has an open dispute.",
  dispute_escrow_not_held: "Only a held escrow can be disputed.",
  dispute_escrow_not_disputed: "This escrow is not under dispute.",
  dispute_frozen_without_case: "This escrow is frozen with no open dispute attached. Report it before settling.",
  dispute_withdraw_own_only: "Only the party who raised the dispute can withdraw it.",
  dispute_reason_unknown: "The reason must be one of: {{reasons}}",
  dispute_statement_too_short: "Say what went wrong in at least {{min}} characters.",
  dispute_statement_too_long: "A statement is at most {{max}} characters.",
  dispute_message_empty: "A message cannot be empty.",
  dispute_message_too_long: "A message is at most {{max}} characters.",
  dispute_evidence_max: "At most {{max}} images can be attached.",
  dispute_evidence_not_found: "Evidence image not found.",
  dispute_evidence_not_yours: "You can only attach images you uploaded.",

  board_not_a_creator: "Only creators can browse open briefs. A brief carries a budget and a brand's plans, so the board stays behind a creator login.",
  board_not_open: "This brief is not open to applications. The brand invites creators to it directly.",
  board_direct_order: "This is a direct order addressed to one creator, not an open brief, and it cannot be applied to.",
  board_already_applied: "You already have a live proposal on this brief. Edit it by submitting a new version instead of applying again.",
  campaign_not_found: "Campaign not found.",
  campaign_not_open: "This campaign is not open for proposals.",

  order_terms_both: "Send either a package or custom terms, not both. Custom terms received: {{supplied}}",
  order_terms_missing: "An order needs either a package or a full custom offer ({{fields}}).",
  order_terms_incomplete: "That custom offer is incomplete. Missing: {{missing}}",
  order_to_self: "You cannot send an offer to yourself.",
  order_target_not_creator: "An offer can only be sent to a creator.",
  order_package_inactive: "That package is not available at the moment.",
  order_own_package: "You cannot order your own package.",
  order_quantity_range: "The deliverable quantity must be a whole number between {{min}} and {{max}}.",
  order_rate_invalid: "The rate must be a whole positive amount.",
  order_timeline_range: "The timeline must be a whole number of days between {{min}} and {{max}}.",
  campaign_not_yours: "This campaign is not yours.",
  contract_proposal_not_found: "Proposal not found.",
  contract_campaign_not_found: "Campaign not found.",
  contract_already_exists: "A contract already exists for this proposal.",
  contract_proposal_not_submitted: "Only a live proposal can be accepted.",
  contract_own_offer: "You cannot accept your own offer. The other party has to accept it.",
  contract_campaign_not_open: "This campaign is no longer open, so no new contract can be created from it.",
  contract_none_for_proposal: "No contract for this proposal.",

  proposal_not_found: "Proposal not found.",
  proposal_not_yours: "That proposal is not yours.",
  proposal_not_live: "That proposal is not the live offer any more, so there is nothing left to withdraw.",
  proposal_closed: "That proposal is closed and cannot be answered.",
  proposal_negotiation_closed: "That negotiation is closed and cannot be answered.",
  proposal_has_contract: "A contract already exists for this proposal. It is the contract that has to be cancelled.",
  proposal_is_direct_order: "This is a direct order, not a bid on a brief. Decline it rather than withdrawing it.",

  message_gate: "Messaging opens when a contract does. There is no contract between you and this person on this campaign.",
  message_self: "Choose a different recipient.",

  invitation_not_found: "Invitation not found.",
  invitation_not_open: "That invitation is no longer open and cannot be withdrawn.",
  invitation_priced: "This creator has already sent a proposal, so there is an offer on the table to answer rather than an invitation to retract. Reply to it or reject it.",

  campaign_is_direct_order: "A direct order cannot be edited. Its terms are a negotiation: counter it with a reply, or let the creator decline it.",
  campaign_cancelled_immutable: "This campaign is cancelled and cannot be edited.",
  campaign_already_cancelled: "This campaign is already cancelled.",
  campaign_needs_title: "A campaign needs a title.",
  campaign_field_locked: "\"{{field}}\" cannot be changed: a creator has already priced a proposal against it. Cancel this campaign and publish a new one if the terms have to change.",
  campaign_has_activity: "This campaign has activity: cancel it instead of deleting it.",
  campaign_has_contract: "This campaign has a contract. Unwinding a signed agreement is the dispute and refund path, not a cancellation.",

  order_not_found: "Order not found.",
  order_not_direct: "That proposal is not a direct order.",
  order_not_yours: "That order is not addressed to you.",
  order_own_counter: "This is your own counter-offer. The brand has to accept it.",
  order_not_open: "That order is no longer open.",
  order_expired: "That order has expired.",

  /* Payments. Mobile CI only type-checks, so a code missing from these maps
     never fails a build — it falls through to the backend's English and only
     a francophone reader ever finds out. */
  escrow_business_not_found: "We couldn't find your account. Please sign in again and retry.",
  payments_gateway_unavailable: "The payment service is unreachable right now. Nothing has been charged — please try again in a moment.",
  payments_gateway_not_configured: "Payments aren't switched on yet. Please contact support.",
  payment_intent_not_found: "We can't find this payment. If you were charged, contact support with the reference.",
  payment_intent_not_yours: "This payment isn't yours.",
  payments_country_unknown: "We couldn't tell which country this payment belongs to. Please complete your profile country and try again.",
  payments_country_unsupported: "Online payments aren't available in your country yet. We'll let you know as soon as they open.",
  payments_currency_unsupported: "We can't process this currency in your country yet. Contact support if you think that's a mistake.",
  payout_country_unsupported: "We can't pay out to your country yet. We'll let you know as soon as it opens.",
  payout_mode_unsupported: "That Mobile Money network isn't available in the country you chose. Please pick one from the list.",
  payout_phone_invalid: "That doesn't look like a valid Mobile Money number.",
  escrow_use_checkout: "Direct funding is no longer available. Open the secure payment page to fund this contract.",
};

/* i18next's t, narrowed to what this file needs — taken as an argument rather
   than imported so this module keeps its no-imports property. */
type Translate = (key: string, opts?: Record<string, unknown>) => string;

/* Anything thrown by api.ts, or by fetch. Read structurally so a plain Error,
   a string, or null still gets an answer rather than a crash. */
type MaybeApiError = { code?: unknown; values?: unknown; message?: unknown };

/* A sentinel handed to i18next as the defaultValue: it must be something no
   translation could equal, so an unknown code is distinguishable from a real
   (possibly falsy) sentence and falls through to the backend's English. */
const MISS = "::apiError-miss::";

/* The sentence to show a human for a failed request. Order of preference:
   1) the localised sentence for the code, if we know it;
   2) the backend's English `detail`/`message` — specific beats generic even in
      the wrong language, because it says what to do next;
   3) the generic sentence, for a network failure or a non-JSON response. */
export function errorText(err: unknown, t: Translate): string {
  const e = (err ?? {}) as MaybeApiError;

  if (typeof e.code === "string" && e.code) {
    const values =
      e.values && typeof e.values === "object" ? (e.values as Record<string, unknown>) : {};
    const text = t(`apiError.${e.code}`, { ...values, defaultValue: MISS });
    if (text !== MISS && text) return text;
  }

  if (typeof e.message === "string" && e.message) return e.message;

  return t(GENERIC_KEY);
}

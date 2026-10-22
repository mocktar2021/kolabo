/* What the API's refusals say, in French and in English.

   The backend answers a refusal with an English `detail` sentence and a stable
   `code` beside it (backend/app/core/errors.py). This file holds one sentence
   per code per language, and errorText() below picks the right one. Same
   arrangement as notificationBodies.ts, and for the same reason: no imports at
   all, so errorMessages.test.ts can read both maps and check them against the
   codes the backend actually emits without booting i18next.

   A CODE NAMES THE RULE, NOT THE SENTENCE. Rewording the English must never
   change the code, and two call sites enforcing the same rule share one even
   when their prose differs. That is what lets these sentences be rewritten in
   either language without touching Python.

   AND NOT THE MODULE EITHER. Most codes carry a module prefix, which is handy
   for reading but is not what makes them correct — so when a rule turned out
   to be enforced in more than one place, the prefix came off rather than the
   rule being duplicated. `deliverable_not_on_platform`, `price_below_floor`
   and `package_not_found` are checked by both profiles and campaigns;
   `campaign_not_yours` by both campaigns and contracts; `auth_user_not_found`
   is raised from profiles and campaigns as well as auth. Each of those was
   briefly two codes with two identical sentences in two languages, which is
   four things to keep in step instead of two — the exact drift this file
   exists to prevent, reintroduced by the naming.

   Codes are migrated one backend module at a time — 200-odd refusals do not
   move in one commit — so most of the API still answers with English prose and
   no code at all. errorText falls back to that prose, which is exactly what
   the app showed before any of this existed. Nothing gets worse on the way. */

/* The sentence shown when there is nothing else: a code we do not know, no
   code at all, and no English either (a network failure, a CORS refusal, a
   response that was not JSON). Also replaces the bare "Error" literal that
   pages used to fall back to, which was itself untranslated. */
export const GENERIC_KEY = "apiError.generic";

export const error_fr = {
  generic: "Une erreur est survenue. Réessayez dans un instant.",

  deliverable_attachments_max: "Vous pouvez joindre au maximum {{max}} fichiers.",
  deliverable_attachment_not_found: "Pièce jointe introuvable.",
  deliverable_attachment_not_yours: "Vous ne pouvez joindre que des fichiers que vous avez importés.",
  deliverable_contract_not_found: "Contrat introuvable.",
  deliverable_not_a_party: "Vous n'êtes pas partie à ce contrat.",
  deliverable_submit_creator_only: "Seul le créateur de ce contrat peut envoyer un livrable.",
  deliverable_contract_not_signed: "Un livrable ne peut être envoyé que sur un contrat entièrement signé.",
  deliverable_escrow_not_funded: "Aucun fonds n'est encore bloqué en séquestre sur ce contrat : il n'y a donc rien à livrer. Le livrable s'envoie une fois que la marque a payé.",
  deliverable_escrow_not_held: "Le séquestre n'est plus bloqué : aucun livrable ne peut être envoyé.",
  deliverable_submission_open_already: "Vous avez déjà envoyé un livrable sur ce contrat et la marque n'a pas encore répondu. Attendez sa réponse ou retirez d'abord votre envoi.",
  deliverable_note_too_long: "Une note fait au plus {{max}} caractères.",
  deliverable_link_too_long: "Un lien fait au plus {{max}} caractères.",
  deliverable_link_invalid: "Ce lien ne ressemble pas à une adresse web. Collez le lien complet de la publication, en commençant par https://.",
  deliverable_submission_empty: "Un envoi doit contenir le lien de la publication, un fichier, ou les deux. Envoyez ce que la marque doit regarder.",
  deliverable_submission_not_found: "Envoi introuvable.",
  deliverable_review_business_only: "Seule l'entreprise de ce contrat peut valider un livrable.",
  deliverable_already_answered: "Cet envoi a déjà reçu une réponse.",
  deliverable_release_escrow_not_held: "Le séquestre n'est pas bloqué : il ne peut pas être libéré.",
  deliverable_changes_need_note: "Dites ce qui doit changer, pour que le créateur puisse corriger.",
  deliverable_withdraw_own_only: "Seul le créateur qui a envoyé ce livrable peut le retirer.",

  escrow_contract_not_found: "Contrat introuvable.",
  escrow_not_your_contract: "Ce contrat n'est pas le vôtre.",
  escrow_contract_not_signed: "Le contrat doit être entièrement signé avant d'être financé.",
  escrow_already_funded: "Ce contrat est déjà financé.",
  escrow_not_found: "Séquestre introuvable.",
  escrow_none_for_contract: "Aucun séquestre pour ce contrat.",
  escrow_not_a_party: "Vous n'êtes pas partie à ce séquestre.",
  escrow_not_held: "Le séquestre n'est pas bloqué.",
  escrow_release_business_only: "Seule l'entreprise peut confirmer la livraison.",
  escrow_release_needs_submission: "Il n'y a encore rien à confirmer : le créateur n'a pas envoyé de livrable pour ce séquestre. Une fois qu'il l'aura envoyé, confirmer la livraison valide cet envoi et libère le paiement.",

  /* Les refus que peut produire le passage par la passerelle FeexPay. Ceux
     qui portent sur le pays et la devise sont le « refus franc » assumé pour
     les marchés que FeexPay ne dessert pas (Ghana, Cameroun) : la phrase doit
     donc promettre une suite, et non se lire comme une panne qu'il suffirait
     de réessayer. */
  escrow_business_not_found: "Nous n'avons pas retrouvé votre compte. Reconnectez-vous puis réessayez.",
  payments_gateway_unavailable: "Le service de paiement est momentanément injoignable. Rien n'a été débité. Réessayez dans un instant.",
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

  contract_proposal_not_found: "Proposition introuvable.",
  contract_campaign_not_found: "Campagne introuvable.",
  contract_already_exists: "Un contrat existe déjà pour cette proposition.",
  contract_proposal_not_submitted: "Seule une proposition en cours peut être acceptée.",
  contract_own_offer: "Vous ne pouvez pas accepter votre propre offre. C'est à l'autre partie de l'accepter.",
  contract_campaign_not_open: "Cette campagne n'est plus ouverte : aucun nouveau contrat ne peut en être créé.",
  contract_not_found: "Contrat introuvable.",
  contract_none_for_proposal: "Aucun contrat pour cette proposition.",
  contract_not_a_party: "Vous n'êtes pas partie à ce contrat.",
  contract_signed_immutable: "Ce contrat est entièrement signé : il ne peut plus être modifié.",
  contract_you_already_signed: "Vous avez déjà signé.",
  contract_sign_cancelled: "Ce contrat a été annulé et ne peut plus être signé. Convenez de nouvelles conditions et générez un nouveau contrat.",
  /* Ces trois-là remplacent undo.contractFunded / undo.contractRefused, qui
     étaient choisis d'après le code HTTP : le 400 servait à la fois pour un
     contrat déjà annulé et pour un contrat signé, deux situations qui
     n'appellent pas la même suite. */
  contract_already_cancelled: "Ce contrat est déjà annulé.",
  contract_cancel_signed: "Ce contrat est signé par les deux parties. Elles s'y sont engagées, et ce n'est pas quelque chose qu'une seule peut annuler.",
  contract_cancel_funded: "Ce contrat a de l'argent bloqué en séquestre. Y mettre fin, c'est décider qui doit quoi : cela passe par le litige et le remboursement, pas par une annulation.",

  /* Auth. These are the first refusals a person ever sees — signing up,
     logging in, entering a code — so they are also the ones most likely to be
     read by somebody who has not yet decided whether this product works. */
  auth_user_not_found: "Utilisateur introuvable.",
  auth_referral_code_failed: "Impossible de générer un code de parrainage. Réessayez.",
  /* {{roles}} is a list of machine values, left untranslated for the same
     reason as dispute_reason_unknown: a French rendering would be a list no
     endpoint accepts. */
  auth_role_unknown: "Le rôle doit être l'un des suivants : {{roles}}",
  auth_country_unavailable: "Kolabo n'est pas encore disponible dans ce pays.",
  auth_phone_taken: "Ce numéro est déjà utilisé par un autre compte.",
  auth_email_invalid: "Cette adresse e-mail ne semble pas valide. Vérifiez-la et réessayez.",
  auth_email_taken: "Cette adresse e-mail est déjà utilisée par un autre compte.",
  auth_no_pending_verification: "Aucune vérification en attente pour cette adresse.",
  auth_code_expired: "Ce code de vérification a expiré. Demandez-en un nouveau.",
  auth_code_invalid: "Code de vérification invalide.",
  /* Vague on purpose, dans les deux langues : distinguer « cette adresse
     n'existe pas » de « mot de passe incorrect » permettrait de savoir qui a
     un compte ici. Voir le commentaire du côté backend. */
  auth_bad_credentials: "Adresse e-mail ou mot de passe incorrect.",
  auth_not_verified: "Ce compte n'est pas encore vérifié. Confirmez le code envoyé par e-mail.",
  auth_password_incorrect: "Mot de passe actuel incorrect.",
  auth_account_has_history: "Ce compte a un historique de transactions et ne peut pas être fermé ici. Contactez le support.",
  auth_token_missing: "Vous n'êtes plus connecté(e). Reconnectez-vous.",
  auth_token_invalid: "Votre session a expiré. Reconnectez-vous.",
  auth_account_nothing_to_change: "Indiquez une nouvelle adresse e-mail, un nouveau numéro, un nouveau mot de passe, ou plusieurs de ces éléments.",
  auth_reset_too_many: "Trop de demandes de réinitialisation. Réessayez plus tard.",
  auth_otp_too_many: "Trop de codes de vérification demandés. Réessayez plus tard.",
  auth_otp_capacity: "Les codes de vérification sont momentanément indisponibles. Réessayez dans quelques minutes.",
  auth_otp_delivery_failed: "Nous n'avons pas pu envoyer le code de vérification. Réessayez dans un instant.",
  auth_reset_code_invalid: "Ce code de réinitialisation est invalide ou expiré.",

  /* Connexion avec Google. Trois refus seulement, parce que le client n'a que
     trois conduites à tenir : cacher le bouton, redemander, ou poser deux
     questions.

     auth_google_token_invalid couvre TOUTES les façons dont un jeton peut
     être refusé, y compris une adresse que Google n'a pas confirmée.
     Distinguer les cas indiquerait à qui présente un faux jeton quelle
     vérification l'a arrêté, et la phrase porte de toute façon les deux seules
     suites utiles : réessayer, et vérifier l'adresse côté Google.

     auth_google_profile_required n'est pas une erreur. C'est la première
     étape d'un parcours en deux temps : Google dit qui vous êtes et ne peut
     pas dire dans quel pays vous vendez ni si vous venez vendre. Le client
     pose les deux questions puis rappelle POST /auth/google avec le même
     jeton. */
  auth_google_unavailable: "La connexion avec Google n'est pas disponible. Utilisez votre adresse e-mail et votre mot de passe.",
  auth_google_token_invalid: "Nous n'avons pas pu vous connecter avec Google. Réessayez, et vérifiez que votre adresse e-mail Google est confirmée.",
  auth_google_profile_required: "Indiquez votre pays et si vous êtes créateur ou entreprise, puis reconnectez-vous avec Google.",

  /* L'autre moitié du même changement. Supprimer son compte ou en changer les
     identifiants demande de prouver qu'on en est le titulaire, et deux preuves
     valent désormais l'une pour l'autre, une seule à la fois : le mot de passe
     actuel, ou une connexion Google fraîchement vérifiée sur la même adresse.
     Un compte créé avec Google n'a pas de mot de passe utilisable, donc sans
     cette seconde preuve son titulaire ne pourrait ni le supprimer ni le
     modifier.

     Pas auth_password_incorrect : cette phrase-là parle d'un mot de passe, et
     enverrait chercher un mot de passe que ce compte n'a peut-être jamais eu. */
  auth_reauth_required: "Nous n'avons pas pu confirmer que c'est bien vous. Saisissez votre mot de passe actuel, ou confirmez avec Google, puis réessayez.",

  /* Profiles: setting up a creator page, its packages and its portfolio. */
  profile_not_found: "Profil introuvable.",
  profile_under_age: "Vous devez avoir au moins {{min}} ans pour créer un profil de créateur.",
  profile_doc_type_unknown: "Le type de document doit être l'un des suivants : {{types}}",
  profile_document_empty: "Ce document est vide.",
  profile_platform_unsupported: "Cette plateforme n'est pas prise en charge.",
  profile_social_method_unknown: "La méthode de connexion doit être « oauth » ou « manual ».",
  profile_proof_url_required: "Une connexion manuelle demande un lien de preuve.",
  profile_social_not_found: "Compte social introuvable.",
  profile_social_not_yours: "Ce compte social n'est pas le vôtre.",
  profile_bio_ai_unavailable: "La rédaction assistée n'est pas disponible. Écrivez votre bio vous-même pour l'instant.",
  profile_bio_limit_reached: "Vous avez atteint la limite de bios générées. Modifiez le texte vous-même.",
  profile_bio_needs_categories: "Choisissez d'abord au moins une catégorie de contenu, pour que la bio vous décrive vous et pas un créateur générique.",
  profile_bio_failed: "Impossible de rédiger une bio pour le moment. Réessayez, ou écrivez la vôtre.",
  profile_image_type_unsupported: "Seules les images JPEG, PNG, WEBP ou GIF sont acceptées.",
  profile_file_empty: "Ce fichier est vide.",
  profile_file_too_large: "Ce fichier est trop volumineux. Les images doivent faire moins de {{max}} Mo.",
  profile_image_not_found: "Image introuvable.",
  /* {{type}} et {{platform}} sont des valeurs machine, mais le client les
     affiche déjà traduites dans ses propres listes ; c'est la phrase autour
     d'elles qui avait besoin d'être traduite. */
  deliverable_not_on_platform: "« {{type}} » n'existe pas sur {{platform}}. Possibilités : {{allowed}}",
  price_below_floor: "Le prix minimum en {{currency}} est de {{floor}}.",
  profile_duration_pair: "La durée et son unité vont ensemble : indiquez les deux, ou aucun des deux.",
  package_not_found: "Pack introuvable.",
  profile_package_not_yours: "Ce pack n'est pas le vôtre.",
  profile_portfolio_item_not_found: "Élément de portfolio introuvable.",
  profile_portfolio_not_yours: "Ce portfolio n'est pas le vôtre.",

  /* Connecter un compte social via OAuth. Les cinq premières phrases pointent
     vers la même suite, parce qu'il n'y en a qu'une : recommencer depuis le
     profil. Un lien de connexion ne sert qu'une fois et vit dix minutes, donc
     « réessayez » serait un conseil qui ne peut pas marcher.

     oauth_page_not_found est la seule à dire autre chose, parce que la suite y
     est autre chose. La liste des Pages est relue en direct à chaque appel, et
     une Page qui n'y figure plus se règle en rechargeant la liste, pas en
     refaisant toute la connexion. */
  oauth_platform_unsupported: "Cette plateforme ne peut pas encore être connectée automatiquement.",
  oauth_state_invalid: "Ce lien de connexion n'est pas valide. Recommencez depuis votre profil.",
  oauth_state_expired: "Ce lien de connexion a expiré. Recommencez depuis votre profil.",
  oauth_exchange_failed: "La plateforme a refusé la connexion. Rien n'a été enregistré.",
  oauth_token_expired: "Votre connexion à cette plateforme a expiré. Reconnectez-la depuis votre profil.",
  oauth_page_not_found: "Cette Page ne fait pas partie de celles que vous gérez. Rechargez la liste et choisissez de nouveau.",

  /* Campaigns: writing a brief, inviting, bidding, negotiating, taking an
     offer back. The un-prefixed codes above and below — deliverable_not_on_-
     platform, price_below_floor, package_not_found, campaign_not_yours — are
     rules that turned out to be enforced in more than one module, so they
     carry no module name. See the note in the header. */
  campaign_not_found: "Campagne introuvable.",
  campaign_not_yours: "Cette campagne n'est pas la vôtre.",
  campaign_author_only: "Seules les entreprises et les agences peuvent créer une campagne.",
  campaign_status_unknown: "Le statut doit être l'un des suivants : {{statuses}}",
  campaign_platform_unsupported: "{{platform}} n'est pas une plateforme prise en charge. Possibilités : {{allowed}}",
  campaign_quantity_range: "La quantité doit être un nombre entier entre {{min}} et {{max}}.",
  campaign_publish_incomplete: "Un budget, des livrables et une date limite sont nécessaires pour publier.",
  campaign_publish_not_draft: "Seule une campagne en brouillon peut être publiée.",
  campaign_publish_before_inviting: "Publiez la campagne avant d'inviter des créateurs.",
  campaign_influencer_not_found: "Créateur introuvable.",
  campaign_influencer_not_verified: "Ce créateur n'est pas encore vérifié et ne peut pas être invité.",
  campaign_not_open: "Cette campagne n'accepte pas de propositions.",
  campaign_deadline_passed: "La date limite de cette campagne est passée, elle n'accepte plus de propositions.",

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

  proposal_not_found: "Proposition introuvable.",
  proposal_not_yours: "Cette proposition n'est pas la vôtre.",
  proposal_not_live: "Cette proposition n'est plus l'offre en cours : il n'y a plus rien à retirer.",
  proposal_closed: "Cette proposition est close et ne peut plus recevoir de réponse.",
  proposal_negotiation_closed: "Cette négociation est close et ne peut plus recevoir de réponse.",
  proposal_has_contract: "Un contrat existe déjà pour cette proposition. C'est le contrat qu'il faut annuler.",
  proposal_is_direct_order: "Ceci est une commande directe, pas une offre sur un brief. Refusez-la plutôt que de la retirer.",

  invitation_not_found: "Invitation introuvable.",
  invitation_not_open: "Cette invitation n'est plus ouverte et ne peut pas être retirée.",
  invitation_priced: "Ce créateur a déjà envoyé une proposition : il y a une offre sur la table, à laquelle il faut répondre plutôt qu'une invitation à retirer. Répondez-lui ou rejetez-la.",
  invitation_already_sent: "Vous avez déjà invité ce créateur à cette campagne.",

  order_not_found: "Commande introuvable.",
  order_not_direct: "Cette proposition n'est pas une commande directe.",
  order_not_yours: "Cette commande ne vous est pas adressée.",
  order_own_counter: "Ceci est votre propre contre-proposition. C'est à la marque de l'accepter.",
  order_not_open: "Cette commande n'est plus ouverte.",
  order_expired: "Cette commande a expiré.",

  campaign_is_direct_order: "Une commande directe ne se modifie pas. Ses conditions sont une négociation : faites une contre-proposition, ou laissez le créateur la refuser.",
  campaign_cancelled_immutable: "Cette campagne est annulée et ne peut plus être modifiée.",
  campaign_already_cancelled: "Cette campagne est déjà annulée.",
  campaign_needs_title: "Une campagne a besoin d'un titre.",
  /* {{field}} est le nom technique du champ ("budget_amount"), donc en
     anglais au milieu d'une phrase française. Même arbitrage que
     {{document}} côté notifications : dire LEQUEL des champs est verrouillé
     compte plus que la couture, tant que les champs n'ont pas leurs propres
     clés de traduction. */
  campaign_field_locked: "« {{field}} » ne peut plus être modifié : un créateur a déjà chiffré une proposition dessus. Annulez cette campagne et republiez-la si les conditions doivent changer.",
  campaign_has_activity: "Cette campagne a de l'activité : annulez-la plutôt que de la supprimer.",
  campaign_has_contract: "Cette campagne a un contrat. Défaire un accord signé passe par le litige et le remboursement, pas par une annulation.",

  board_not_a_creator: "Seuls les créateurs peuvent parcourir les briefs ouverts. Un brief contient un budget et les projets d'une marque, donc le tableau reste derrière un compte créateur.",
  board_not_open: "Ce brief n'est pas ouvert aux candidatures. La marque y invite les créateurs directement.",
  board_direct_order: "Ceci est une commande directe adressée à un seul créateur, pas un brief ouvert : on ne peut pas y candidater.",
  board_already_applied: "Vous avez déjà une proposition en cours sur ce brief. Modifiez-la en envoyant une nouvelle version plutôt qu'en candidatant à nouveau.",

  cart_empty: "Un paiement demande au moins un article.",
  cart_too_many_items: "Un panier contient au plus {{max}} articles. Payez en plusieurs fois.",
  cart_mixed_currencies: "Les articles de ce créateur sont libellés en {{currencies}}. Une commande porte un seul séquestre, et un séquestre une seule devise : commandez chaque devise séparément.",
  /* Seulement pour un refus qui n'a pas de code à lui — voir cart._resolve_item.
     Le cas normal renvoie le code du refus d'origine, avec cart_index dans les
     valeurs pour que la page surligne la bonne ligne. */
  cart_item_refused: "L'article {{cart_index}} de votre panier a été refusé.",

  /* The tail: moderation, the admin queue, messaging, notification settings,
     country config, discovery. Small modules, and the last of them. */
  admin_not_authorised: "Ce compte n'est pas administrateur.",
  admin_decision_unknown: "La décision doit être « approuvé » ou « refusé ».",
  admin_rejection_needs_reason: "Un refus demande un motif.",
  admin_document_not_found: "Document introuvable.",

  /* Not escrow_not_found, though it is the same row being looked up. The
     person here is reviewing a finished job, and "séquestre introuvable" is
     not the word they would use for it — the rule is shared, the reader's
     noun is not. Where those two pull apart, the reader wins. */
  review_collaboration_not_found: "Collaboration introuvable.",
  review_not_a_party: "Vous n'avez pas participé à cette collaboration.",
  review_not_completed: "Vous pourrez laisser un avis une fois la collaboration terminée et payée.",
  review_already_submitted: "Vous avez déjà laissé un avis sur cette collaboration.",

  report_target_type_unknown: "Type de signalement inconnu.",
  report_reason_unknown: "Motif de signalement inconnu.",
  report_decision_unknown: "La décision doit être « examiné » ou « rejeté ».",
  report_not_found: "Signalement introuvable.",
  report_already_resolved: "Ce signalement est déjà traité.",

  message_gate: "La messagerie s'ouvre en même temps que le contrat. Il n'y a pas de contrat entre vous et cette personne sur cette campagne.",
  message_self: "Choisissez un autre destinataire.",

  notification_not_found: "Notification introuvable.",
  notification_critical_locked: "Les notifications critiques (paiement, litige) ne peuvent pas être désactivées.",

  country_not_configured: "Ce pays n'est pas configuré.",

  dispute_not_found: "Litige introuvable.",
  dispute_closed: "Ce litige est clos.",
  dispute_already_open: "Ce séquestre a déjà un litige ouvert.",
  dispute_escrow_not_held: "Seul un séquestre bloqué peut faire l'objet d'un litige.",
  dispute_escrow_not_disputed: "Ce séquestre n'est pas en litige.",
  dispute_frozen_without_case: "Ce séquestre est gelé sans litige ouvert. Signalez-le avant de trancher.",
  dispute_withdraw_own_only: "Seule la partie qui a ouvert le litige peut le retirer.",
  /* {{reasons}} is a list of machine values the client sends back, not prose:
     translating them would produce a list no endpoint accepts. A client that
     hits this has a bug, not a language problem. */
  dispute_reason_unknown: "Le motif doit être l'un des suivants : {{reasons}}",
  dispute_statement_too_short: "Expliquez ce qui s'est passé en au moins {{min}} caractères.",
  dispute_statement_too_long: "Une déclaration fait au plus {{max}} caractères.",
  dispute_message_empty: "Un message ne peut pas être vide.",
  dispute_message_too_long: "Un message fait au plus {{max}} caractères.",
  dispute_evidence_max: "Vous pouvez joindre au maximum {{max}} images.",
  dispute_evidence_not_found: "Image introuvable.",
  dispute_evidence_not_yours: "Vous ne pouvez joindre que des images que vous avez importées.",
  dispute_amount_negative: "Aucun des deux montants ne peut être négatif.",
  /* Shown to an admin settling a split that does not add up. The arithmetic is
     the useful part, not the rule — hence five values rather than a sentence
     about conservation of money. */
  dispute_amounts_must_balance: "{{released}} libérés et {{refunded}} remboursés font {{total}}, mais le séquestre contient {{amount}} {{currency}}. L'argent ne doit être ni créé ni détruit.",

  /* The contact guard's refusal, and the only body whose values are words
     rather than numbers. {{what}} and {{surface}} are composed by
     contactDetails() below from the tokens the backend sends, because French
     does not build a list the way English does and a sentence assembled in
     Python could only ever be assembled in one language. */
  contact_details_found: "Ce {{surface}} semble contenir {{what}}. Kolabo garde la conversation, le contrat et l'argent au même endroit : un accord conclu ailleurs n'a ni contrat ni séquestre derrière lui, donc aucune des deux parties n'a de recours si ça tourne mal. Retirez-le et renvoyez votre {{surface}}. Rien n'a été enregistré et rien n'a été modifié.",
  kind_email: "une adresse e-mail",
  kind_phone: "un numéro de téléphone",
  kind_handle: "un identifiant de messagerie",
  /* Grammatical gender is why these are nouns with their article attached and
     why the sentence above says "Ce {{surface}}" rather than agreeing with
     each one: "cette déclaration" would need the template to change with the
     value. Kept masculine and neutral instead — correct for "message" and
     "livrable", and readable for the others. */
  surface_message: "message",
  surface_statement: "texte",
  surface_proposal_note: "commentaire de proposition",
  surface_brief_description: "descriptif de brief",
  /* The last separator in a list of two or three. Everything before it is a
     comma in both languages; only the final join differs. */
  list_and: "et"
};

export const error_en = {
  generic: "Something went wrong. Try again in a moment.",

  deliverable_attachments_max: "At most {{max}} files can be attached.",
  deliverable_attachment_not_found: "Attachment not found.",
  deliverable_attachment_not_yours: "You can only attach files you uploaded.",
  deliverable_contract_not_found: "Contract not found.",
  deliverable_not_a_party: "You are not a party to this contract.",
  deliverable_submit_creator_only: "Only the creator on this contract can submit work.",
  deliverable_contract_not_signed: "Work can only be submitted on a fully signed contract.",
  deliverable_escrow_not_funded: "This contract has no money in escrow yet, so there is nothing to deliver against. Work is submitted once the brand has funded it.",
  deliverable_escrow_not_held: "This escrow is no longer held, so work cannot be submitted against it.",
  deliverable_submission_open_already: "You have already submitted work on this contract and the brand has not answered yet. Wait for their review, or withdraw the submission first.",
  deliverable_note_too_long: "A note is at most {{max}} characters.",
  deliverable_link_too_long: "A link is at most {{max}} characters.",
  deliverable_link_invalid: "That link does not look like a web address. Paste the full link to the published post, starting with https://.",
  deliverable_submission_empty: "A submission needs the link to the published post, a file, or both. Send what the brand is meant to look at.",
  deliverable_submission_not_found: "Submission not found.",
  deliverable_review_business_only: "Only the business on this contract can review submitted work.",
  deliverable_already_answered: "This submission has already been answered.",
  deliverable_release_escrow_not_held: "This escrow is not held, so it cannot be released.",
  deliverable_changes_need_note: "Say what needs to change, so the creator can fix it.",
  deliverable_withdraw_own_only: "Only the creator who submitted this work can withdraw it.",

  escrow_contract_not_found: "Contract not found.",
  escrow_not_your_contract: "This contract is not yours.",
  escrow_contract_not_signed: "The contract must be fully signed before it can be funded.",
  escrow_already_funded: "This contract is already funded.",
  escrow_not_found: "Escrow not found.",
  escrow_none_for_contract: "No escrow for this contract.",
  escrow_not_a_party: "You are not a party to this escrow.",
  escrow_not_held: "This escrow is not held.",
  escrow_release_business_only: "Only the business can confirm delivery.",
  escrow_release_needs_submission: "There is nothing to confirm yet: the creator has not submitted any work against this escrow. Once they submit it, confirming delivery approves that submission and releases the payment.",

  /* The refusals the FeexPay gateway path can produce. The country and
     currency ones are the deliberate "fail loudly" answer for markets FeexPay
     does not serve (Ghana, Cameroon), so the sentence has to promise a
     follow-up rather than read like a fault worth retrying. */
  escrow_business_not_found: "We couldn't find your account. Please sign in again and retry.",
  payments_gateway_unavailable: "The payment service is unreachable right now. Nothing has been charged. Please try again in a moment.",
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

  contract_proposal_not_found: "Proposal not found.",
  contract_campaign_not_found: "Campaign not found.",
  contract_already_exists: "A contract already exists for this proposal.",
  contract_proposal_not_submitted: "Only a live proposal can be accepted.",
  contract_own_offer: "You cannot accept your own offer. The other party has to accept it.",
  contract_campaign_not_open: "This campaign is no longer open, so no new contract can be created from it.",
  contract_not_found: "Contract not found.",
  contract_none_for_proposal: "No contract for this proposal.",
  contract_not_a_party: "You are not a party to this contract.",
  contract_signed_immutable: "This contract is fully signed and can no longer be changed.",
  contract_you_already_signed: "You have already signed.",
  contract_sign_cancelled: "This contract was cancelled and can no longer be signed. Agree new terms and generate a new contract.",
  contract_already_cancelled: "This contract is already cancelled.",
  contract_cancel_signed: "This contract is fully signed. Both parties agreed to it, and it is not something either side can cancel alone.",
  contract_cancel_funded: "This contract has money in escrow. Ending it is a question about who is owed what, which is the dispute and refund path, not a cancellation.",

  auth_user_not_found: "User not found.",
  auth_referral_code_failed: "A referral code could not be generated. Please try again.",
  auth_role_unknown: "The role must be one of: {{roles}}",
  auth_country_unavailable: "Kolabo is not available in this country yet.",
  auth_phone_taken: "That number is already used by another account.",
  auth_email_invalid: "That email address does not look right. Check it and try again.",
  auth_email_taken: "That email address is already used by another account.",
  auth_no_pending_verification: "There is no pending verification for this address.",
  auth_code_expired: "That verification code has expired. Request a new one.",
  auth_code_invalid: "Invalid verification code.",
  auth_bad_credentials: "Wrong email address or password.",
  auth_not_verified: "This account is not verified yet. Confirm the code sent by email.",
  auth_password_incorrect: "Current password is incorrect.",
  auth_account_has_history: "This account has transaction history and cannot be closed here. Contact support.",
  auth_token_missing: "You are not signed in any more. Please sign in again.",
  auth_token_invalid: "Your session has expired. Please sign in again.",
  auth_account_nothing_to_change: "Send a new email address, a new phone number, a new password, or any combination of them.",
  auth_reset_too_many: "Too many reset requests. Try again later.",
  auth_otp_too_many: "Too many verification codes requested. Try again later.",
  auth_otp_capacity: "Verification codes are temporarily unavailable. Try again in a few minutes.",
  auth_otp_delivery_failed: "We could not send the verification code. Try again in a moment.",
  auth_reset_code_invalid: "That reset code is invalid or expired.",

  /* Signing in with Google. Three refusals only, because a client has exactly
     three things to do about it: hide the button, ask again, or ask two
     questions.

     auth_google_token_invalid covers EVERY way a token can be refused,
     including an address Google has not confirmed. Telling them apart would
     say to whoever is holding a forged token which check caught it, and the
     sentence carries the only two next steps that ever help anyway: try
     again, and check the address on the Google side.

     auth_google_profile_required is not an error. It is the first leg of a
     two step flow: Google says who somebody is and cannot say which country
     they sell in or whether they came here to sell. The client asks both
     questions and calls POST /auth/google again with the same token. */
  auth_google_unavailable: "Signing in with Google is not available. Use your email address and password.",
  auth_google_token_invalid: "We could not sign you in with Google. Try again, and check that your Google email address is confirmed.",
  auth_google_profile_required: "Tell us your country and whether you are a creator or a business, then sign in with Google again.",

  /* The other half of the same change. Deleting an account, or changing what
     it is reached by, costs proof that you own it, and two proofs now stand
     for each other, exactly one at a time: the current password, or a freshly
     verified Google sign in on the same address. An account created with
     Google has no usable password, so without the second proof its owner
     could never delete or edit it.

     Not auth_password_incorrect: that sentence is about a password, and it
     would send somebody hunting for one this account may never have had. */
  auth_reauth_required: "We could not confirm it is you. Enter your current password, or confirm with Google, and try again.",

  profile_not_found: "Profile not found.",
  profile_under_age: "You must be at least {{min}} to create a creator profile.",
  profile_doc_type_unknown: "The document type must be one of: {{types}}",
  profile_document_empty: "That document is empty.",
  profile_platform_unsupported: "That platform is not supported.",
  profile_social_method_unknown: "The connection method must be \"oauth\" or \"manual\".",
  profile_proof_url_required: "A manual connection needs a proof link.",
  profile_social_not_found: "Social account not found.",
  profile_social_not_yours: "That social account is not yours.",
  profile_bio_ai_unavailable: "Assisted writing is not available. Write your bio yourself for now.",
  profile_bio_limit_reached: "You have reached the limit for generated bios. Edit the text yourself instead.",
  profile_bio_needs_categories: "Choose at least one content category first, so the bio describes you and not a generic creator.",
  profile_bio_failed: "A bio could not be drafted right now. Try again, or write your own.",
  profile_image_type_unsupported: "Only JPEG, PNG, WEBP and GIF images are accepted.",
  profile_file_empty: "That file is empty.",
  profile_file_too_large: "This file is too large. Images must be under {{max}} MB.",
  profile_image_not_found: "Image not found.",
  deliverable_not_on_platform: "\"{{type}}\" is not available on {{platform}}. Allowed: {{allowed}}",
  price_below_floor: "The minimum price in {{currency}} is {{floor}}.",
  profile_duration_pair: "A duration and its unit go together: give both, or neither.",
  package_not_found: "Package not found.",
  profile_package_not_yours: "That package is not yours.",
  profile_portfolio_item_not_found: "Portfolio item not found.",
  profile_portfolio_not_yours: "That portfolio is not yours.",

  /* Connecting a social account over OAuth. The first five point at the same
     next step, because there is only one: start again from your profile. A
     connection link is single-use and ten minutes old, so "try again" would
     be advice that cannot work.

     oauth_page_not_found is the one that says something else, because its next
     step is something else. The Page list is re-read live on every call, so a
     Page that is no longer in it is put right by reloading the list rather
     than by doing the whole connection again. */
  oauth_platform_unsupported: "This platform cannot be connected automatically yet.",
  oauth_state_invalid: "This connection link is not valid. Start again from your profile.",
  oauth_state_expired: "This connection link has expired. Start again from your profile.",
  oauth_exchange_failed: "The platform refused the connection. Nothing was saved.",
  oauth_token_expired: "Your connection to this platform has expired. Reconnect it from your profile.",
  oauth_page_not_found: "That is not one of the Pages you manage. Refresh the list and choose again.",

  campaign_not_found: "Campaign not found.",
  campaign_not_yours: "This campaign is not yours.",
  campaign_author_only: "Only businesses and agencies can create a campaign.",
  campaign_status_unknown: "The status must be one of: {{statuses}}",
  campaign_platform_unsupported: "{{platform}} is not a supported platform. Allowed: {{allowed}}",
  campaign_quantity_range: "The quantity must be a whole number between {{min}} and {{max}}.",
  campaign_publish_incomplete: "A budget, deliverables and a deadline are required to publish.",
  campaign_publish_not_draft: "Only a draft campaign can be published.",
  campaign_publish_before_inviting: "Publish the campaign before inviting creators.",
  campaign_influencer_not_found: "Creator not found.",
  campaign_influencer_not_verified: "This creator is not verified yet and cannot be invited.",
  campaign_not_open: "This campaign is not open for proposals.",
  campaign_deadline_passed: "This brief's deadline has passed, so it is no longer taking proposals.",

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

  proposal_not_found: "Proposal not found.",
  proposal_not_yours: "That proposal is not yours.",
  proposal_not_live: "That proposal is not the live offer any more, so there is nothing left to withdraw.",
  proposal_closed: "That proposal is closed and cannot be answered.",
  proposal_negotiation_closed: "That negotiation is closed and cannot be answered.",
  proposal_has_contract: "A contract already exists for this proposal. It is the contract that has to be cancelled.",
  proposal_is_direct_order: "This is a direct order, not a bid on a brief. Decline it rather than withdrawing it.",

  invitation_not_found: "Invitation not found.",
  invitation_not_open: "That invitation is no longer open and cannot be withdrawn.",
  invitation_priced: "This creator has already sent a proposal, so there is an offer on the table to answer rather than an invitation to retract. Reply to it or reject it.",
  invitation_already_sent: "You have already invited this creator to this campaign.",

  order_not_found: "Order not found.",
  order_not_direct: "That proposal is not a direct order.",
  order_not_yours: "That order is not addressed to you.",
  order_own_counter: "This is your own counter-offer. The brand has to accept it.",
  order_not_open: "That order is no longer open.",
  order_expired: "That order has expired.",

  campaign_is_direct_order: "A direct order cannot be edited. Its terms are a negotiation: counter it with a reply, or let the creator decline it.",
  campaign_cancelled_immutable: "This campaign is cancelled and cannot be edited.",
  campaign_already_cancelled: "This campaign is already cancelled.",
  campaign_needs_title: "A campaign needs a title.",
  campaign_field_locked: "\"{{field}}\" cannot be changed: a creator has already priced a proposal against it. Cancel this campaign and publish a new one if the terms have to change.",
  campaign_has_activity: "This campaign has activity: cancel it instead of deleting it.",
  campaign_has_contract: "This campaign has a contract. Unwinding a signed agreement is the dispute and refund path, not a cancellation.",

  board_not_a_creator: "Only creators can browse open briefs. A brief carries a budget and a brand's plans, so the board stays behind a creator login.",
  board_not_open: "This brief is not open to applications. The brand invites creators to it directly.",
  board_direct_order: "This is a direct order addressed to one creator, not an open brief, and it cannot be applied to.",
  board_already_applied: "You already have a live proposal on this brief. Edit it by submitting a new version instead of applying again.",

  cart_empty: "A checkout needs at least one item.",
  cart_too_many_items: "A cart holds at most {{max}} items. Check out in smaller baskets.",
  cart_mixed_currencies: "This creator's items are priced in {{currencies}}. An order carries one escrow and an escrow carries one currency, so order each currency separately.",
  cart_item_refused: "Item {{cart_index}} in your basket was refused.",

  admin_not_authorised: "This account is not an administrator.",
  admin_decision_unknown: "The decision must be \"approved\" or \"rejected\".",
  admin_rejection_needs_reason: "A rejection needs a reason.",
  admin_document_not_found: "Document not found.",

  review_collaboration_not_found: "Collaboration not found.",
  review_not_a_party: "You were not part of this collaboration.",
  review_not_completed: "You can leave a review once the collaboration is completed and paid.",
  review_already_submitted: "You have already reviewed this collaboration.",

  report_target_type_unknown: "Unknown report target type.",
  report_reason_unknown: "Unknown report reason.",
  report_decision_unknown: "The decision must be \"reviewed\" or \"dismissed\".",
  report_not_found: "Report not found.",
  report_already_resolved: "That report has already been dealt with.",

  message_gate: "Messaging opens when a contract does. There is no contract between you and this person on this campaign.",
  message_self: "Choose a different recipient.",

  notification_not_found: "Notification not found.",
  notification_critical_locked: "Critical notifications (payment, dispute) cannot be turned off.",

  country_not_configured: "That country is not configured.",

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
  dispute_amount_negative: "Neither amount can be negative.",
  dispute_amounts_must_balance: "{{released}} released and {{refunded}} refunded add up to {{total}}, but the escrow holds {{amount}} {{currency}}. Money must not be invented or destroyed.",

  contact_details_found: "This {{surface}} looks like it contains {{what}}. Kolabo keeps the conversation, the contract and the money in one place: a deal agreed elsewhere has no contract and no escrow behind it, so neither side has any recourse if it goes wrong. Take it out and send the {{surface}} again. Nothing was saved and nothing was edited.",
  kind_email: "an email address",
  kind_phone: "a phone number",
  kind_handle: "a messaging app handle",
  surface_message: "message",
  surface_statement: "statement",
  surface_proposal_note: "proposal note",
  surface_brief_description: "brief description",
  list_and: "and"
};

/* i18next's t, narrowed to what this file needs. Taken as an argument rather
   than imported so this module keeps its no-imports property. */
type Translate = (key: string, opts?: Record<string, unknown>) => string;

/* Anything thrown by lib/api.ts, or by fetch, or by a component. Read
   structurally rather than with `instanceof ApiError` — importing ApiError
   would be an import, and a caller that hands us a plain Error (or a string,
   or null) still deserves an answer rather than a crash. */
type MaybeApiError = { code?: unknown; values?: unknown; message?: unknown };

/* Handed to i18next as the defaultValue so a missing key is unmistakable.
   Deliberately not a sentence and not empty: it has to be something no
   translation in either language could ever equal by accident, and something
   that is obviously wrong if it ever does reach a screen. */
const MISS = "::apiError-miss::";

/* Values that are WORDS, not numbers, and so need translating before they are
   interpolated.

   Every other code sends a ceiling or an amount, which goes straight into the
   template. The contact guard sends a list of kinds and a surface — tokens
   naming a concept, not values — and a French sentence needs French nouns and
   a French "et" in the right place. Composing that in Python was impossible
   (the backend does not know the reader's language) and composing it inside
   the template is impossible too (a template interpolates, it does not join).
   So one small step in between, keyed by code.

   PREPARE is a map rather than a branch so the next code that needs this adds
   an entry instead of an `if`. If a code has no entry its values are passed
   through untouched, which is the case for all of them but this one. */
function contactDetails(values: Record<string, unknown>, t: Translate): Record<string, unknown> {
  const kinds = Array.isArray(values.kinds) ? values.kinds.map(String) : [];
  /* An unknown kind falls back to the token. It would be a backend that grew a
     fourth kind without telling anyone, and a stray English word beats a hole
     in the sentence. */
  const names = kinds.map((k) => t(`apiError.kind_${k}`, { defaultValue: k }));
  const last = names.pop() ?? "";
  const what = names.length ? `${names.join(", ")} ${t("apiError.list_and")} ${last}` : last;

  /* "proposal note" -> surface_proposal_note. The backend keeps the spaced
     form because it is also the noun in its own English sentence; normalising
     here is cheaper than carrying two spellings of the same token. */
  const raw = typeof values.surface === "string" ? values.surface : "";
  const surface = t(`apiError.surface_${raw.trim().replace(/\s+/g, "_")}`, { defaultValue: raw });

  return { what, surface };
}

const PREPARE: Record<string, (values: Record<string, unknown>, t: Translate) => Record<string, unknown>> = {
  contact_details_found: contactDetails
};

/* The sentence to show a human for a failed request.

   Order of preference, and the reasoning for each step:

     1. the localised sentence for the code, if the backend sent one and this
        file knows it;
     2. the backend's English `detail`, if there is one. Worse than French for
        a French reader, but it is SPECIFIC — "you have already submitted work
        and the brand has not answered" beats "something went wrong" even in
        the wrong language, because it says what to do next;
     3. the generic sentence, for a network failure or a response that was not
        JSON, where there is nothing specific to say.

   Step 2 is why this migration can be gradual and why it is safe: an
   un-migrated endpoint behaves exactly as it did before this file existed. */
export function errorText(err: unknown, t: Translate): string {
  const e = (err ?? {}) as MaybeApiError;

  if (typeof e.code === "string" && e.code) {
    const values = e.values && typeof e.values === "object" ? (e.values as Record<string, unknown>) : {};
    /* A sentinel rather than "" or the English text, because this has to
       distinguish "no sentence for that code" from "a sentence that happens
       to be falsy", and because i18next returns the KEY ITSELF on a miss —
       without a defaultValue an unknown code puts the literal string
       "apiError.deliverable_whatever" on a user's screen. MISS cannot collide
       with any translation, so an unknown code always falls through to the
       backend's English below, which is the whole reason this migration can
       be gradual. */
    const prepare = PREPARE[e.code];
    const ready = prepare ? prepare(values, t) : values;
    const text = t(`apiError.${e.code}`, { ...ready, defaultValue: MISS });
    if (text !== MISS && text) return text;
  }

  if (typeof e.message === "string" && e.message) return e.message;

  return t(GENERIC_KEY);
}

/* Copy for the notifications bell and the full history page, registered as a
   resource bundle so the 40 KB i18n.ts stays focused on the core app copy —
   the same arrangement the cart, the open board, the disputes queue, the
   admin console, the account settings and the two money screens use.

   nav.notifications is deep-merged into the group i18n.ts owns, exactly as
   nav.board is in boardStrings.ts: addResourceBundle runs with deep=true and
   overwrite=true, and main.tsx imports this after "./i18n", so the key joins
   the existing group rather than replacing it.

   notif.body.* are the localised NOTIFICATION BODIES. The backend stores a
   {key, ...values} in params and the client renders notif.body.<key> with the
   values interpolated (see notificationBody in notifications.ts). A row with
   no params — an old one, or a type not migrated yet — falls back to the
   English `message` the backend also emails, so a missing key is never blank.
   Only the migrated types are here; the rest keep appearing in English until
   their call sites carry params too. */
import i18n from "../i18n";

const body_fr = {
  escrow_funded_creator: "Des fonds sont bloqués en séquestre pour votre collaboration.",
  escrow_funded_brand: "Votre paiement est bloqué en séquestre.",
  escrow_released_creator: "Séquestre libéré, votre paiement est en route.",
  escrow_released_brand: "Séquestre libéré au créateur.",
  dispute_opened_other: "Un litige a été ouvert sur votre séquestre. Vous avez {{hours}} h pour répondre ou le résoudre avant qu'il ne soit transmis à l'équipe Kolabo.",
  dispute_opened_self: "Votre litige a été ouvert et le séquestre est gelé. L'autre partie a {{hours}} h pour répondre.",
  dispute_escalated_both: "Les deux parties ont répondu ; le litige a été transmis à l'équipe Kolabo pour décision.",
  dispute_escalated_stale: "Le délai de réponse de votre séquestre en litige est écoulé. L'équipe Kolabo va l'examiner et trancher.",
  dispute_reply: "L'autre partie a répondu sur votre séquestre en litige.",
  dispute_withdrawn: "Le litige a été retiré. Le séquestre est de nouveau bloqué et suit son calendrier de libération normal.",
  dispute_resolved_creator: "Votre litige a été tranché : {{payout}} {{currency}} vous sont versés et {{refunded}} {{currency}} ont été remboursés à la marque.",
  dispute_resolved_brand: "Votre litige a été tranché : {{refunded}} {{currency}} vous sont remboursés et {{released}} {{currency}} ont été versés au créateur.",
  contract_ready: "Un contrat est prêt à signer pour {{campaign}}.",
  contract_signed: "Votre contrat est entièrement signé.",
  contract_cancelled: "Un contrat que vous n'aviez pas fini de signer a été annulé par l'autre partie.",
  message_campaign: "Nouveau message à propos de la campagne {{campaign}}.",
  message_generic: "Vous avez un nouveau message."
};

const body_en = {
  escrow_funded_creator: "Funds are held in escrow for your collaboration.",
  escrow_funded_brand: "Your payment is held in escrow.",
  escrow_released_creator: "Escrow released, your payout is on the way.",
  escrow_released_brand: "Escrow released to the creator.",
  dispute_opened_other: "A dispute was opened on your escrow. You have {{hours}} hours to answer or resolve it before it goes to the Kolabo team.",
  dispute_opened_self: "Your dispute was opened and the escrow is frozen. The other party has {{hours}} hours to answer.",
  dispute_escalated_both: "Both parties have answered the dispute, so it has gone to the Kolabo team for a decision.",
  dispute_escalated_stale: "The response window on your disputed escrow has closed. The Kolabo team will now review it and decide.",
  dispute_reply: "The other party replied on your disputed escrow.",
  dispute_withdrawn: "The dispute was withdrawn. The escrow is held again and back on its normal release schedule.",
  dispute_resolved_creator: "Your dispute was decided: {{payout}} {{currency}} is on its way to you and {{refunded}} {{currency}} was refunded to the brand.",
  dispute_resolved_brand: "Your dispute was decided: {{refunded}} {{currency}} is being refunded to you and {{released}} {{currency}} was released to the creator.",
  contract_ready: "A contract is ready to sign for {{campaign}}.",
  contract_signed: "Your contract is fully signed.",
  contract_cancelled: "A contract you had not finished signing was cancelled by the other party.",
  message_campaign: "New message about the campaign {{campaign}}.",
  message_generic: "You have a new message."
};

const fr = {
  navAria: "Notifications, {{n}} non lue(s)",
  title: "Notifications",
  sub: "Tout ce que Kolabo vous a signalé, de la plus récente à la plus ancienne.",

  panelTitle: "Notifications",
  markAll: "Tout marquer comme lu",
  seeAll: "Voir tout l'historique",
  unreadMark: "Non lue",
  loading: "Chargement…",

  empty: "Aucune notification pour l'instant.",
  emptyHint: "Les invitations, les propositions, les contrats, les messages et les mouvements d'argent arrivent ici.",
  loadFailed: "Impossible de charger vos notifications pour l'instant.",

  /* Depuis le lien porté par la notification, un clic ouvre directement
     l'élément concerné quand il existe — le contrat, le litige, la
     conversation — et sinon l'écran correspondant. */
  routeNote: "Un clic ouvre directement l'élément concerné quand c'est possible — le contrat, le litige, la conversation — et sinon l'écran correspondant.",
  opensScreen: "Ouvre l'élément concerné",

  justNow: "à l'instant",
  minutesAgo: "il y a {{n}} min",
  hoursAgo: "il y a {{n}} h",
  daysAgo: "il y a {{n}} j",

  newer: "Plus récentes",
  older: "Plus anciennes",
  page: "Page {{n}}",
  /* Le serveur ne renvoie pas de total : on ne peut donc pas dire « page 3
     sur 7 », seulement qu'une page incomplète est la dernière. */
  pageEnd: "Vous êtes au bout de votre historique.",

  body: body_fr
};

const en = {
  navAria: "Notifications, {{n}} unread",
  title: "Notifications",
  sub: "Everything Kolabo has told you about, newest first.",

  panelTitle: "Notifications",
  markAll: "Mark all as read",
  seeAll: "See the full history",
  unreadMark: "Unread",
  loading: "Loading…",

  empty: "No notifications yet.",
  emptyHint: "Invitations, proposals, contracts, messages and money movements arrive here.",
  loadFailed: "Your notifications could not be loaded right now.",

  routeNote: "A click opens the item it is about when it can — the contract, the dispute, the conversation — otherwise the matching screen.",
  opensScreen: "Opens the item it is about",

  justNow: "just now",
  minutesAgo: "{{n}} min ago",
  hoursAgo: "{{n}} h ago",
  daysAgo: "{{n}} d ago",

  newer: "Newer",
  older: "Older",
  page: "Page {{n}}",
  pageEnd: "You have reached the end of your history.",

  body: body_en
};

i18n.addResourceBundle(
  "fr",
  "translation",
  { notif: fr, nav: { notifications: "Notifications" } },
  true,
  true
);
i18n.addResourceBundle(
  "en",
  "translation",
  { notif: en, nav: { notifications: "Notifications" } },
  true,
  true
);

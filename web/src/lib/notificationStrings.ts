/* Copy for the notifications bell and the full history page, registered as a
   resource bundle so the 40 KB i18n.ts stays focused on the core app copy —
   the same arrangement the cart, the open board, the disputes queue, the
   admin console, the account settings and the two money screens use.

   nav.notifications is deep-merged into the group i18n.ts owns, exactly as
   nav.board is in boardStrings.ts: addResourceBundle runs with deep=true and
   overwrite=true, and main.tsx imports this after "./i18n", so the key joins
   the existing group rather than replacing it.

   notif.body.* are the localised NOTIFICATION BODIES, and they live one file
   over in notificationBodies.ts — a module with no imports, so the test that
   compares the two languages (and checks them against the keys the backend
   actually emits) can read them without booting i18next. This file is the
   wiring: it hangs them off notif.body in both bundles. */
import i18n from "../i18n";
import { body_en, body_fr } from "./notificationBodies";

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
  routeNote: "Un clic ouvre directement l'élément concerné quand c'est possible (le contrat, le litige, la conversation) et sinon l'écran correspondant.",
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

  routeNote: "A click opens the item it is about when it can (the contract, the dispute, the conversation), otherwise the matching screen.",
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

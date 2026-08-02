/* Messaging strings, registered as a resource bundle so the main i18n file
   stays focused on the core app copy — the same arrangement the onboarding
   wizard, the marketing pages and the cart use. */
import i18n from "../i18n";

const fr = {
  nav: "Messages",
  navAria: "Messages, {{n}} non lu(s)",
  title: "Messages",
  /* The empty state says WHEN conversations open rather than apologising for
     having none. A thread exists only à côté d'un contrat, and somebody who
     does not know that reads an empty inbox as a broken feature. */
  empty: "Vos conversations s'ouvrent dès qu'un contrat est signé.",
  emptyHint: "Une conversation accompagne toujours un contrat : c'est ce qui en fait un espace de travail et non une boîte à prospection.",
  pick: "Choisissez une conversation.",
  noMessages: "Aucun message pour l'instant. Lancez la conversation.",
  placeholder: "Écrivez votre message",
  send: "Envoyer",
  you: "Vous",
  unknownParty: "Interlocuteur",
  openConversation: "Ouvrir la conversation",
  /* Une ligne, une PERSONNE. Le nombre de contrats est un fait sur la
     relation — « on a fait quatre jobs ensemble » — et pas un compteur
     technique : c'est précisément ce que l'ancienne liste, qui répétait le
     même nom quatre fois, rendait illisible. */
  contractsCount: "{{n}} contrats",
  contracts: "Contrats",
  /* Numérotés depuis le plus ancien, donc un nouveau contrat ne renumérote
     jamais les précédents. Le payload ne porte le titre de campagne que du
     plus récent, alors les autres sont nommés par leur rang plutôt que par un
     titre qu'il faudrait aller chercher contrat par contrat. */
  contractN: "Contrat {{n}}",
  contractCurrent: "en cours",
  justNow: "à l'instant",
  minutesAgo: "il y a {{n}} min",
  hoursAgo: "il y a {{n}} h",
  daysAgo: "il y a {{n}} j"
};

const en = {
  nav: "Messages",
  navAria: "Messages, {{n}} unread",
  title: "Messages",
  /* The empty state says WHEN conversations open rather than apologising for
     having none. A thread only ever exists alongside a contract, and somebody
     who does not know that reads an empty inbox as a broken feature. */
  empty: "Your conversations open as soon as a contract is signed.",
  emptyHint: "A conversation always sits alongside a contract: that is what keeps it a place of work rather than an inbox to prospect in.",
  pick: "Pick a conversation.",
  noMessages: "No messages yet. Start the conversation.",
  placeholder: "Write your message",
  send: "Send",
  you: "You",
  unknownParty: "Counterparty",
  openConversation: "Open the conversation",
  contractsCount: "{{n}} contracts",
  contracts: "Contracts",
  contractN: "Contract {{n}}",
  contractCurrent: "current",
  justNow: "just now",
  minutesAgo: "{{n}} min ago",
  hoursAgo: "{{n}} h ago",
  daysAgo: "{{n}} d ago"
};

i18n.addResourceBundle("fr", "translation", { msg: fr }, true, true);
i18n.addResourceBundle("en", "translation", { msg: en }, true, true);

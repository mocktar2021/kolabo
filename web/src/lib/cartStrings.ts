/* Cart strings, registered as a resource bundle so the main i18n file stays
   focused on the core app copy — the same arrangement the onboarding wizard
   and the marketing pages use. */
import i18n from "../i18n";

const fr = {
  nav: "Panier",
  navAria: "Panier, {{n}} article(s)",
  title: "Mon panier",
  add: "Ajouter au panier",
  added: "Ajouté au panier.",
  /* Said at the button, because the server would otherwise refuse the whole
     checkout for a line the buyer thought they had added. */
  full: "Votre panier contient déjà 20 articles. Commandez-les avant d'en ajouter d'autres.",
  view: "Voir mon panier ({{n}})",
  empty: "Votre panier est vide.",
  emptyCta: "Découvrir des créateurs",
  remove: "Retirer",
  custom: "Offre sur mesure",
  qty: "×{{n}}",
  days: "{{n}} j",
  note: "Note",
  subtotal: "Sous-total",
  total: "Total",

  /* NEUTRE, ET PAS « Créateur sans nom ». Une ligne ajoutée avant que le
     panier ne garde l'identité du créateur n'a pas de nom parce que personne
     ne l'a jamais demandé — pas parce que cette personne n'en a pas. Dire le
     contraire serait affirmer un fait qu'on n'a pas vérifié. */
  unknownCreator: "Créateur",

  /* Why there is no single grand total. */
  totalsNote: "Les devises ne sont jamais additionnées : chaque commande porte un séquestre, et un séquestre porte une seule devise.",
  mixedCurrency: "Ce créateur a des articles dans plusieurs devises. Une commande ne peut en porter qu'une : commandez chaque devise séparément.",
  checkout: "Commander tout le panier",
  rule: "Une commande par créateur. Chacun a 48 h pour accepter, et aucun paiement n'est prélevé avant son acceptation.",
  /* Shown with the error, because a buyer who reads "Article 3" and assumes
     the first two are ordered will order them une deuxième fois. */
  allOrNothing: "Le panier est validé en une seule fois : aucune commande n'a été créée.",
  lineRejected: "Article refusé",
  successTitle: "Commandes envoyées.",
  successRule: "Chaque créateur a 48 h pour répondre à la sienne.",
  viewOrder: "Voir la commande"
};

const en = {
  nav: "Cart",
  navAria: "Cart, {{n}} item(s)",
  title: "My cart",
  add: "Add to cart",
  added: "Added to the cart.",
  /* Said at the button, because the server would otherwise refuse the whole
     checkout for a line the buyer thought they had added. */
  full: "Your cart already holds 20 items. Order them before adding more.",
  view: "View my cart ({{n}})",
  empty: "Your cart is empty.",
  emptyCta: "Discover creators",
  remove: "Remove",
  custom: "Custom offer",
  qty: "×{{n}}",
  days: "{{n}} d",
  note: "Note",
  subtotal: "Subtotal",
  total: "Total",

  /* Neutral, and not "Unnamed creator": a line added before the cart kept the
     creator's identity has no name because nobody ever asked — not because
     that person has none. */
  unknownCreator: "Creator",

  /* Why there is no single grand total. */
  totalsNote: "Currencies are never added together: each order carries one escrow, and an escrow carries one currency.",
  mixedCurrency: "This creator has items in more than one currency. An order can only carry one: check out each currency separately.",
  checkout: "Order the whole cart",
  rule: "One order per creator. Each has 48 h to accept, and no payment is taken before they do.",
  /* Shown with the error, because a buyer who reads "Item 3" and assumes the
     first two went through will order them a second time. */
  allOrNothing: "The cart is checked out in one go: nothing was ordered.",
  lineRejected: "Item rejected",
  successTitle: "Orders sent.",
  successRule: "Each creator has 48 h to answer theirs.",
  viewOrder: "View the order"
};

i18n.addResourceBundle("fr", "translation", { cart: fr }, true, true);
i18n.addResourceBundle("en", "translation", { cart: en }, true, true);

import i18n from "../i18n";

/* Copy for the basket and for the custom-terms panel on a creator's
   storefront — the two things the phone could not do that the browser could.

   REGISTERED AT RUNTIME, like paymentStrings.ts, packageStrings.ts and
   parityStrings.ts, and for the same reason: src/strings.ts is 60 KB and a
   forty-key change lands in it invisibly. The consequence is the thing to
   remember — every screen using a key below must import this module FOR ITS
   SIDE EFFECT or it renders the raw key at the reader. Three do: CartScreen,
   CreatorPublicScreen and HeaderCart (through CartScreen's own import, which
   RootNavigator pulls in at module load before any header renders).

   TWO GROUPS IN ONE FILE because they are one change: the basket, and the
   only way into it that is not a listed pack. The keys are deep-merged into
   the cart.* and public.* groups (addResourceBundle runs with deep=true and
   overwrite=true), so the public.* additions sit beside the order copy
   strings.ts already owns without disturbing it.

   THE WORD IS "PACK", NOT "OFFRE". Web calls a creator's listed bundle an
   offre; this client has said pack since packageStrings.ts
   (profile.packagesTitle = "Packs"), and a third word for one thing is worse
   than either. So the sentences below say pack where they name one — and say
   "sur mesure" for a line that is not one, which is a different noun on
   purpose.

   NO SUM ACROSS CURRENCIES ANYWHERE IN THIS COPY, and totalsNote says why out
   loud: a buyer who can see two totals and no grand total will otherwise
   assume the screen forgot to add them up.

   French first, like the other bundles: three of the five launch markets are
   francophone. */

const fr = {
  cart: {
    title: "Mon panier",
    nav: "Panier",
    navAria: "Panier, {{n}} article(s)",

    add: "Ajouter au panier",
    added: "Ajouté au panier.",
    /* Dit au bouton, parce que le serveur refuserait sinon la totalité de la
       commande pour une ligne que l'acheteur croyait avoir ajoutée. */
    full: "Votre panier contient déjà 20 articles. Commandez-les avant d'en ajouter d'autres.",
    view: "Voir mon panier ({{n}})",

    empty: "Votre panier est vide.",
    emptyCta: "Découvrir des créateurs",
    loading: "Chargement du panier...",

    remove: "Retirer",
    /* Pas un pack : des conditions que l'acheteur a nommées lui-même. Le mot
       est différent exprès. */
    custom: "Sur mesure",
    qty: "×{{n}}",
    days: "{{n}} j",
    note: "Note",

    subtotal: "Sous-total",
    total: "Total",
    totalSelected: "Total de la sélection",
    /* Pourquoi il n'y a pas de total unique. */
    totalsNote: "Les devises ne sont jamais additionnées : chaque commande porte un séquestre, et un séquestre porte une seule devise.",
    mixedCurrency: "Ce créateur a des articles dans plusieurs devises. Une commande ne peut en porter qu'une : commandez chaque devise séparément.",

    /* NEUTRE, ET PAS « Créateur sans nom ». Une ligne ajoutée avant que le
       panier ne garde l'identité du créateur n'a pas de nom parce que
       personne ne l'a jamais demandé, pas parce que cette personne n'en a
       pas. */
    unknownCreator: "Créateur",

    /* La sélection se fait par créateur, jamais par ligne : l'unité que le
       serveur crée est la commande d'un créateur. */
    selectGroup: "Inclure {{name}} dans la commande",
    selectedCount: "{{n}} créateur(s) sélectionné(s) sur {{total}}",
    selectAll: "Tout sélectionner",
    selectNone: "Tout désélectionner",
    noneSelected: "Sélectionnez au moins un créateur pour commander.",
    groupExcluded: "Ce créateur ne sera pas commandé cette fois. Il reste dans votre panier.",
    selectionNote: "Le panier est envoyé en une seule fois : décocher un créateur ne commande pas la moitié du panier, cela l'envoie sans lui. Ce qui n'est pas coché reste dans votre panier.",

    checkout: "Commander tout le panier",
    checkoutSelected: "Commander la sélection ({{n}})",
    rule: "Une commande par créateur. Chacun a 48 h pour accepter, et aucun paiement n'est prélevé avant son acceptation.",
    /* Affiché avec l'erreur, parce qu'un acheteur qui lit « Article 3 » et
       suppose que les deux premiers sont passés les commandera une
       deuxième fois. */
    allOrNothing: "Le panier est validé en une seule fois : aucune commande n'a été créée.",
    lineRejected: "Article refusé",

    successTitle: "Commandes envoyées.",
    successRule: "Chaque créateur a 48 h pour répondre à la sienne.",
    viewOrder: "Voir la commande",
    remaining: "Il reste {{n}} article(s) dans votre panier.",
    backToCart: "Revenir au panier",

    /* Le panier est réservé au côté acheteur, comme l'API (403). Les points
       d'entrée n'existent pas pour un créateur ; cet écran le dit quand même,
       parce qu'un écran vide sans explication se lit comme une panne. */
    brandsOnly: "Le panier est réservé aux marques et aux agences.",
  },

  public: {
    /* Le point d'entrée qui manquait : la façon de proposer ses propres
       conditions quand aucun pack publié ne correspond. Secondaire exprès —
       le prix affiché reste le chemin rapide — mais présent, parce que ces
       accords-là se concluaient sur WhatsApp. */
    negotiate: "Proposer mes conditions",
    negotiateOr: "ou",
    negotiateTitle: "Vos conditions",
    negotiatePlatform: "Plateforme",
    negotiateDeliverable: "Livrable",
    negotiateQuantity: "Quantité",
    negotiatePrice: "Prix proposé",
    negotiateDays: "Délai (jours)",
    negotiateFloor: "Prix minimum : {{n}} {{currency}}.",
    negotiateSend: "Envoyer l'offre",
  },
};

const en = {
  cart: {
    title: "My cart",
    nav: "Cart",
    navAria: "Cart, {{n}} item(s)",

    add: "Add to cart",
    added: "Added to the cart.",
    full: "Your cart already holds 20 items. Order them before adding more.",
    view: "View my cart ({{n}})",

    empty: "Your cart is empty.",
    emptyCta: "Discover creators",
    loading: "Loading your cart...",

    remove: "Remove",
    custom: "Custom terms",
    qty: "×{{n}}",
    days: "{{n}} d",
    note: "Note",

    subtotal: "Subtotal",
    total: "Total",
    totalSelected: "Selected total",
    totalsNote: "Currencies are never added together: each order carries one escrow, and an escrow carries one currency.",
    mixedCurrency: "This creator has items in more than one currency. An order can only carry one: check out each currency separately.",

    unknownCreator: "Creator",

    selectGroup: "Include {{name}} in the order",
    selectedCount: "{{n}} of {{total}} creators selected",
    selectAll: "Select all",
    selectNone: "Deselect all",
    noneSelected: "Select at least one creator to order.",
    groupExcluded: "This creator will not be ordered this time. They stay in your cart.",
    selectionNote: "The cart is sent in one go: unticking a creator does not order half the cart, it sends the cart without them. Whatever is unticked stays in your cart.",

    checkout: "Order the whole cart",
    checkoutSelected: "Order the selection ({{n}})",
    rule: "One order per creator. Each has 48 h to accept, and no payment is taken before they do.",
    allOrNothing: "The cart is checked out in one go: nothing was ordered.",
    lineRejected: "Item rejected",

    successTitle: "Orders sent.",
    successRule: "Each creator has 48 h to answer theirs.",
    viewOrder: "View the order",
    remaining: "{{n}} item(s) still in your cart.",
    backToCart: "Back to the cart",

    brandsOnly: "The cart is for brands and agencies.",
  },

  public: {
    negotiate: "Propose my own terms",
    negotiateOr: "or",
    negotiateTitle: "Your terms",
    negotiatePlatform: "Platform",
    negotiateDeliverable: "Deliverable",
    negotiateQuantity: "Quantity",
    negotiatePrice: "Your price",
    negotiateDays: "Timeline (days)",
    negotiateFloor: "Minimum price: {{n}} {{currency}}.",
    negotiateSend: "Send the offer",
  },
};

i18n.addResourceBundle("fr", "translation", fr, true, true);
i18n.addResourceBundle("en", "translation", en, true, true);

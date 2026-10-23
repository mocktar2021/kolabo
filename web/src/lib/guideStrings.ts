/* THE USER GUIDE, AND ONLY ITS WORDS. The outline, the numbering and the
   anchors live in pages/Guide.tsx, exactly as the legal documents keep their
   outline in pages/LegalPage.tsx and their sentences in lib/legalStrings.ts.
   Owns the guide.* group outright, so it carries no ordering constraint in
   main.tsx.

   WRITTEN AGAINST THE CODE, NOT AGAINST THE BRIEF. That is the rule this file
   is held to, and it is why several sections are narrower than the product
   description would suggest:

   Facebook is the only network a creator can CONNECT. socialPlatforms.ts sets
   canConnect on one entry and the backend registers one provider, so the
   guide says one. Eight networks can be declared by typing a handle, which is
   a different thing, and the guide says that too rather than blurring them.

   Discover has four filters: category, country, platform, minimum followers.
   Not price, not city, not verified, not availability. The guide names four.

   A phone number is never verified. It is optional, it lives on the account
   screen, and it is the Mobile Money destination. No step here asks anybody
   to verify one, because no screen does.

   THE COUNTRIES ANSWER IS TIED TO PAYMENTS, not to a pilot. It named a two
   country pilot for weeks after four markets were open, because nothing
   connects a sentence here to the list in lib/countries.ts. A country opens
   when money can move there, so the sentence says that and stops going stale
   every time the gateway adds a market.

   NO COMMISSION PERCENTAGE. Not one user-facing string in this product states
   a figure, in either language, and this file does not become the first place
   it appears. The guide describes the mechanism, which the Terms and the
   earnings screen already describe the same way: the commission comes off the
   amount released to the creator, never off what the brand pays. Publishing a
   rate is a founder decision and it belongs in the pricing page and the Terms
   at the same time, not here alone.

   NO SUPPORT ADDRESS EITHER, and for a different reason. It used to be here,
   as faq.contactLink, in both language blocks. An address is a fact rather
   than a sentence: there is nothing in it to translate, a translator can
   mis-type it, and holding it in two places is how one of them goes stale.
   The sentence inviting somebody to write in is still copy and is still here;
   the address itself lives in lib/support.ts and pages/Guide.tsx renders it.

   THE NUMBERS THAT ARE STATED are the ones the interface already states, so
   there is one source for each: 8 characters for a password, a 6 digit code,
   48 hours for a creator to accept an order, 4 days for a brand to review a
   deliverable, 72 hours to answer a dispute. If one of those changes in the
   code it has to change here, and the guide section that carries it is named
   in the test that guards the catalogue.

   NO EM DASH AND NO EN DASH, like every other bundle: punctuation.test.ts
   walks web/src and reads the string literals. The narrow no-break spaces
   before colons are written as escapes so they are visible in a diff. */
import i18n from "../i18n";

const fr = {
  title: "Guide d'utilisation",
  sub: "Comment utiliser Kolabo, rôle par rôle. Le sommaire mène directement à une section si vous cherchez une réponse précise.",
  tocTitle: "Sommaire",
  scope: "Ce guide décrit le site. Les applications Android et iOS suivent les mêmes étapes, avec les mêmes règles.",

  creator: {
    title: "Créateur",
    intro: "Vous avez une audience et vous voulez travailler avec des marques. Voici le chemin complet, de la création du compte au versement sur votre portefeuille Mobile Money.",

    accountTitle: "Créer votre compte",
    account1: "Ouvrez Créer un compte et choisissez Créateur.",
    account2: "Choisissez votre pays, puis saisissez votre adresse e-mail et un mot de passe de 8 caractères au moins.",
    account3: "Nous envoyons un code à 6 chiffres à cette adresse. Saisissez-le pour activer votre compte.",
    accountGoogle: "Vous pouvez aussi utiliser Continuer avec Google. Kolabo vous demandera ensuite votre rôle et votre pays, que Google ne connaît pas.",
    accountNote: "Le code expire, il ne fonctionne qu'une fois, et un code erroné coûte une tentative. Si rien n'arrive au bout de quelques minutes, regardez dans vos courriers indésirables, puis demandez un nouveau code.",

    profileTitle: "Votre profil",
    profileIntro: "Votre profil est votre vitrine. C'est ce qu'une marque lit avant de vous écrire, et c'est sur lui que s'appuient ses filtres de recherche.",
    profile1: "Votre nom public et une courte présentation.",
    profile2: "Votre pays et votre ville.",
    profile3: "Vos catégories, par exemple Mode, Beauté, Tech ou Cuisine.",
    profile4: "Votre photo de profil.",
    profile5: "Votre portfolio, c'est à dire les contenus que vous montrez en premier.",
    profileNote: "Une marque filtre par catégorie, par pays, par plateforme et par nombre d'abonnés. Un profil sans catégorie et sans réseau ne ressort d'aucun de ces filtres.",

    socialTitle: "Vos réseaux sociaux",
    social1: "Vous déclarez un réseau en saisissant votre nom d'utilisateur. Huit réseaux sont acceptés : Instagram, TikTok, YouTube, Facebook, X, Snapchat, LinkedIn et WhatsApp.",
    social2: "Facebook est le seul réseau que vous pouvez connecter aujourd'hui, et connecter n'est pas la même chose que déclarer : la connexion lit votre nombre d'abonnés directement depuis le réseau, ce qu'une saisie à la main ne fait pas. Les autres connexions arriveront.",
    socialNote: "WhatsApp ne porte pas d'audience publique, donc aucun nombre d'abonnés ne lui est attaché.",

    packagesTitle: "Vos offres",
    packages1: "Une offre est ce qu'une marque commande. Elle porte un titre, un prix et un délai de livraison.",
    packages2: "Une offre peut être active ou inactive. Une offre inactive reste sur votre profil sans pouvoir être commandée. Quand vous n'êtes pas disponible, désactivez plutôt que de supprimer : vous garderez le texte et le prix pour la prochaine fois.",

    workTitle: "Trouver du travail",
    workIntro: "Trois chemins, et ils ne s'excluent pas.",
    work1: "Une commande directe. Une marque choisit une offre sur votre profil et la commande. Vous avez 48 heures pour accepter. Sans réponse, la commande expire, et rien n'a été prélevé.",
    work2: "Une invitation. Une marque vous écrit depuis sa campagne. Vous les trouvez dans Invitations.",
    work3: "Un brief ouvert. Une campagne publiée à laquelle vous pouvez répondre sans avoir été invité. Vous les trouvez dans Briefs.",
    workNegotiate: "Dans les trois cas vous pouvez accepter, refuser, ou proposer un autre prix et un autre délai. Chaque tour de négociation reste dans le fil avec sa date, donc personne ne discute de mémoire.",

    contractTitle: "Le contrat",
    contract1: "Dès que vous acceptez, un contrat est créé, et les deux parties le signent.",
    contract2: "Une fois les deux signatures posées, la marque bloque l'argent en séquestre. Kolabo le détient. Il n'est plus à la marque et il n'est pas encore à vous.",
    contractNote: "Ne commencez pas avant que le séquestre soit financé. La page du contrat vous dit où il en est, et la section des livrables reste fermée tant que l'argent n'est pas bloqué.",

    deliverTitle: "Remettre le travail",
    deliver1: "Ouvrez le contrat et allez à Livrables.",
    deliver2: "Ajoutez le lien de la publication, un fichier, ou les deux. L'un des deux suffit, mais il en faut au moins un.",
    deliver3: "Cliquez sur Envoyer pour validation.",
    deliverWindow: "La marque est prévenue et dispose de 4 jours pour répondre. Sans réponse de sa part dans ce délai, l'argent vous est libéré automatiquement. Chaque nouvelle remise fait repartir les 4 jours.",
    deliverWithdraw: "Tant que la marque n'a pas répondu, vous pouvez retirer votre livrable et en remettre un autre.",
    deliverChanges: "La marque peut aussi demander des modifications. Cela ne débloque pas l'argent et n'ouvre pas de litige : le séquestre reste en place et vous remettez une nouvelle version.",

    paidTitle: "Être payé",
    paid1: "Renseignez votre moyen de versement avant la fin du travail. Sans lui, votre argent peut être libéré, visible et à vous, sans pouvoir partir.",
    paid2: "Le formulaire demande votre pays, votre réseau Mobile Money et le numéro qui recevra l'argent. Les réseaux proposés dépendent du pays : MTN Mobile Money, Moov Money, Celtiis Cash, T-Money, Wave et Orange Money.",
    paidNote: "Si un paiement vous attend et que ce formulaire est vide, Kolabo vous envoie une notification qui mène directement à lui.",
    paid3: "Vos montants sont nets. La commission Kolabo est déduite au moment où l'argent vous est libéré, jamais avant. Le relevé de vos gains montre, pour chaque ligne, le brut, la commission et le net, pour que rien ne soit seulement soustrait.",

    disputeTitle: "En cas de désaccord",
    dispute1: "Si ce qui est attendu et ce qui est remis ne se rejoignent pas, l'une des deux parties peut ouvrir un litige depuis la page du contrat. L'argent reste en séquestre pendant ce temps.",
    dispute2: "La partie qui n'a pas ouvert le litige a 72 heures pour répondre. Sans réponse dans ce délai, le dossier passe à l'équipe Kolabo, qui l'examine.",
    disputeNote: "Demander des modifications et ouvrir un litige sont deux choses différentes. La première est une étape normale du travail. La seconde est une réclamation sur l'argent."
  },

  brand: {
    title: "Entreprise et agence",
    intro: "Vous cherchez des créateurs pour une campagne. Voici le chemin complet, de la recherche au paiement du créateur.",

    accountTitle: "Créer votre compte",
    account1: "Ouvrez Créer un compte et choisissez Entreprise, ou Agence si vous gérez des campagnes pour des clients.",
    account2: "Choisissez votre pays, puis saisissez votre adresse e-mail et un mot de passe de 8 caractères au moins.",
    account3: "Saisissez le code à 6 chiffres reçu par e-mail.",
    accountNote: "Une agence achète exactement comme une entreprise. Le rôle change ce que Kolabo vous montre, pas ce que vous pouvez faire.",

    findTitle: "Trouver des créateurs",
    find1: "La recherche est gratuite et ne demande aucun compte. Le compte ne sert qu'à commander.",
    find2: "Sur Découvrir, quatre filtres réduisent la liste : la catégorie, le pays, la plateforme et le nombre minimum d'abonnés. Puis Rechercher.",
    find3: "Une fois connecté, vous pouvez enregistrer un créateur pour le retrouver plus tard.",

    orderTitle: "Commander une offre",
    order1: "Ouvrez le profil du créateur et lisez ses offres.",
    order2: "Choisissez une offre et ajoutez-la à votre panier.",
    order3: "Dans Mon panier, vérifiez votre sélection, puis commandez.",
    orderRule: "Le panier passe une commande par créateur. Chaque créateur a 48 heures pour accepter la sienne, et aucun paiement n'est prélevé avant son acceptation.",
    orderNote: "Les devises ne sont jamais additionnées, parce qu'une commande porte un séquestre et qu'un séquestre porte une seule devise. Si un même créateur a des articles dans deux devises, faites deux commandes.",

    briefTitle: "Publier un brief",
    brief1: "Au lieu de choisir les créateurs un par un, vous pouvez publier une campagne et les laisser venir à vous.",
    brief2: "Une campagne publiée apparaît dans les briefs ouverts, où les créateurs peuvent y répondre. Vous pouvez aussi inviter des créateurs précis depuis la page de la campagne.",
    brief3: "Les réponses arrivent comme des propositions sur votre campagne. Vous acceptez, vous refusez, ou vous négociez le prix et le délai.",

    signTitle: "Le contrat",
    sign1: "Une offre acceptée devient un contrat, et les deux parties le signent avant que l'argent entre en jeu.",

    payTitle: "Payer",
    payIntro: "Le bouton de paiement n'apparaît qu'une fois les deux signatures posées.",
    pay1: "Sur la page du contrat, cliquez sur Financer le séquestre.",
    pay2: "Kolabo vous emmène sur la page sécurisée de son prestataire de paiement, hors de l'application.",
    pay3: "Validez le paiement sur votre téléphone, par Mobile Money.",
    pay4: "Revenez sur Kolabo. La page se met à jour toute seule dès que le paiement est confirmé.",
    payAfter: "Votre argent est alors en séquestre. Le créateur est prévenu et peut commencer. Vous ne lui avez encore rien versé.",
    payNote: "Les paiements en ligne ne sont pas encore ouverts dans tous les pays. Si c'est le cas du vôtre, la page de paiement vous le dit au lieu de vous laisser essayer.",

    reviewTitle: "Valider la livraison",
    reviewIntro: "Quand le créateur remet son travail, vous êtes prévenu, et vous avez deux réponses possibles.",
    review1: "Valider et payer. Le séquestre est libéré immédiatement et le paiement part au créateur. C'est irréversible, et la page vous le dit avant le clic.",
    review2: "Demander des modifications. Vous expliquez ce qui manque, le séquestre reste en place, et le créateur remet une nouvelle version. Ce n'est pas un litige.",
    reviewWindow: "Vous avez 4 jours pour répondre. Sans réponse de votre part dans ce délai, le séquestre est libéré automatiquement au créateur. Chaque nouvelle remise fait repartir les 4 jours.",
    reviewNote: "Il n'existe pas de bouton pour libérer l'argent séparément. Libérer, c'est valider un travail remis, pour que l'argent et le travail ne puissent jamais raconter deux histoires différentes.",

    spendTitle: "Suivre vos dépenses",
    spend1: "Votre page de paiements montre ce que vous avez dépensé, ce qui est en attente, ce qui est en litige et ce qui a été remboursé, avec un relevé ligne par ligne.",
    spend2: "Aucun de ces montants n'est amputé d'une commission. La commission Kolabo est prélevée sur ce que le créateur reçoit, jamais sur ce que vous payez. Ce que vous voyez là est ce qui est parti de votre portefeuille.",

    disputeTitle: "En cas de désaccord",
    dispute1: "Si le travail remis ne correspond pas au contrat, ouvrez un litige depuis la page du contrat. L'argent reste en séquestre.",
    dispute2: "La partie qui n'a pas ouvert le litige a 72 heures pour répondre. Sans réponse dans ce délai, le dossier passe à l'équipe Kolabo, qui l'examine."
  },

  faq: {
    title: "Questions fréquentes",

    passwordTitle: "J'ai oublié mon mot de passe",
    password1: "Sur la page de connexion, cliquez sur Mot de passe oublié.",
    password2: "Saisissez votre adresse e-mail. Nous y envoyons un code à six chiffres.",
    password3: "Saisissez le code, puis votre nouveau mot de passe deux fois. Il lui faut 8 caractères au moins.",

    menuTitle: "Où sont mon compte et la langue",
    menu1: "En haut à droite. Le bouton qui porte votre photo ouvre votre profil, votre argent, les réglages de votre compte et la déconnexion.",
    menu2: "Le choix FR et EN est dans la barre du haut. Votre choix est enregistré : il tient après un rafraîchissement, dans un autre onglet et le lendemain.",

    commissionTitle: "La commission Kolabo",
    commission1: "Kolabo prélève une commission sur le montant libéré au créateur. Elle ne s'ajoute pas au prix : la marque paie le prix convenu, et la commission sort de la part du créateur au moment du versement.",
    commission2: "Le relevé des gains du créateur montre le brut, la commission et le net pour chaque ligne. Les conditions d'utilisation décrivent la règle complète, remboursements compris.",

    countriesTitle: "Pays et moyens de paiement",
    countries1: "Kolabo est ouvert au Bénin, au Togo, en Côte d'Ivoire et au Sénégal. D'autres pays s'ajouteront à mesure que les paiements y deviennent possibles.",
    countries2: "Les paiements et les versements passent par Mobile Money, et les réseaux disponibles dépendent du pays.",

    timelineTitle: "Quand suis-je payé",
    timeline1: "Le jour où la marque valide votre livrable, ou au plus tard 4 jours après votre remise si elle ne répond pas. Le versement part ensuite vers le numéro Mobile Money de votre moyen de versement.",
    timeline2: "Si ce moyen de versement est vide, l'argent est à vous mais il attend. Renseignez-le pour que le versement puisse partir.",

    deleteTitle: "Supprimer mon compte",
    delete1: "Ouvrez les réglages de votre compte. La suppression s'y trouve.",
    delete2: "Ce qui est effacé et ce qui doit être conservé est décrit dans la politique de confidentialité, parce qu'un contrat signé et un paiement sont aussi des pièces comptables.",

    contactTitle: "Nous écrire",
    contact1: "Une question à laquelle cette page ne répond pas, un compte bloqué, un paiement qui n'arrive pas : écrivez-nous et nous vous répondrons."
  }
};

const en = {
  title: "User guide",
  sub: "How to use Kolabo, role by role. The contents list goes straight to a section if you are after one answer.",
  tocTitle: "Contents",
  scope: "This guide describes the website. The Android and iOS apps follow the same steps, under the same rules.",

  creator: {
    title: "Creator",
    intro: "You have an audience and you want to work with brands. Here is the whole path, from creating the account to the money arriving in your Mobile Money wallet.",

    accountTitle: "Create your account",
    account1: "Open Create an account and choose Creator.",
    account2: "Choose your country, then enter your email address and a password of at least 8 characters.",
    account3: "We send a 6 digit code to that address. Enter it to activate your account.",
    accountGoogle: "You can also use Continue with Google. Kolabo then asks for your role and your country, which Google does not know.",
    accountNote: "The code expires, it works only once, and a wrong code costs an attempt. If nothing arrives after a few minutes, look in your junk mail, then ask for a new code.",

    profileTitle: "Your profile",
    profileIntro: "Your profile is your storefront. It is what a brand reads before writing to you, and it is what their search filters work on.",
    profile1: "Your public name and a short introduction.",
    profile2: "Your country and your city.",
    profile3: "Your categories, for instance Fashion, Beauty, Tech or Food.",
    profile4: "Your profile photo.",
    profile5: "Your portfolio, meaning the work you want seen first.",
    profileNote: "A brand filters by category, by country, by platform and by follower count. A profile with no category and no social account comes back from none of those filters.",

    socialTitle: "Your social accounts",
    social1: "You declare an account by typing your username. Eight networks are accepted: Instagram, TikTok, YouTube, Facebook, X, Snapchat, LinkedIn and WhatsApp.",
    social2: "Facebook is the only network you can connect today, and connecting is not the same as declaring: a connection reads your follower count from the network itself, which a typed number does not. The other connections are coming.",
    socialNote: "WhatsApp carries no public audience, so no follower count is attached to it.",

    packagesTitle: "Your packages",
    packages1: "A package is the thing a brand orders. It carries a title, a price and a delivery time.",
    packages2: "A package can be active or inactive. An inactive one stays on your profile but cannot be ordered. When you are not available, deactivate rather than delete: you keep the wording and the price for next time.",

    workTitle: "Finding work",
    workIntro: "Three routes, and they do not exclude each other.",
    work1: "A direct order. A brand picks a package on your profile and orders it. You have 48 hours to accept. With no answer the order expires, and nothing was charged.",
    work2: "An invitation. A brand writes to you from its campaign. You find these under Invitations.",
    work3: "An open brief. A published campaign you can answer without having been invited. You find these under Briefs.",
    workNegotiate: "In all three you can accept, decline, or propose a different price and a different delivery time. Every round of the negotiation stays in the thread with its date, so nobody argues from memory.",

    contractTitle: "The contract",
    contract1: "The moment you accept, a contract is created, and both parties sign it.",
    contract2: "Once both signatures are in, the brand holds the money in escrow. Kolabo holds it. It is no longer the brand's and it is not yet yours.",
    contractNote: "Do not start before the escrow is funded. The contract page tells you where it stands, and the deliverables section stays shut until the money is held.",

    deliverTitle: "Submitting the work",
    deliver1: "Open the contract and go to Deliverables.",
    deliver2: "Add the link to the post, a file, or both. Either one is enough, but you need at least one.",
    deliver3: "Click Send for review.",
    deliverWindow: "The brand is notified and has 4 days to answer. With no answer from them in that time the money is released to you automatically. Every new submission restarts the 4 days.",
    deliverWithdraw: "For as long as the brand has not answered, you can withdraw your deliverable and submit another.",
    deliverChanges: "The brand can also request changes. That does not unlock the money and does not open a dispute: the escrow stays where it is and you submit a new version.",

    paidTitle: "Getting paid",
    paid1: "Fill in your payout method before the work ends. Without it your money can be released, visible and yours, with no way to leave.",
    paid2: "The form asks for your country, your Mobile Money network and the number that will receive the money. The networks on offer depend on the country: MTN Mobile Money, Moov Money, Celtiis Cash, T-Money, Wave and Orange Money.",
    paidNote: "If a payment is waiting and that form is empty, Kolabo sends you a notification that leads straight to it.",
    paid3: "Your figures are net. The Kolabo commission comes off at the moment the money is released to you, never before. Your earnings statement shows gross, commission and net on every line, so nothing is merely subtracted.",

    disputeTitle: "When you disagree",
    dispute1: "If what was expected and what was delivered do not meet, either party can open a dispute from the contract page. The money stays in escrow while that runs.",
    dispute2: "The party who did not open the dispute has 72 hours to answer. With no answer in that time the case goes to the Kolabo team, who review it.",
    disputeNote: "Requesting changes and opening a dispute are different things. The first is an ordinary step in the work. The second is a claim on the money."
  },

  brand: {
    title: "Business and agency",
    intro: "You are looking for creators for a campaign. Here is the whole path, from the search to paying the creator.",

    accountTitle: "Create your account",
    account1: "Open Create an account and choose Business, or Agency if you run campaigns for clients.",
    account2: "Choose your country, then enter your email address and a password of at least 8 characters.",
    account3: "Enter the 6 digit code sent to you by email.",
    accountNote: "An agency buys exactly as a business does. The role changes what Kolabo shows you, not what you are allowed to do.",

    findTitle: "Finding creators",
    find1: "Searching is free and needs no account. The account is only for ordering.",
    find2: "On Discover, four filters narrow the list: category, country, platform and minimum followers. Then Search.",
    find3: "Once signed in you can save a creator to find them again later.",

    orderTitle: "Ordering a package",
    order1: "Open the creator's profile and read their packages.",
    order2: "Choose one and add it to your cart.",
    order3: "In My cart, check your selection, then order.",
    orderRule: "The cart places one order per creator. Each creator has 48 hours to accept theirs, and nothing is charged before they do.",
    orderNote: "Currencies are never added together, because an order carries one escrow and an escrow carries one currency. If one creator has items in two currencies, place two orders.",

    briefTitle: "Publishing a brief",
    brief1: "Instead of picking creators one by one, you can publish a campaign and let them come to you.",
    brief2: "A published campaign appears in the open briefs, where creators can answer it. You can also invite particular creators from the campaign page.",
    brief3: "Answers arrive as proposals on your campaign. You accept, you decline, or you negotiate the price and the delivery time.",

    signTitle: "The contract",
    sign1: "An accepted offer becomes a contract, and both parties sign it before money enters the picture.",

    payTitle: "Paying",
    payIntro: "The payment button only appears once both signatures are in.",
    pay1: "On the contract page, click Fund escrow.",
    pay2: "Kolabo takes you to its payment provider's secure page, outside the app.",
    pay3: "Approve the payment on your handset, by Mobile Money.",
    pay4: "Come back to Kolabo. The page updates itself as soon as the payment is confirmed.",
    payAfter: "Your money is then in escrow. The creator is notified and can start. You have paid them nothing yet.",
    payNote: "Online payments are not open in every country yet. Where yours is one of them, the payment page says so rather than letting you try.",

    reviewTitle: "Approving the delivery",
    reviewIntro: "When the creator submits the work you are notified, and you have two possible answers.",
    review1: "Approve and pay. The escrow is released at once and the payment goes to the creator. This cannot be undone, and the page says so before the click.",
    review2: "Request changes. You say what is missing, the escrow stays where it is, and the creator submits a new version. This is not a dispute.",
    reviewWindow: "You have 4 days to answer. With no answer from you in that time the escrow is released to the creator automatically. Every new submission restarts the 4 days.",
    reviewNote: "There is no separate button for releasing the money. Releasing is approving submitted work, so that the money and the work can never tell two different stories.",

    spendTitle: "Following your spend",
    spend1: "Your payments page shows what you have spent, what is pending, what is in dispute and what was refunded, with a line by line statement.",
    spend2: "None of those figures has a commission taken off. The Kolabo commission comes out of what the creator receives, never out of what you pay. What you see there is what left your wallet.",

    disputeTitle: "When you disagree",
    dispute1: "If the submitted work does not match the contract, open a dispute from the contract page. The money stays in escrow.",
    dispute2: "The party who did not open the dispute has 72 hours to answer. With no answer in that time the case goes to the Kolabo team, who review it."
  },

  faq: {
    title: "Common questions",

    passwordTitle: "I forgot my password",
    password1: "On the sign in page, click Forgot password.",
    password2: "Enter your email address. We send a six digit code to it.",
    password3: "Enter the code, then your new password twice. It needs at least 8 characters.",

    menuTitle: "Where are my account and the language",
    menu1: "Top right. The button carrying your photo opens your profile, your money, your account settings and sign out.",
    menu2: "The FR and EN choice is in the top bar. Your choice is written down: it holds after a refresh, in another tab and tomorrow.",

    commissionTitle: "The Kolabo commission",
    commission1: "Kolabo takes a commission on the amount released to the creator. It is not added to the price: the brand pays the agreed price, and the commission comes out of the creator's share at payout.",
    commission2: "The creator's earnings statement shows gross, commission and net on every line. The terms of service describe the full rule, refunds included.",

    countriesTitle: "Countries and payment methods",
    countries1: "Kolabo is open in Benin, Togo, Cote d'Ivoire and Senegal. Other countries are added as payments become possible there.",
    countries2: "Payments and payouts run on Mobile Money, and the available networks depend on the country.",

    timelineTitle: "When do I get paid",
    timeline1: "The day the brand approves your deliverable, or at the latest 4 days after you submitted it if they do not answer. The payout then goes to the Mobile Money number on your payout method.",
    timeline2: "If that payout method is empty the money is yours but it waits. Fill it in so the payout can leave.",

    deleteTitle: "Deleting my account",
    delete1: "Open your account settings. Deletion is there.",
    delete2: "What is erased and what has to be kept is described in the privacy policy, because a signed contract and a payment are also accounting records.",

    contactTitle: "Writing to us",
    contact1: "A question this page does not answer, an account you cannot get into, a payment that has not arrived: write to us and we will answer."
  }
};

i18n.addResourceBundle("fr", "translation", { guide: fr }, true, true);
i18n.addResourceBundle("en", "translation", { guide: en }, true, true);

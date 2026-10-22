/* THE THREE PAGES THE HEADER HAS BEEN LINKING TO WITHOUT CONTENT.

   /for-brands, /for-creators and /pricing existed so the marketing nav would
   not 404, and each rendered marketingPage.placeholder: "Cette page est en
   cours de rédaction." The nav links to all three on every page of the site
   and so does the footer, which means that sentence is what a Meta reviewer
   or an app-store reviewer reads when they click "Pour les marques". These
   three groups replace it.

   OWNS forBrands.*, forCreators.* AND pricingPage.* OUTRIGHT, so it carries
   no ordering constraint in main.tsx. The older marketingPage.* keys stay
   where they are: marketingStrings.ts owns that group, brandsTitle and
   friends are no longer rendered, and deleting them belongs in whatever
   change next touches that file rather than in this one.

   THE COMMISSION FIGURE IS NOT IN THIS FILE, and that is the point of the
   {{pct}} placeholder. backend/app/core/config.py holds the one definition,
   commission_bps = 1500, described there as a launch value to be set per
   country later; web/src/lib/pricing.ts already exists as the declared
   frontend mirror of it and the admin dispute screen already renders a
   percentage from it. pages/MarketingPage.tsx interpolates the same constant
   here, so the rate appears in exactly one place in the source and three
   pages in two languages follow it.

   THE WORKED EXAMPLE IS COMPUTED, NOT WRITTEN. Only the row labels live
   here. The amounts come from commissionFor() in lib/pricing.ts against one
   example figure in the page, using the same integer division the backend
   uses, so the example cannot drift from the rate above it or from what the
   server would actually do.

   WHAT THIS COPY DELIBERATELY DOES NOT SAY. It does not promise that the
   rate in force at signature governs a contract signed before a change. That
   is a sensible commitment and it is not mine to publish: it is a founder
   decision and a question for counsel, because it is a term rather than a
   description. The pricing page points at the terms of service for the full
   rule, which is where such a commitment belongs. It also names no
   competitor, in either language.

   No em dash and no en dash, like every other bundle. The no-break spaces
   before French colons and percent signs are written as escapes so they are
   visible in a diff. */
import i18n from "../i18n";

const frBrands = {
  title: "Pour les marques",
  sub: "Trouver un créateur, convenir d'un prix, payer une fois le travail livré. Sur une seule plateforme.",

  whyTitle: "Pourquoi passer par Kolabo",
  why1: "La recherche est gratuite et ne demande aucun compte. Vous regardez avant de vous engager.",
  why2: "Les prix sont publiés sur les profils. Vous savez ce que coûte une collaboration avant d'écrire à qui que ce soit.",
  why3: "Votre argent est bloqué en séquestre, pas versé. Le créateur sait qu'il sera payé, et vous ne payez qu'un travail que vous avez validé.",
  why4: "Le contrat, les messages et les livrables sont au même endroit, avec leurs dates. Personne ne discute de mémoire.",
  why5: "Rien n'est ajouté à votre prix. La commission Kolabo sort de la part du créateur, jamais de votre paiement.",

  howTitle: "Comment ça marche",
  how1: "Cherchez des créateurs par catégorie, par pays, par plateforme et par nombre d'abonnés. Ou publiez un brief et laissez-les venir à vous.",
  how2: "Commandez une offre, ou négociez le prix et le délai. Le créateur a 48 heures pour accepter.",
  how3: "Les deux parties signent le contrat, puis vous bloquez les fonds en séquestre par Mobile Money.",
  how4: "Le créateur livre. Vous validez, et le paiement part. Sans réponse de votre part sous 4 jours, le séquestre est libéré automatiquement.",

  feeTitle: "Ce que cela vous coûte",
  fee1: "Rien de plus que le prix convenu avec le créateur. Pas d'abonnement, pas de frais par campagne, pas de majoration à la commande.",
  fee2: "Kolabo prélève {{pct}} % sur le montant libéré au créateur, et les frais du prestataire de paiement sont à notre charge, pas à la vôtre.",

  whereTitle: "Où Kolabo fonctionne",
  where1: "Le pilote démarre au Bénin et au Togo. Côte d'Ivoire, Ghana, Sénégal, Cameroun et Nigeria suivront.",
  where2: "Les paiements passent par Mobile Money, et les réseaux disponibles dépendent du pays."
};

const frCreators = {
  title: "Pour les créateurs",
  sub: "Publiez vos offres, recevez des demandes, soyez payé sur votre portefeuille Mobile Money.",

  whyTitle: "Pourquoi passer par Kolabo",
  why1: "L'argent est bloqué en séquestre avant que vous commenciez. Vous ne travaillez pas sur une promesse.",
  why2: "Vous fixez vos prix et vous les publiez. Une marque qui vous écrit sait déjà ce que vous demandez.",
  why3: "Sans réponse de la marque sous 4 jours après votre remise, l'argent vous est libéré automatiquement. Vous n'avez personne à relancer.",
  why4: "Chaque tour de négociation reste dans le fil avec sa date, donc ce qui a été convenu est écrit.",
  why5: "Les avis que vous recevez restent sur votre profil et servent la collaboration suivante.",

  howTitle: "Comment ça marche",
  how1: "Créez votre profil : votre présentation, vos catégories, votre pays, votre photo et votre portfolio.",
  how2: "Déclarez vos réseaux sociaux, et connectez Facebook si vous en avez un, ce qui lit votre nombre d'abonnés directement depuis le réseau.",
  how3: "Publiez vos offres, avec un titre, un prix et un délai.",
  how4: "Répondez aux demandes et aux briefs ouverts, signez le contrat, livrez, et soyez payé.",

  feeTitle: "Ce que cela vous coûte",
  fee1: "Créer un compte, publier un profil et publier vos offres est gratuit. Kolabo ne gagne quelque chose que lorsqu'une collaboration aboutit.",
  fee2: "La commission est de {{pct}} %, prélevée sur le montant libéré au moment où l'argent vous est versé, jamais avant. Le relevé de vos gains montre le brut, la commission et le net pour chaque ligne.",
  fee3: "Les frais du prestataire de paiement sont à la charge de Kolabo. Ils ne sont pas déduits de ce que vous recevez.",

  payoutTitle: "Comment vous êtes payé",
  payout1: "Sur votre numéro Mobile Money. Les réseaux proposés dépendent de votre pays : MTN Mobile Money, Moov Money, Celtiis Cash, T-Money, Wave et Orange Money.",
  payout2: "Renseignez ce numéro avant la fin du travail. Sans lui, l'argent est à vous mais il attend."
};

const frPricing = {
  title: "Tarifs",
  sub: "Une seule commission, prélevée une seule fois, au moment où le créateur est payé.",

  freeTitle: "Ce qui est gratuit",
  free1: "Chercher et filtrer les créateurs, sans même avoir de compte.",
  free2: "Créer un compte, pour une marque comme pour un créateur.",
  free3: "Publier un profil de créateur et autant d'offres que vous voulez.",
  free4: "Publier un brief et négocier un prix.",

  feeTitle: "La commission",
  fee1: "Kolabo prélève {{pct}} % sur le montant libéré au créateur. Rien n'est ajouté au prix que paie la marque : la marque paie le prix convenu, et la commission sort de la part du créateur.",
  fee2: "Il n'y a pas d'abonnement, pas de frais de publication et pas de frais par campagne. Les frais du prestataire de paiement sont à la charge de Kolabo.",

  exampleTitle: "Un exemple",
  exampleAgreed: "Prix convenu avec le créateur",
  examplePaid: "Payé par la marque",
  exampleCommission: "Commission Kolabo",
  exampleNet: "Reçu par le créateur",
  exampleNote: "Les montants sont arrondis au franc, et le reste de l'arrondi va au créateur.",

  whenTitle: "Quand elle est prélevée",
  when1: "À la libération du séquestre, c'est à dire au moment où l'argent part vers le créateur. Pas à la commande, et pas quand la marque dépose les fonds.",
  when2: "Si une collaboration n'aboutit pas et que l'argent est remboursé, la commission ne porte que sur la part effectivement libérée au créateur.",
  when3: "Le taux en vigueur est celui indiqué sur cette page. Les conditions d'utilisation décrivent la règle complète, remboursements compris.",

  payTitle: "Moyens de paiement",
  pay1: "Les paiements et les versements passent par Mobile Money. Les réseaux disponibles dépendent du pays, et les paiements en ligne ne sont pas encore ouverts partout.",
  pay2: "Le pilote démarre au Bénin et au Togo. Côte d'Ivoire, Ghana, Sénégal, Cameroun et Nigeria suivront."
};

const enBrands = {
  title: "For brands",
  sub: "Find a creator, agree a price, pay once the work is delivered. On one platform.",

  whyTitle: "Why go through Kolabo",
  why1: "Searching is free and needs no account. You look before you commit to anything.",
  why2: "Prices are published on the profiles. You know what a collaboration costs before you write to anybody.",
  why3: "Your money is held in escrow, not paid out. The creator knows they will be paid, and you only pay for work you have approved.",
  why4: "The contract, the messages and the deliverables are in one place, with their dates. Nobody argues from memory.",
  why5: "Nothing is added to your price. The Kolabo commission comes out of the creator's share, never out of your payment.",

  howTitle: "How it works",
  how1: "Search creators by category, country, platform and follower count. Or publish a brief and let them come to you.",
  how2: "Order a package, or negotiate the price and the delivery time. The creator has 48 hours to accept.",
  how3: "Both parties sign the contract, then you hold the funds in escrow by Mobile Money.",
  how4: "The creator delivers. You approve, and the payment goes out. With no answer from you within 4 days the escrow is released automatically.",

  feeTitle: "What it costs you",
  fee1: "Nothing beyond the price you agreed with the creator. No subscription, no per campaign fee, no markup at checkout.",
  fee2: "Kolabo takes {{pct}}% of the amount released to the creator, and the payment provider's fees are ours to carry, not yours.",

  whereTitle: "Where Kolabo works",
  where1: "The pilot starts in Benin and Togo. Cote d'Ivoire, Ghana, Senegal, Cameroon and Nigeria follow.",
  where2: "Payments run on Mobile Money, and the available networks depend on the country."
};

const enCreators = {
  title: "For creators",
  sub: "Publish your packages, receive requests, get paid to your Mobile Money wallet.",

  whyTitle: "Why go through Kolabo",
  why1: "The money is held in escrow before you start. You are not working on a promise.",
  why2: "You set your prices and you publish them. A brand writing to you already knows what you charge.",
  why3: "With no answer from the brand within 4 days of your submission, the money is released to you automatically. There is nobody to chase.",
  why4: "Every round of a negotiation stays in the thread with its date, so what was agreed is written down.",
  why5: "The reviews you earn stay on your profile and work for the next collaboration.",

  howTitle: "How it works",
  how1: "Build your profile: your introduction, your categories, your country, your photo and your portfolio.",
  how2: "Declare your social accounts, and connect Facebook if you have one, which reads your follower count from the network itself.",
  how3: "Publish your packages, each with a title, a price and a delivery time.",
  how4: "Answer requests and open briefs, sign the contract, deliver, and get paid.",

  feeTitle: "What it costs you",
  fee1: "Creating an account, publishing a profile and publishing your packages are free. Kolabo earns something only when a collaboration completes.",
  fee2: "The commission is {{pct}}%, taken from the released amount at the moment the money is paid out to you, never before. Your earnings statement shows gross, commission and net on every line.",
  fee3: "The payment provider's fees are Kolabo's to carry. They are not deducted from what you receive.",

  payoutTitle: "How you are paid",
  payout1: "To your Mobile Money number. The networks on offer depend on your country: MTN Mobile Money, Moov Money, Celtiis Cash, T-Money, Wave and Orange Money.",
  payout2: "Fill that number in before the work ends. Without it the money is yours but it waits."
};

const enPricing = {
  title: "Pricing",
  sub: "One commission, taken once, at the moment the creator is paid.",

  freeTitle: "What is free",
  free1: "Searching and filtering creators, without even having an account.",
  free2: "Creating an account, for a brand as much as for a creator.",
  free3: "Publishing a creator profile and as many packages as you like.",
  free4: "Publishing a brief and negotiating a price.",

  feeTitle: "The commission",
  fee1: "Kolabo takes {{pct}}% of the amount released to the creator. Nothing is added to the price the brand pays: the brand pays the agreed price, and the commission comes out of the creator's share.",
  fee2: "There is no subscription, no listing fee and no per campaign fee. The payment provider's fees are Kolabo's to carry.",

  exampleTitle: "An example",
  exampleAgreed: "Price agreed with the creator",
  examplePaid: "Paid by the brand",
  exampleCommission: "Kolabo commission",
  exampleNet: "Received by the creator",
  exampleNote: "Amounts are rounded to the franc, and the rounding remainder goes to the creator.",

  whenTitle: "When it is taken",
  when1: "At the release of the escrow, meaning the moment the money goes to the creator. Not at the order, and not when the brand deposits the funds.",
  when2: "If a collaboration does not complete and the money is refunded, the commission applies only to the part actually released to the creator.",
  when3: "The rate in force is the one shown on this page. The terms of service describe the full rule, refunds included.",

  payTitle: "Payment methods",
  pay1: "Payments and payouts run on Mobile Money. The available networks depend on the country, and online payments are not open everywhere yet.",
  pay2: "The pilot starts in Benin and Togo. Cote d'Ivoire, Ghana, Senegal, Cameroon and Nigeria follow."
};

i18n.addResourceBundle("fr", "translation", { forBrands: frBrands }, true, true);
i18n.addResourceBundle("fr", "translation", { forCreators: frCreators }, true, true);
i18n.addResourceBundle("fr", "translation", { pricingPage: frPricing }, true, true);
i18n.addResourceBundle("en", "translation", { forBrands: enBrands }, true, true);
i18n.addResourceBundle("en", "translation", { forCreators: enCreators }, true, true);
i18n.addResourceBundle("en", "translation", { pricingPage: enPricing }, true, true);

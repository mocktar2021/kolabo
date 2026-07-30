/* Marketing site copy (landing, nav, footer), kept in its own bundle so the
   core app strings stay readable. Social proof numbers and quotes are clearly
   marked placeholders until pilot data exists. */
import i18n from "../i18n";

const fr = {
  marketingNav: { findCreators: "Trouver des createurs", forBrands: "Pour les marques", forCreators: "Pour les createurs", pricing: "Tarifs" },
  marketingPage: {
    placeholder: "Cette page est en cours de redaction. Le produit, lui, est deja utilisable.",
    brandsTitle: "Pour les marques", brandsBody: "Trouvez des createurs verifies, lancez une campagne et payez en toute securite.",
    creatorsTitle: "Pour les createurs", creatorsBody: "Publiez votre profil et vos tarifs, recevez des demandes de marques, soyez paye par Mobile Money.",
    pricingTitle: "Tarifs", pricingBody: "La recherche est gratuite. Une commission plateforme est prelevee sur chaque collaboration payee."
  },
  footer: {
    tagline: "La plateforme de marketing d'influence pour l'Afrique. Collaborations securisees, paiements proteges.",
    discover: "Decouvrir", company: "Kolabo", support: "Support",
    faq: "Questions frequentes", contact: "Nous contacter", rights: "Tous droits reserves."
  },
  landing: {
    heroA: "Le marketing d'influence en Afrique, de la", heroAccent: "recherche", heroB: "au paiement.",
    platform: "Plateforme", allPlatforms: "Toutes les plateformes",
    searchPlaceholder: "Rechercher par nom, niche ou mot cle...",
    featuredSub: "Des createurs verifies, prets a collaborer.",
    trustedBy: "Ils nous font confiance (exemples a remplacer)",
    howItWorks: "Comment ca marche", howItWorksSub: "De la recherche au paiement, en quatre etapes.",
    step1t: "Trouvez un createur", step1d: "Recherchez par niche, pays et audience. La recherche est gratuite.",
    step2t: "Convenez des termes", step2d: "Choisissez une offre ou negociez une campagne sur mesure.",
    step3t: "Signez et payez en sequestre", step3d: "Le contrat est signe par les deux parties, puis les fonds sont bloques.",
    step4t: "Validez et liberez", step4d: "Le createur livre, vous validez, le paiement part par Mobile Money.",
    whySub: "Ce qui compte vraiment sur nos marches.",
    statCountriesValue: "7", statCountries: "Pays cibles",
    statEscrowValue: "100%", statEscrow: "Paiements en sequestre",
    statLangValue: "2", statLang: "Langues (FR et EN)",
    statFeeValue: "15%", statFee: "Commission plateforme",
    testimonials: "Ce qu'ils en disent", testimonialsSub: "Exemples de temoignages.",
    quote1: "Nous avons trouve trois createurs pertinents en une apres-midi, et le paiement en sequestre a rassure tout le monde.",
    quote1Who: "Nom a venir", quote1Role: "Marque, Cotonou",
    quote2: "Enfin une plateforme en francais qui paie par Mobile Money. Je n'ai plus a courir apres mes paiements.",
    quote2Who: "Nom a venir", quote2Role: "Creatrice, Lome",
    quote3: "Le contrat genere automatiquement nous fait gagner un temps fou sur chaque collaboration.",
    quote3Who: "Nom a venir", quote3Role: "Agence, Abidjan",
    placeholderNote: "Temoignages provisoires, a remplacer par ceux du pilote.",
    faq: "Questions frequentes",
    faq1q: "La recherche est-elle gratuite?", faq1a: "Oui. Parcourir et rechercher des createurs ne demande aucun compte. Un compte est necessaire pour enregistrer un createur ou lancer une collaboration.",
    faq2q: "Comment fonctionne le paiement?", faq2a: "Les fonds sont bloques en sequestre des la signature du contrat, puis liberes au createur une fois la livraison validee. Une commission plateforme est prelevee a la liberation.",
    faq3q: "Quels pays sont couverts?", faq3a: "Le pilote demarre au Benin et au Togo. Cote d'Ivoire, Ghana, Senegal, Cameroun et Nigeria suivront.",
    faq4q: "Comment suis-je paye?", faq4a: "Par Mobile Money, dans votre devise locale. Le fournisseur est en cours de selection pour le lancement.",
    ctaTitle: "Pret a lancer votre premiere collaboration?", ctaSub: "Creez votre compte gratuitement et publiez votre profil ou votre campagne en quelques minutes."
  }
};

const en = {
  marketingNav: { findCreators: "Find creators", forBrands: "For brands", forCreators: "For creators", pricing: "Pricing" },
  marketingPage: {
    placeholder: "This page is still being written. The product itself is already usable.",
    brandsTitle: "For brands", brandsBody: "Find verified creators, run a campaign, and pay securely.",
    creatorsTitle: "For creators", creatorsBody: "Publish your profile and pricing, receive requests from brands, get paid by Mobile Money.",
    pricingTitle: "Pricing", pricingBody: "Searching is free. A platform commission is taken on each paid collaboration."
  },
  footer: {
    tagline: "The influencer marketing platform for Africa. Secure collaborations, protected payments.",
    discover: "Discover", company: "Kolabo", support: "Support",
    faq: "FAQ", contact: "Contact us", rights: "All rights reserved."
  },
  landing: {
    heroA: "Influencer marketing in Africa, from", heroAccent: "first search", heroB: "to final payment.",
    platform: "Platform", allPlatforms: "All platforms",
    searchPlaceholder: "Search creators by name, niche, or keyword...",
    featuredSub: "Verified creators, ready to collaborate.",
    trustedBy: "Trusted by (placeholder examples)",
    howItWorks: "How it works", howItWorksSub: "From search to payment, in four steps.",
    step1t: "Find a creator", step1d: "Search by niche, country, and audience. Searching is free.",
    step2t: "Agree the terms", step2d: "Buy a package or negotiate a custom campaign.",
    step3t: "Sign and fund escrow", step3d: "Both parties sign the contract, then the funds are held.",
    step4t: "Approve and release", step4d: "The creator delivers, you approve, payment goes out by Mobile Money.",
    whySub: "What actually matters in our markets.",
    statCountriesValue: "7", statCountries: "Target countries",
    statEscrowValue: "100%", statEscrow: "Payments held in escrow",
    statLangValue: "2", statLang: "Languages (EN and FR)",
    statFeeValue: "15%", statFee: "Platform commission",
    testimonials: "What people say", testimonialsSub: "Example testimonials.",
    quote1: "We found three relevant creators in an afternoon, and escrow made everyone comfortable.",
    quote1Who: "Name to come", quote1Role: "Brand, Cotonou",
    quote2: "Finally a platform in French that pays by Mobile Money. No more chasing payments.",
    quote2Who: "Name to come", quote2Role: "Creator, Lome",
    quote3: "The auto generated contract saves us real time on every collaboration.",
    quote3Who: "Name to come", quote3Role: "Agency, Abidjan",
    placeholderNote: "Placeholder testimonials, to be replaced with real pilot quotes.",
    faq: "Frequently asked questions",
    faq1q: "Is searching free?", faq1a: "Yes. Browsing and searching creators needs no account. An account is needed to save a creator or start a collaboration.",
    faq2q: "How does payment work?", faq2a: "Funds are held in escrow once the contract is signed, then released to the creator after you approve delivery. A platform commission is taken at release.",
    faq3q: "Which countries are covered?", faq3a: "The pilot starts in Benin and Togo. Cote d'Ivoire, Ghana, Senegal, Cameroon, and Nigeria follow.",
    faq4q: "How do I get paid?", faq4a: "By Mobile Money, in your local currency. The provider is being selected for launch.",
    ctaTitle: "Ready to start your first collaboration?", ctaSub: "Create a free account and publish your profile or campaign in minutes."
  }
};

i18n.addResourceBundle("fr", "translation", fr, true, true);
i18n.addResourceBundle("en", "translation", en, true, true);

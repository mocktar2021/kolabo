/* Marketing site copy (landing, nav, footer), kept in its own bundle so the
   core app strings stay readable. Social proof numbers and quotes are clearly
   marked placeholders until pilot data exists. Feature claims describe only
   shipped features: discovery, campaigns, proposals and negotiation,
   contracts, escrow payments, per-campaign messaging, reviews, FR/EN. */
import i18n from "../i18n";

const fr = {
  marketingNav: { findCreators: "Trouver des créateurs", forBrands: "Pour les marques", forCreators: "Pour les créateurs", pricing: "Tarifs" },
  featuresMenu: {
    label: "Fonctionnalités",
    searchT: "Recherche de créateurs", searchD: "Filtrez par niche, pays, audience et plateforme.",
    campaignsT: "Campagnes", campaignsD: "Créez un brief, invitez des créateurs, recevez des propositions.",
    contractsT: "Contrats", contractsD: "Contrats bilingues générés et signés en ligne.",
    paymentsT: "Paiements sécurisés", paymentsD: "Fonds bloqués en séquestre, libérés à la livraison validée.",
    messagingT: "Messagerie", messagingD: "Les échanges vivent dans chaque campagne, tout au même endroit.",
    reviewsT: "Avis vérifiés", reviewsD: "Des avis liés à de vraies collaborations, visibles sur les profils."
  },
  marketingPage: {
    placeholder: "Cette page est en cours de rédaction. Le produit, lui, est déjà utilisable.",
    brandsTitle: "Pour les marques", brandsBody: "Trouvez des créateurs vérifiés, lancez une campagne et payez en toute sécurité.",
    creatorsTitle: "Pour les créateurs", creatorsBody: "Publiez votre profil et vos tarifs, recevez des demandes de marques, soyez payé par Mobile Money.",
    pricingTitle: "Tarifs", pricingBody: "La recherche est gratuite. Une commission plateforme est prélevée sur chaque collaboration payée."
  },
  footer: {
    tagline: "La plateforme de marketing d'influence pour l'Afrique. Collaborations sécurisées, paiements protégés.",
    discover: "Découvrir", company: "Kolabo", support: "Support",
    faq: "Questions fréquentes", contact: "Nous contacter", rights: "Tous droits réservés.",
    /* Parent-company attribution, at the very bottom of every page. Brand
       apposition rather than "un produit de Mocktar Technologies": French
       reads a company name straight after the noun the same way it reads
       "une voiture Renault", and it is the shorter of the two on a 320 px
       phone. "Mocktar Technologies" is a company name and stays untranslated
       in both bundles. */
    parentProduct: "Un produit Mocktar Technologies."
  },
  landing: {
    heroA: "Le marketing d'influence en Afrique, de la", heroAccent: "recherche", heroB: "au paiement.",
    platform: "Plateforme", allPlatforms: "Toutes les plateformes",
    searchPlaceholder: "Rechercher par nom, niche ou mot clé...",
    featured: "Des créateurs prêts à collaborer",
    featuredSub: "Profils vérifiés, tarifs affichés.",
    seeAll: "Voir tous les créateurs",
    /* PLACEHOLDER metrics — replace with real numbers before public launch.
       The note key right below keeps the visible "exemples" convention. */
    trustedBy: "Ils nous font confiance",
    trustedByNote: "Chiffres d'exemple, à remplacer par les données du pilote.",
    tb1v: "500+", tb1l: "Créateurs inscrits",
    tb2v: "120+", tb2l: "Marques actives",
    tb3v: "1 000+", tb3l: "Contenus livrés",
    tb4v: "300+", tb4l: "Avis 5 étoiles",
    howItWorks: "Comment ça marche", howItWorksSub: "De la recherche au paiement, en quatre étapes.",
    step1t: "Trouvez un créateur", step1d: "Recherchez par niche, pays et audience. La recherche est gratuite.",
    step2t: "Convenez des termes", step2d: "Choisissez une offre ou négociez une campagne sur mesure.",
    step3t: "Signez et payez en séquestre", step3d: "Le contrat est signé par les deux parties, puis les fonds sont bloqués.",
    step4t: "Validez et libérez", step4d: "Le créateur livre, vous validez, le paiement part par Mobile Money.",
    /* Workflow tabs ("Tout en un seul flux"): every panel describes a shipped
       feature, nothing aspirational. */
    wfTitle: "Tout en un seul flux",
    wfSub: "Six étapes, une seule plateforme : suivez chaque collaboration de la découverte à l'avis final.",
    wf1Tab: "Découverte des créateurs",
    wf1D: "Recherchez parmi des profils vérifiés, par niche, pays, plateforme et audience. Les tarifs sont affichés dès la fiche du créateur, et la recherche reste gratuite, sans compte.",
    wf1C1: "Filtres par niche et pays", wf1C2: "Tarifs affichés", wf1C3: "Recherche gratuite",
    wf2Tab: "Briefs de campagne",
    wf2D: "Décrivez votre besoin une seule fois : budget, échéance et livrables par plateforme. Publiez le brief, invitez vos créateurs favoris et recevez leurs propositions au même endroit.",
    wf2C1: "Livrables par plateforme", wf2C2: "Budget et échéance", wf2C3: "Invitations ciblées",
    wf3Tab: "Négociation & contrats",
    wf3D: "Chaque proposition arrive chiffrée, avec tarif et délai. Acceptez-la et le contrat bilingue est généré automatiquement, puis signé en ligne par les deux parties.",
    wf3C1: "Propositions chiffrées", wf3C2: "Contrat bilingue", wf3C3: "Signature en ligne",
    wf4Tab: "Paiements sécurisés",
    wf4D: "Les fonds sont bloqués en séquestre dès la signature et libérés une fois la livraison validée. Le créateur est payé par Mobile Money, et un litige peut être ouvert à tout moment.",
    wf4C1: "Séquestre intégré", wf4C2: "Mobile Money", wf4C3: "Litiges arbitrés",
    wf5Tab: "Messagerie",
    wf5D: "Les échanges vivent dans chaque campagne : brief, questions et décisions restent attachés à la collaboration concernée. Plus rien ne se perd entre deux applications.",
    wf5C1: "Fil par campagne", wf5C2: "Historique conservé",
    wf6Tab: "Avis & confiance",
    wf6D: "Après chaque collaboration livrée, la marque laisse un avis lié à une transaction réelle. Les avis s'affichent sur le profil public du créateur, aux côtés des badges de vérification.",
    wf6C1: "Avis liés aux contrats", wf6C2: "Visibles sur le profil", wf6C3: "Comptes vérifiés",
    wfChat1: "Le script est validé ?", wfChat2: "Oui, je tourne demain.",
    wfReview: "Livraison rapide, très professionnel.",
    /* Replace-10-tools band. */
    toolsTitle: "Remplacez 10 outils par 1 plateforme",
    toolsBody: "Recherche. Brief. Négociation. Contrat. Paiement. Suivi. Aujourd'hui : WhatsApp, Excel, virements manuels et contrats papier. Kolabo réunit tout au même endroit.",
    toolsT1: "WhatsApp", toolsT2: "Excel", toolsT3: "Virements", toolsT4: "Contrats papier", toolsT5: "E-mails", toolsT6: "Notes",
    toolsHub: "Kolabo",
    /* Time band. */
    timeKicker: "Le temps de gestion d'une campagne",
    timeOld: "40 heures", timeNew: "1 heure",
    timeLine: "Relances, suivi des paiements et reporting tournent tout seuls. Il ne vous reste que les décisions.",
    timeCta: "Commencer gratuitement",
    whySub: "Ce qui compte vraiment sur nos marchés.",
    /* Teams ("Pensé pour toutes les tailles"). */
    teamsTitle: "Pensé pour toutes les tailles",
    teamsSub: "Des indépendants aux institutions, le même flux sécurisé.",
    team1t: "Marques", team1d: "Lancez des campagnes structurées et suivez chaque livrable. Le séquestre protège votre budget jusqu'à la validation.", team1b: "Découvrir les créateurs",
    team2t: "Agences", team2d: "Gérez plusieurs campagnes et créateurs depuis un seul compte. Contrats et paiements sont générés pour vous.", team2b: "Créer un compte agence",
    team3t: "Entrepreneurs", team3d: "Trouvez un créateur adapté à votre budget, sans intermédiaire. Commandez une offre à prix fixe en quelques minutes.", team3b: "Trouver un créateur",
    team4t: "ONG & institutions", team4d: "Faites porter vos messages par des voix locales de confiance. Chaque collaboration est contractualisée et traçable.", team4b: "Lancer une campagne",
    testimonials: "Ce qu'ils en disent", testimonialsSub: "Exemples de témoignages.",
    quote1: "Nous avons trouvé trois créateurs pertinents en une après-midi, et le paiement en séquestre a rassuré tout le monde.",
    quote1Who: "Nom à venir", quote1Role: "Marque, Cotonou",
    quote2: "Enfin une plateforme en français qui paie par Mobile Money. Je n'ai plus à courir après mes paiements.",
    quote2Who: "Nom à venir", quote2Role: "Créatrice, Lomé",
    quote3: "Le contrat généré automatiquement nous fait gagner un temps fou sur chaque collaboration.",
    quote3Who: "Nom à venir", quote3Role: "Agence, Abidjan",
    placeholderNote: "Témoignages provisoires, à remplacer par ceux du pilote.",
    faq: "Questions fréquentes",
    faq1q: "La recherche est-elle gratuite?", faq1a: "Oui. Parcourir et rechercher des créateurs ne demande aucun compte. Un compte est nécessaire pour enregistrer un créateur ou lancer une collaboration.",
    faq2q: "Comment fonctionne le paiement?", faq2a: "Les fonds sont bloqués en séquestre dès la signature du contrat, puis libérés au créateur une fois la livraison validée. Une commission plateforme est prélevée à la libération.",
    faq3q: "Quels pays sont couverts?", faq3a: "Le pilote démarre au Bénin et au Togo. Côte d'Ivoire, Ghana, Sénégal, Cameroun et Nigeria suivront.",
    faq4q: "Comment suis-je payé?", faq4a: "Par Mobile Money, dans votre devise locale. Le fournisseur est en cours de sélection pour le lancement.",
    /* Closing band. */
    closeA: "Votre prochaine collaboration est à",
    closeAccent: "trois minutes",
    closeB: ".",
    closeSub: "Créez votre compte, publiez un brief ou une offre, et démarrez dès aujourd'hui.",
    closeChip1: "Gratuit pour commencer", closeChip2: "Créateurs vérifiés", closeChip3: "Paiement Mobile Money",
    ctaBrandTitle: "Je cherche des créateurs",
    ctaBrandSub: "Parcourez les profils, comparez les prix, commandez en toute sécurité.",
    ctaBrandBtn: "Découvrir les créateurs",
    ctaCreatorTitle: "Je suis créateur",
    ctaCreatorSub: "Créez votre profil gratuit et recevez des demandes de marques.",
    ctaCreatorBtn: "Créer mon profil"
  }
};

const en = {
  marketingNav: { findCreators: "Find creators", forBrands: "For brands", forCreators: "For creators", pricing: "Pricing" },
  featuresMenu: {
    label: "Features",
    searchT: "Creator search", searchD: "Filter by niche, country, audience, and platform.",
    campaignsT: "Campaigns", campaignsD: "Create a brief, invite creators, receive proposals.",
    contractsT: "Contracts", contractsD: "Bilingual contracts generated and signed online.",
    paymentsT: "Secure payments", paymentsD: "Funds held in escrow, released once delivery is approved.",
    messagingT: "Messaging", messagingD: "Conversations live inside each campaign, all in one place.",
    reviewsT: "Verified reviews", reviewsD: "Reviews tied to real collaborations, shown on profiles."
  },
  marketingPage: {
    placeholder: "This page is still being written. The product itself is already usable.",
    brandsTitle: "For brands", brandsBody: "Find verified creators, run a campaign, and pay securely.",
    creatorsTitle: "For creators", creatorsBody: "Publish your profile and pricing, receive requests from brands, get paid by Mobile Money.",
    pricingTitle: "Pricing", pricingBody: "Searching is free. A platform commission is taken on each paid collaboration."
  },
  footer: {
    tagline: "The influencer marketing platform for Africa. Secure collaborations, protected payments.",
    discover: "Discover", company: "Kolabo", support: "Support",
    faq: "FAQ", contact: "Contact us", rights: "All rights reserved.",
    parentProduct: "A Mocktar Technologies product."
  },
  landing: {
    heroA: "Influencer marketing in Africa, from", heroAccent: "first search", heroB: "to final payment.",
    platform: "Platform", allPlatforms: "All platforms",
    searchPlaceholder: "Search creators by name, niche, or keyword...",
    featured: "Creators ready to collaborate",
    featuredSub: "Verified profiles, visible pricing.",
    seeAll: "See all creators",
    /* PLACEHOLDER metrics — replace with real numbers before public launch.
       The note key right below keeps the visible "examples" convention. */
    trustedBy: "Trusted by",
    trustedByNote: "Example figures, to be replaced with pilot data.",
    tb1v: "500+", tb1l: "Creators signed up",
    tb2v: "120+", tb2l: "Active brands",
    tb3v: "1,000+", tb3l: "Deliverables completed",
    tb4v: "300+", tb4l: "Five-star reviews",
    howItWorks: "How it works", howItWorksSub: "From search to payment, in four steps.",
    step1t: "Find a creator", step1d: "Search by niche, country, and audience. Searching is free.",
    step2t: "Agree the terms", step2d: "Buy a package or negotiate a custom campaign.",
    step3t: "Sign and fund escrow", step3d: "Both parties sign the contract, then the funds are held.",
    step4t: "Approve and release", step4d: "The creator delivers, you approve, payment goes out by Mobile Money.",
    /* Workflow tabs ("Everything in one flow"): every panel describes a
       shipped feature, nothing aspirational. */
    wfTitle: "Everything in one flow",
    wfSub: "Six steps, one platform: follow every collaboration from discovery to the final review.",
    wf1Tab: "Creator discovery",
    wf1D: "Search verified profiles by niche, country, platform, and audience. Pricing is visible right on the creator's page, and searching stays free, with no account needed.",
    wf1C1: "Niche and country filters", wf1C2: "Visible pricing", wf1C3: "Free search",
    wf2Tab: "Campaign briefs",
    wf2D: "Describe your need once: budget, deadline, and deliverables per platform. Publish the brief, invite your favorite creators, and receive their proposals in one place.",
    wf2C1: "Deliverables per platform", wf2C2: "Budget and deadline", wf2C3: "Targeted invitations",
    wf3Tab: "Negotiation & contracts",
    wf3D: "Every proposal arrives priced, with a rate and a timeline. Accept it and the bilingual contract is generated automatically, then signed online by both parties.",
    wf3C1: "Priced proposals", wf3C2: "Bilingual contract", wf3C3: "Online signature",
    wf4Tab: "Secure payments",
    wf4D: "Funds are held in escrow at signature and released once delivery is approved. The creator is paid by Mobile Money, and a dispute can be opened at any time.",
    wf4C1: "Built-in escrow", wf4C2: "Mobile Money", wf4C3: "Arbitrated disputes",
    wf5Tab: "Messaging",
    wf5D: "Conversations live inside each campaign: the brief, questions, and decisions stay attached to the collaboration they belong to. Nothing gets lost between apps anymore.",
    wf5C1: "One thread per campaign", wf5C2: "History preserved",
    wf6Tab: "Reviews & trust",
    wf6D: "After each delivered collaboration, the brand leaves a review tied to a real transaction. Reviews appear on the creator's public profile, next to verification badges.",
    wf6C1: "Reviews tied to contracts", wf6C2: "Shown on the profile", wf6C3: "Verified accounts",
    wfChat1: "Is the script approved?", wfChat2: "Yes, filming tomorrow.",
    wfReview: "Fast delivery, very professional.",
    /* Replace-10-tools band. */
    toolsTitle: "Replace 10 tools with 1 platform",
    toolsBody: "Search. Brief. Negotiation. Contract. Payment. Tracking. Today that means WhatsApp, Excel, manual transfers, and paper contracts. Kolabo brings it all together in one place.",
    toolsT1: "WhatsApp", toolsT2: "Excel", toolsT3: "Bank transfers", toolsT4: "Paper contracts", toolsT5: "Emails", toolsT6: "Notes",
    toolsHub: "Kolabo",
    /* Time band. */
    timeKicker: "Time spent managing a campaign",
    timeOld: "40 hours", timeNew: "1 hour",
    timeLine: "Status chasing, payment tracking, and reporting run on their own. All that's left for you is the decisions.",
    timeCta: "Start for free",
    whySub: "What actually matters in our markets.",
    /* Teams ("Built for every size"). */
    teamsTitle: "Built for every size",
    teamsSub: "From solo founders to institutions, the same secure flow.",
    team1t: "Brands", team1d: "Run structured campaigns and track every deliverable. Escrow protects your budget until you approve.", team1b: "Discover creators",
    team2t: "Agencies", team2d: "Manage several campaigns and creators from one account. Contracts and payments are generated for you.", team2b: "Create an agency account",
    team3t: "Entrepreneurs", team3d: "Find a creator that fits your budget, with no middleman. Order a fixed-price package in minutes.", team3b: "Find a creator",
    team4t: "NGOs & institutions", team4d: "Have trusted local voices carry your message. Every collaboration is contracted and traceable.", team4b: "Start a campaign",
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
    /* Closing band. */
    closeA: "Your next collaboration is",
    closeAccent: "three minutes",
    closeB: " away.",
    closeSub: "Create your account, publish a brief or a package, and start today.",
    closeChip1: "Free to start", closeChip2: "Verified creators", closeChip3: "Mobile Money payments",
    ctaBrandTitle: "I'm looking for creators",
    ctaBrandSub: "Browse profiles, compare prices, order securely.",
    ctaBrandBtn: "Discover creators",
    ctaCreatorTitle: "I'm a creator",
    ctaCreatorSub: "Create your free profile and receive requests from brands.",
    ctaCreatorBtn: "Create my profile"
  }
};

i18n.addResourceBundle("fr", "translation", fr, true, true);
i18n.addResourceBundle("en", "translation", en, true, true);

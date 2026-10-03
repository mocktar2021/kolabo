import i18n from "i18next";
import { initReactI18next } from "react-i18next";
/* THE CHOICE A VISITOR ALREADY MADE, if they made one. It has to be read
   HERE and not in a module that runs later, and the reason is the shape of
   main.tsx: this file is its first import, so init() below has already run by
   the time any of the twenty string bundles after it is evaluated. A read
   placed in one of those would be reading a language that had already been
   decided, and would have to call changeLanguage to correct it, which is a
   visible flash of French on an English visitor's first paint. */
import { initialLanguage } from "./lib/language";

/* Bilingual from day one. French is the default because the pilot markets
   (Benin and Togo) are francophone; English is a first class toggle. */
const cat = {
  fr: { fashion: "Mode", beauty: "Beauté", tech: "Tech", food: "Cuisine", travel: "Voyage", fitness: "Fitness", music: "Musique", comedy: "Humour", lifestyle: "Lifestyle", gaming: "Gaming", business: "Business", education: "Éducation" },
  en: { fashion: "Fashion", beauty: "Beauty", tech: "Tech", food: "Food", travel: "Travel", fitness: "Fitness", music: "Music", comedy: "Comedy", lifestyle: "Lifestyle", gaming: "Gaming", business: "Business", education: "Education" }
};
/* Every deliverable id in backend/app/core/platforms.py needs a label in both
   languages, otherwise a package shows the buyer a raw id like "photo_post". */
const deliverable = {
  fr: {
    post: "Publication", story: "Story", reel: "Reel", video: "Vidéo", short: "Short",
    carousel: "Carrousel", live: "Live", photo_post: "Publication photo",
    community_post: "Post communauté", snap: "Snap", spotlight: "Spotlight",
    thread: "Fil", article: "Article", status: "Statut", server_post: "Publication serveur",
    ugc_video: "Vidéo UGC", ugc_photo: "Photo UGC"
  },
  en: {
    post: "Post", story: "Story", reel: "Reel", video: "Video", short: "Short",
    carousel: "Carousel", live: "Live", photo_post: "Photo post",
    community_post: "Community post", snap: "Snap", spotlight: "Spotlight",
    thread: "Thread", article: "Article", status: "Status", server_post: "Server post",
    ugc_video: "UGC video", ugc_photo: "UGC photo"
  }
};
/* Chip labels on package rows (×3, 30 s, 5 min, 1 h). The unit abbreviations
   happen to be identical in both languages, but each locale still carries its
   own copy so a future divergence stays a one-line change. */
const pkg = {
  fr: { qty: "×{{n}}", duration_seconds: "{{n}} s", duration_minutes: "{{n}} min", duration_hours: "{{n}} h" },
  en: { qty: "×{{n}}", duration_seconds: "{{n}} s", duration_minutes: "{{n}} min", duration_hours: "{{n}} h" }
};

const resources = {
  fr: {
    translation: {
      cat: cat.fr,
      deliverable: deliverable.fr,
      pkg: pkg.fr,
      nav: { login: "Se connecter", signup: "Créer un compte", dashboard: "Tableau de bord", discover: "Découvrir", campaigns: "Campagnes", invitations: "Invitations", contracts: "Contrats", profile: "Profil", logout: "Déconnexion" },
      landing: {
        eyebrow: "Marketing d'influence pour l'Afrique",
        title: "Là où les créateurs et les marques se rencontrent",
        lead: "Kolabo connecte les créateurs de contenu africains et les entreprises: collaborations sécurisées, paiements protégés, et résultats mesurables.",
        ctaCreator: "Je suis créateur",
        ctaBusiness: "Je suis une marque",
        f1t: "Contrat pour chaque collaboration", f1d: "Chaque collaboration est contractualisée et traçable, des termes convenus jusqu'à la validation.",
        f2t: "Paiements sécurisés", f2d: "Les fonds sont bloqués en séquestre et libérés une fois le travail livré.",
        f3t: "Bilingue et local", f3d: "Français et anglais, pensée pour les paiements mobiles et les réseaux locaux.",
        searchCreators: "Rechercher", freeToSearch: "La recherche est gratuite, aucun compte requis.",
        featured: "Créateurs en vedette", seeAll: "Voir tout", whyKolabo: "Pourquoi Kolabo"
      },
      auth: {
        loginTitle: "Content de vous revoir", loginSub: "Connectez-vous à votre compte Kolabo.",
        registerTitle: "Créer votre compte", registerSub: "Rejoignez Kolabo en quelques secondes.",
        email: "Adresse e-mail", phone: "Numéro de téléphone", password: "Mot de passe", country: "Pays", role: "Je suis",
        roleInfluencer: "Créateur", roleInfluencerD: "J'ai une audience",
        roleBusiness: "Entreprise", roleBusinessD: "Je cherche des créateurs",
        roleAgency: "Agence", roleAgencyD: "Je gère des campagnes",
        submitLogin: "Se connecter", submitRegister: "Continuer",
        needAccount: "Pas encore de compte?", haveAccount: "Vous avez déjà un compte?",
        signupLink: "Créer un compte", loginLink: "Se connecter",
        otpTitle: "Vérifiez votre adresse e-mail", otpSub: "Entrez le code à 6 chiffres envoyé par e-mail.",
        otpCode: "Code de vérification", otpSubmit: "Vérifier",
        otpDevHint: "En développement, le code est écrit dans les logs du serveur.",
        working: "Un instant...",
        referredHint: "Parrainé·e par un créateur Kolabo."
      },
      dash: {
        welcome: "Bienvenue sur Kolabo", sub: "Que voulez-vous faire aujourd'hui?",
        profileTitle: "Compléter mon profil", profileDesc: "Ajoutez vos informations pour être visible et crédible.",
        discoverTitle: "Découvrir des créateurs", discoverDesc: "Recherchez et enregistrez des créateurs pour vos campagnes.",
        campaignTitle: "Mes campagnes", campaignDesc: "Créez et gérez vos campagnes et leurs propositions.",
        invitationsTitle: "Mes invitations", invitationsDesc: "Répondez aux invitations avec une proposition.",
        contractsTitle: "Mes contrats", contractsDesc: "Signez vos contrats et gérez les paiements.",
        /* Buyer-side wording for the same page. A brand that ordered a package
           looks for its commande, and the order only becomes a contract once
           the creator accepts — so "Mes contrats" is where the search stops
           too early. */
        ordersTitle: "Mes commandes et contrats",
        ordersDesc: "Suivez les commandes que vous avez passées et signez vos contrats.",
        /* Creator-side nudge, shown only when the count is not zero. */
        pendingOrders: "{{n}} commande(s) en attente de réponse",
        pendingOrdersDesc: "Répondez avant la fin du délai de 48 h.",
        /* Referral panel. The explainer states the rule the backend actually
           applies: credit is minted on the referred account's first completed
           order, not at signup. Anything vaguer reads as a promise we would
           be breaking on every dashboard load. */
        referralTitle: "Parrainez, gagnez du crédit",
        referralExplain: "Vous et la personne parrainée recevez du crédit Kolabo dès sa première commande terminée.",
        referralShare: "Partager mon lien",
        referralWhatsapp: "Partager sur WhatsApp",
        referralInvite: "Rejoins-moi sur Kolabo, la plateforme qui connecte créateurs et marques en Afrique. Inscris-toi ici : {{link}}",
        referralStatTotal: "Parrainages",
        referralBreakdown: "{{c}} créateurs · {{b}} marques",
        referralStatCredit: "Crédit gagné",
        referralColDate: "Date", referralColType: "Type", referralColStatus: "Statut",
        referralTypeCreator: "Créateur", referralTypeBrand: "Marque",
        referralStatusSignedUp: "Inscrit", referralStatusOrdered: "A commandé",
        referralEmpty: "Personne pour l'instant. Partagez votre lien pour commencer."
      },
      profile: {
        title: "Votre profil", sub: "Ces informations apparaissent sur la plateforme.",
        asCreator: "Profil créateur", asBusiness: "Profil entreprise",
        bio: "Bio", categories: "Catégories", followers: "Nombre d'abonnés",
        rate: "Tarif par publication", rateHint: "Montant indicatif en devise locale.",
        company: "Nom de l'entreprise", industry: "Secteur", description: "Description",
        save: "Enregistrer", saved: "Profil enregistré.",
        displayName: "Nom d'affichage", headline: "Titre", headlinePlaceholder: "Ex: Créateur lifestyle", location: "Localisation",
        locationCountry: "Pays", locationCity: "Ville", cityOther: "Autre…",
        birthDate: "Date de naissance",
        birthDateHint: "Jamais affichée publiquement. Vous devez avoir 18 ans.",
        gender: "Genre", genderNone: "Non précisé", genderFemale: "Femme", genderMale: "Homme", genderOther: "Autre", genderNoSay: "Préfère ne pas dire",
        languages: "Langues",
        uploadPhoto: "Ajouter une photo", viewPublic: "Voir ma page publique", portfolio: "Portfolio", addImage: "Ajouter des images",
        uploadingCount: "Envoi {{done}} / {{total}}",
        faqTitle: "FAQ", faqHint: "Vos réponses apparaissent sur votre page publique. Enregistrez le profil pour les sauvegarder.",
        faqAudience: "Qui est votre audience ?", faqBrands: "Avec quelles marques avez-vous travaillé ?",
        packages: "Mes offres", packagesHint: "Proposez des prestations à prix fixe.", packageTitle: "Titre de l'offre", addPackage: "Ajouter une offre",
        minPrice: "Minimum : {{n}} {{currency}}",
        packageQuantity: "Nombre",
        packageDuration: "Durée (optionnel)",
        durationUnitNone: "Aucune", durationUnitSeconds: "Secondes", durationUnitMinutes: "Minutes", durationUnitHours: "Heures",
        durationTogether: "Indiquez la durée et son unité ensemble.",
        connectSocialHint: "Connectez un réseau social pour proposer d'autres plateformes.",
        socialTitle: "Réseaux sociaux", socialAdd: "Ajouter un réseau",
        socialEmpty: "Aucun compte connecté pour le moment.",
        socialVerified: "Vérifié", socialPending: "En attente",
        socialEdit: "Modifier", socialDelete: "Supprimer",
        socialDeleteConfirm: "Supprimer ce compte ?",
        socialEditHint: "Modifier l'identifiant nécessite une nouvelle vérification."
      },
      danger: {
        title: "Zone dangereuse",
        explain: "La suppression est définitive : profil, offres, photos et conversations seront effacés.",
        delete: "Supprimer mon compte",
        confirmPassword: "Confirmez votre mot de passe",
        deleteForever: "Supprimer définitivement"
      },
      discover: {
        title: "Découvrir des créateurs", sub: "Trouvez le bon créateur pour votre campagne.",
        category: "Catégorie", country: "Pays", platform: "Plateforme", minFollowers: "Abonnés min.", any: "Tous",
        searchBtn: "Rechercher", loading: "Chargement...", empty: "Aucun créateur trouvé.",
        creator: "Créateur", followers: "abonnés", favorite: "Enregistrer", viewProfile: "Voir le profil", onRequest: "Prix sur demande"
      },
      public: {
        notFound: "Profil introuvable.", portfolio: "Portfolio", packages: "Offres", noPackages: "Aucune offre pour le moment.",
        /* Direct ordering. The card is the decision point, so everything that
           decides the click lives next to the price: who may order, what the
           creator has to do next, and the one fact that makes it safe — no
           money moves until they accept. */
        order: "Commander",
        orderSignedOut: "Créer un compte pour commander",
        orderBrandsOnly: "Seules les marques peuvent commander.",
        orderConfirm: "Confirmer votre commande",
        orderNote: "Note pour le créateur (optionnel)",
        orderRule: "Le créateur a 48 h pour accepter. Aucun paiement n'est prélevé avant son acceptation.",
        orderSend: "Envoyer la commande",
        orderCancel: "Annuler",
        orderSent: "Commande envoyée. Le créateur a 48 h pour répondre.",
        orderView: "Voir ma commande",
        /* Negotiating instead of taking the package as listed. Secondary to
           the order button on purpose: the published price is still the fast
           path, and this is the way out for the deals that do not fit it —
           the ones that were being agreed on WhatsApp instead. The terms are
           the only thing that changes; the 48 h rule, the note and the
           success line are the package order's. */
        negotiate: "Négocier une offre",
        negotiateOr: "ou",
        negotiateTitle: "Votre offre",
        negotiatePlatform: "Plateforme",
        negotiateDeliverable: "Livrable",
        negotiateQuantity: "Quantité",
        negotiatePrice: "Prix total",
        negotiateDays: "Délai (jours)",
        negotiateSend: "Envoyer l'offre",
        allPhotos: "Toutes les photos",
        reviewsTitle: "Avis", reviewCount_one: "{{count}} avis", reviewCount_other: "{{count}} avis",
        verifiedClient: "Client vérifié",
        verifiedAccount: "Compte vérifié",
        audienceTitle: "Audience", audienceUnit: "abonnés",
        audienceNote: "Données démographiques détaillées disponibles après connexion officielle de la plateforme.",
        filterAll: "Tous", seeMore: "Voir plus", seeLess: "Voir moins",
        choosePackage: "Choisir une offre",
        howItWorks: "Comment ça marche ?",
        how1: "1. Vous commandez et les fonds sont bloqués en séquestre.",
        how2: "2. Le créateur livre le contenu pour validation.",
        how3: "3. Vous validez, le paiement est libéré.",
        relatedCategories: "Catégories associées",
        share: "Partager",
        shareTitle: "Partager le profil de {{name}}",
        copy: "Copier", copied: "Copié !",
        shareEmail: "E-mail", shareEmailSubject: "Découvrez {{name}} sur Kolabo",
        close: "Fermer"
      },
      campaign: {
        title: "Créer une campagne", sub: "Décrivez votre besoin pour recevoir des propositions.",
        name: "Titre de la campagne", budget: "Budget", currency: "Devise", deadline: "Échéance",
        deliverables: "Livrables", addDeliverable: "Ajouter un livrable", publishNow: "Publier immédiatement",
        create: "Créer la campagne", publish: "Publier", published: "Campagne publiée.",
        another: "Créer une autre campagne", noBudget: "Budget non défini",
        noDeliverables: "Livrables non précisés",
        /* The brief in prose, set at creation and correctable afterwards. It
           is description and not terms, which is why it never locks. */
        description: "Description",
        descriptionPlaceholder: "Le contexte, le ton, ce que vous voulez dire et à qui.",
        status_draft: "Brouillon", status_published: "Publiée", status_cancelled: "Annulée",
        listTitle: "Mes campagnes", new: "Nouvelle campagne", listEmpty: "Vous n'avez pas encore de campagne.",
        notFound: "Campagne introuvable.",
        /* Correcting, calling off, erasing. The scope of an edit narrows as
           the campaign acquires an audience — editLocked is that rule said to
           the buyer, next to the fields it applies to. The two conflict lines
           are chosen by HTTP status, never by reading the server's English
           sentence, which is written for the API and can be reworded. */
        edit: "Modifier",
        editTitle: "Modifier la campagne",
        saveEdit: "Enregistrer les modifications",
        cancelEdit: "Annuler",
        editSaved: "Modifications enregistrées.",
        editLocked: "Verrouillé : des créateurs ont déjà proposé sur ces conditions.",
        directNotEditable: "Une commande directe ne se modifie pas : répondez par une contre-proposition.",
        cancelCampaign: "Annuler la campagne",
        cancelConfirm: "Annuler cette campagne ? Elle reste consultable et les créateurs invités seront prévenus.",
        cancelYes: "Confirmer l'annulation",
        cancelNo: "Retour",
        cancelled: "Cette campagne est annulée.",
        delete: "Supprimer",
        deleteHint: "Seul un brouillon sans proposition ni invitation peut être supprimé.",
        deleteConfirm: "Supprimer définitivement ce brouillon ? Rien n'en sera conservé.",
        deleteYes: "Confirmer la suppression",
        deleteNo: "Retour",
        inviteFromFavorites: "Inviter depuis mes favoris", noFavorites: "Aucun créateur favori à inviter.",
        /* Shown wherever a creator is named before they have a profile. "Nom
           d'affichage manquant" is the brand's problem to notice, not a raw
           id to decipher. */
        unnamedCreator: "Créateur sans nom",
        invite: "Inviter", invitations: "Invitations", noInvitations: "Aucune invitation pour le moment.",
        proposals: "Propositions", noProposals: "Aucune proposition pour le moment.",
        /* Negotiation thread. authorCreator/authorBrand label who wrote a
           version; the chain itself always belongs to the creator. */
        authorCreator: "Créateur", authorBrand: "Marque",
        currentOffer: "Offre actuelle", daysShort: "j",
        /* Whose turn it is, derived from the live version's author_role. The
           mirror image of the badge the creator reads on their invitations
           page: exactly one side is being waited on, and both screens read
           it off the same field rather than off a stored flag. */
        awaitingCreator: "En attente du créateur",
        creatorReplied: "Le créateur a répondu",
        reply: "Répondre",
        replyNote: "Votre réponse",
        replyNotePlaceholder: "Expliquez votre contre-proposition ou posez votre question.",
        replyRate: "Tarif (optionnel)", replyDays: "Délai (optionnel)",
        replyHint: "Laissez les montants vides pour conserver les termes actuels.",
        replySend: "Envoyer la réponse",
        /* Anti-disintermediation: what the brand loses by moving the
           conversation to WhatsApp, not what we lose. */
        keepOnPlatform: "Échangez ici pour garder le contrat et le paiement protégés.",
        accept: "Accepter et créer le contrat", viewContract: "Voir le contrat"
      },
      invitation: {
        title: "Mes invitations", sub: "Les campagnes auxquelles vous êtes invité.",
        empty: "Vous n'avez pas encore d'invitation.",
        /* The brief the creator prices against: who is asking, for what, by
           when. brandFallback covers a business that has not named itself yet. */
        brandFallback: "Marque", noDeadline: "Pas d'échéance", yourProposal: "Votre proposition",
        rate: "Tarif proposé", days: "Délai (jours)", send: "Envoyer", proposalSent: "Proposition envoyée.",
        /* Optional: the note carries the reasoning behind the numbers, in the
           same record as the numbers. */
        note: "Note (optionnel)",
        notePlaceholder: "Précisez ce qui est inclus, vos délais, vos conditions.",
        /* Direct orders share this list with brief invitations and must not
           read like them: the terms are already set, the money is already
           named, and the only thing missing is a yes or a no. */
        orderBadge: "Commande directe",
        campaignCancelled: "Campagne annulée",
        /* L'autre fin qu'une campagne peut atteindre, et elle ferme la carte
           comme l'annulation : le dossier reste, les formulaires partent. Sa
           propre pastille plutôt que celle de l'annulation, parce qu'une
           campagne menée à son terme et une campagne annulée ne sont pas la
           même nouvelle. */
        campaignCompleted: "Cette campagne est terminée.",
        orderPrice: "Prix", orderDelay: "Délai", orderNote: "Note de la marque",
        orderExpiresHours: "Expire dans {{n}} h",
        orderExpiresMinutes: "Expire dans {{n}} min",
        orderExpired: "Expirée",
        orderAccept: "Accepter", orderDecline: "Refuser",
        /* Said before the refusal rather than after it: nothing has been
           charged, so a no costs the brand nothing but the wait. */
        orderDeclineConfirm: "Aucun paiement n'a été prélevé ; la marque sera prévenue.",
        orderDeclineYes: "Confirmer le refus", orderDeclineNo: "Annuler",
        /* Reading the exchange, and answering it. The badge says whose move
           it is — derived from the live version's author_role, never stored. */
        negotiationTitle: "Négociation",
        turnYours: "À vous de répondre",
        turnBrand: "En attente de la marque",
        counter: "Contre-proposer",
        counterSend: "Envoyer la contre-proposition",
        counterHint: "Une contre-proposition reste dans le même délai de 48 h."
      },
      contract: {
        listTitle: "Mes contrats", listSub: "Signez vos contrats et suivez les paiements.",
        listEmpty: "Vous n'avez pas encore de contrat.", notFound: "Contrat introuvable.",
        title: "Contrat", rate: "Montant convenu", timeline: "Délai",
        businessSigned: "Signé par l'entreprise", creatorSigned: "Signé par le créateur", yes: "Oui", no: "En attente",
        document: "Document du contrat", signHeading: "Signature électronique",
        typeName: "Tapez votre nom pour signer", namePlaceholder: "Nom complet", sign: "Signer",
        waitingOther: "Vous avez signé. En attente de l'autre partie.",
        payment: "Paiement (séquestre)", fundHint: "Bloquez les fonds en séquestre via Mobile Money.",
        fund: "Financer le séquestre", awaitingFunding: "En attente du financement par l'entreprise.",
        escrowStatus: "Statut du séquestre", amount: "Montant", commission: "Commission",
        dispute: "Ouvrir un litige",
        released: "Séquestre libéré, le paiement est en route.",
        disputed: "Litige en cours, un administrateur va trancher.",
        refunded: "Le séquestre a été remboursé à l'entreprise.",
        status_pending_signatures: "En attente de signatures", status_signed: "Signé"
      },
      escrow: { status_held: "Bloqué", status_released: "Libéré", status_disputed: "En litige", status_refunded: "Remboursé" }
    }
  },
  en: {
    translation: {
      cat: cat.en,
      deliverable: deliverable.en,
      pkg: pkg.en,
      nav: { login: "Log in", signup: "Sign up", dashboard: "Dashboard", discover: "Discover", campaigns: "Campaigns", invitations: "Invitations", contracts: "Contracts", profile: "Profile", logout: "Log out" },
      landing: {
        eyebrow: "Influencer marketing for Africa",
        title: "Where creators and brands connect",
        lead: "Kolabo connects African content creators with businesses: secure collaborations, protected payments, and results you can measure.",
        ctaCreator: "I am a creator",
        ctaBusiness: "I am a brand",
        f1t: "A contract for every collaboration", f1d: "Every collaboration is put under contract and traceable, from agreed terms to validation.",
        f2t: "Secure payments", f2d: "Funds are held in escrow and released once the work is delivered.",
        f3t: "Bilingual and local", f3d: "English and French, built for mobile money and local networks.",
        searchCreators: "Search", freeToSearch: "Searching is free, no account needed.",
        featured: "Featured creators", seeAll: "See all", whyKolabo: "Why Kolabo"
      },
      auth: {
        loginTitle: "Welcome back", loginSub: "Log in to your Kolabo account.",
        registerTitle: "Create your account", registerSub: "Join Kolabo in seconds.",
        email: "Email address", phone: "Phone number", password: "Password", country: "Country", role: "I am",
        roleInfluencer: "Creator", roleInfluencerD: "I have an audience",
        roleBusiness: "Business", roleBusinessD: "I am looking for creators",
        roleAgency: "Agency", roleAgencyD: "I manage campaigns",
        submitLogin: "Log in", submitRegister: "Continue",
        needAccount: "No account yet?", haveAccount: "Already have an account?",
        signupLink: "Sign up", loginLink: "Log in",
        otpTitle: "Verify your email address", otpSub: "Enter the 6 digit code sent by email.",
        otpCode: "Verification code", otpSubmit: "Verify",
        otpDevHint: "In development the code is written to the server logs.",
        working: "One moment...",
        referredHint: "Referred by a Kolabo creator."
      },
      dash: {
        welcome: "Welcome to Kolabo", sub: "What would you like to do today?",
        profileTitle: "Complete my profile", profileDesc: "Add your details to be visible and credible.",
        discoverTitle: "Discover creators", discoverDesc: "Search and save creators for your campaigns.",
        campaignTitle: "My campaigns", campaignDesc: "Create and manage your campaigns and their proposals.",
        invitationsTitle: "My invitations", invitationsDesc: "Respond to invitations with a proposal.",
        contractsTitle: "My contracts", contractsDesc: "Sign your contracts and manage payments.",
        /* Buyer-side wording for the same page. A brand that ordered a package
           looks for its order, and the order only becomes a contract once the
           creator accepts — so "My contracts" is where the search stops too
           early. */
        ordersTitle: "My orders and contracts",
        ordersDesc: "Track the orders you placed and sign your contracts.",
        /* Creator-side nudge, shown only when the count is not zero. */
        pendingOrders: "{{n}} order(s) awaiting your answer",
        pendingOrdersDesc: "Answer before the 48 h window closes.",
        /* Referral panel. The explainer states the rule the backend actually
           applies: credit is minted on the referred account's first completed
           order, not at signup. Anything vaguer reads as a promise we would
           be breaking on every dashboard load. */
        referralTitle: "Refer and earn credit",
        referralExplain: "You and the person you refer both receive Kolabo credit as soon as their first order is completed.",
        referralShare: "Share my link",
        referralWhatsapp: "Share on WhatsApp",
        referralInvite: "Join me on Kolabo, the platform connecting African creators and brands. Sign up here: {{link}}",
        referralStatTotal: "Referrals",
        referralBreakdown: "{{c}} creators · {{b}} brands",
        referralStatCredit: "Credit earned",
        referralColDate: "Date", referralColType: "Type", referralColStatus: "Status",
        referralTypeCreator: "Creator", referralTypeBrand: "Brand",
        referralStatusSignedUp: "Signed up", referralStatusOrdered: "Ordered",
        referralEmpty: "No one yet. Share your link to get started."
      },
      profile: {
        title: "Your profile", sub: "This information appears across the platform.",
        asCreator: "Creator profile", asBusiness: "Business profile",
        bio: "Bio", categories: "Categories", followers: "Follower count",
        rate: "Rate per post", rateHint: "Indicative amount in local currency.",
        company: "Company name", industry: "Industry", description: "Description",
        save: "Save", saved: "Profile saved.",
        displayName: "Display name", headline: "Headline", headlinePlaceholder: "e.g. Lifestyle creator", location: "Location",
        locationCountry: "Country", locationCity: "City", cityOther: "Other…",
        birthDate: "Birth date",
        birthDateHint: "Never shown publicly. You must be 18 or older.",
        gender: "Gender", genderNone: "Not specified", genderFemale: "Female", genderMale: "Male", genderOther: "Other", genderNoSay: "Prefer not to say",
        languages: "Languages",
        uploadPhoto: "Upload a photo", viewPublic: "View my public page", portfolio: "Portfolio", addImage: "Add images",
        uploadingCount: "Uploading {{done}} / {{total}}",
        faqTitle: "FAQ", faqHint: "Your answers appear on your public page. Save the profile to store them.",
        faqAudience: "Who is your audience?", faqBrands: "What brands have you worked with?",
        packages: "My packages", packagesHint: "Offer fixed-price services.", packageTitle: "Package title", addPackage: "Add a package",
        minPrice: "Minimum: {{n}} {{currency}}",
        packageQuantity: "Quantity",
        packageDuration: "Duration (optional)",
        durationUnitNone: "None", durationUnitSeconds: "Seconds", durationUnitMinutes: "Minutes", durationUnitHours: "Hours",
        durationTogether: "Set the duration value and its unit together.",
        connectSocialHint: "Connect a social account to offer other platforms.",
        socialTitle: "Social accounts", socialAdd: "Add an account",
        socialEmpty: "No accounts connected yet.",
        socialVerified: "Verified", socialPending: "Pending",
        socialEdit: "Edit", socialDelete: "Delete",
        socialDeleteConfirm: "Delete this account?",
        socialEditHint: "Changing the handle requires a new verification."
      },
      danger: {
        title: "Danger zone",
        explain: "Deletion is permanent: your profile, packages, photos, and conversations will be erased.",
        delete: "Delete my account",
        confirmPassword: "Confirm your password",
        deleteForever: "Delete permanently"
      },
      discover: {
        title: "Discover creators", sub: "Find the right creator for your campaign.",
        category: "Category", country: "Country", platform: "Platform", minFollowers: "Min. followers", any: "Any",
        searchBtn: "Search", loading: "Loading...", empty: "No creators found.",
        creator: "Creator", followers: "followers", favorite: "Save", viewProfile: "View profile", onRequest: "Price on request"
      },
      public: {
        notFound: "Profile not found.", portfolio: "Portfolio", packages: "Packages", noPackages: "No packages yet.",
        /* Direct ordering. The card is the decision point, so everything that
           decides the click lives next to the price: who may order, what the
           creator has to do next, and the one fact that makes it safe — no
           money moves until they accept. */
        order: "Order",
        orderSignedOut: "Create an account to order",
        orderBrandsOnly: "Only brands can order.",
        orderConfirm: "Confirm your order",
        orderNote: "Note for the creator (optional)",
        orderRule: "The creator has 48 h to accept. No payment is taken before they accept.",
        orderSend: "Send the order",
        orderCancel: "Cancel",
        orderSent: "Order sent. The creator has 48 h to answer.",
        orderView: "View my order",
        /* Negotiating instead of taking the package as listed. Secondary to
           the order button on purpose: the published price is still the fast
           path, and this is the way out for the deals that do not fit it —
           the ones that were being agreed on WhatsApp instead. The terms are
           the only thing that changes; the 48 h rule, the note and the
           success line are the package order's. */
        negotiate: "Negotiate an offer",
        negotiateOr: "or",
        negotiateTitle: "Your offer",
        negotiatePlatform: "Platform",
        negotiateDeliverable: "Deliverable",
        negotiateQuantity: "Quantity",
        negotiatePrice: "Total price",
        negotiateDays: "Timeline (days)",
        negotiateSend: "Send the offer",
        allPhotos: "All photos",
        reviewsTitle: "Reviews", reviewCount_one: "{{count}} review", reviewCount_other: "{{count}} reviews",
        verifiedClient: "Verified client",
        verifiedAccount: "Verified account",
        audienceTitle: "Audience", audienceUnit: "followers",
        audienceNote: "Detailed demographics become available once the platform account is officially connected.",
        filterAll: "All", seeMore: "See more", seeLess: "See less",
        choosePackage: "Choose a package",
        howItWorks: "How does it work?",
        how1: "1. You order and the funds are held in escrow.",
        how2: "2. The creator delivers the content for review.",
        how3: "3. You approve and the payment is released.",
        relatedCategories: "Related categories",
        share: "Share",
        shareTitle: "Share {{name}}'s profile",
        copy: "Copy", copied: "Copied!",
        shareEmail: "Email", shareEmailSubject: "Discover {{name}} on Kolabo",
        close: "Close"
      },
      campaign: {
        title: "Create a campaign", sub: "Describe your brief to receive proposals.",
        name: "Campaign title", budget: "Budget", currency: "Currency", deadline: "Deadline",
        deliverables: "Deliverables", addDeliverable: "Add a deliverable", publishNow: "Publish immediately",
        create: "Create campaign", publish: "Publish", published: "Campaign published.",
        another: "Create another campaign", noBudget: "No budget set",
        noDeliverables: "Deliverables not specified",
        /* The brief in prose, set at creation and correctable afterwards. It
           is description and not terms, which is why it never locks. */
        description: "Description",
        descriptionPlaceholder: "The context, the tone, what you want to say and to whom.",
        status_draft: "Draft", status_published: "Published", status_cancelled: "Cancelled",
        listTitle: "My campaigns", new: "New campaign", listEmpty: "You have no campaigns yet.",
        notFound: "Campaign not found.",
        /* Correcting, calling off, erasing. The scope of an edit narrows as
           the campaign acquires an audience — editLocked is that rule said to
           the buyer, next to the fields it applies to. The two conflict lines
           are chosen by HTTP status, never by reading the server's English
           sentence, which is written for the API and can be reworded. */
        edit: "Edit",
        editTitle: "Edit campaign",
        saveEdit: "Save changes",
        cancelEdit: "Cancel",
        editSaved: "Changes saved.",
        editLocked: "Locked: creators have already made offers against these terms.",
        directNotEditable: "A direct order cannot be edited: answer it with a counter-offer.",
        cancelCampaign: "Cancel the campaign",
        cancelConfirm: "Cancel this campaign? It stays readable and the invited creators will be told.",
        cancelYes: "Confirm cancellation",
        cancelNo: "Back",
        cancelled: "This campaign is cancelled.",
        delete: "Delete",
        deleteHint: "Only a draft with no proposals and no invitations can be deleted.",
        deleteConfirm: "Permanently delete this draft? Nothing will be kept.",
        deleteYes: "Confirm deletion",
        deleteNo: "Back",
        inviteFromFavorites: "Invite from my favorites", noFavorites: "No favorited creators to invite.",
        /* Shown wherever a creator is named before they have a profile. A
           missing display name is something the brand should notice, not a
           raw id to decipher. */
        unnamedCreator: "Unnamed creator",
        invite: "Invite", invitations: "Invitations", noInvitations: "No invitations yet.",
        proposals: "Proposals", noProposals: "No proposals yet.",
        /* Negotiation thread. authorCreator/authorBrand label who wrote a
           version; the chain itself always belongs to the creator. */
        authorCreator: "Creator", authorBrand: "Brand",
        currentOffer: "Current offer", daysShort: "d",
        /* Whose turn it is, derived from the live version's author_role. The
           mirror image of the badge the creator reads on their invitations
           page: exactly one side is being waited on, and both screens read
           it off the same field rather than off a stored flag. */
        awaitingCreator: "Waiting on the creator",
        creatorReplied: "The creator replied",
        reply: "Reply",
        replyNote: "Your reply",
        replyNotePlaceholder: "Explain your counter-offer or ask your question.",
        replyRate: "Rate (optional)", replyDays: "Timeline (optional)",
        replyHint: "Leave the amounts blank to keep the current terms.",
        replySend: "Send reply",
        /* Anti-disintermediation: what the brand loses by moving the
           conversation to WhatsApp, not what we lose. */
        keepOnPlatform: "Negotiate here to keep the contract and payment protected.",
        accept: "Accept and create contract", viewContract: "View contract"
      },
      invitation: {
        title: "My invitations", sub: "Campaigns you have been invited to.",
        empty: "You have no invitations yet.",
        /* The brief the creator prices against: who is asking, for what, by
           when. brandFallback covers a business that has not named itself yet. */
        brandFallback: "Brand", noDeadline: "No deadline", yourProposal: "Your proposal",
        rate: "Proposed rate", days: "Timeline (days)", send: "Send", proposalSent: "Proposal sent.",
        /* Optional: the note carries the reasoning behind the numbers, in the
           same record as the numbers. */
        note: "Note (optional)",
        notePlaceholder: "Spell out what is included, your timing, your conditions.",
        /* Direct orders share this list with brief invitations and must not
           read like them: the terms are already set, the money is already
           named, and the only thing missing is a yes or a no. */
        orderBadge: "Direct order",
        campaignCancelled: "Campaign cancelled",
        /* The other end a campaign can reach, and it closes the card the way
           cancelling does: the record stays, the forms go. Its own badge
           rather than the cancelled one, because a brief that ran to the end
           and a brief that was called off are not the same news. */
        campaignCompleted: "This brief is finished.",
        orderPrice: "Price", orderDelay: "Timeline", orderNote: "Note from the brand",
        orderExpiresHours: "Expires in {{n}} h",
        orderExpiresMinutes: "Expires in {{n}} min",
        orderExpired: "Expired",
        orderAccept: "Accept", orderDecline: "Decline",
        /* Said before the refusal rather than after it: nothing has been
           charged, so a no costs the brand nothing but the wait. */
        orderDeclineConfirm: "No payment has been taken; the brand will be notified.",
        orderDeclineYes: "Confirm decline", orderDeclineNo: "Cancel",
        /* Reading the exchange, and answering it. The badge says whose move
           it is — derived from the live version's author_role, never stored. */
        negotiationTitle: "Negotiation",
        turnYours: "Your turn to answer",
        turnBrand: "Waiting on the brand",
        counter: "Counter-offer",
        counterSend: "Send counter-offer",
        counterHint: "A counter-offer stays within the same 48 h window."
      },
      contract: {
        listTitle: "My contracts", listSub: "Sign your contracts and track payments.",
        listEmpty: "You have no contracts yet.", notFound: "Contract not found.",
        title: "Contract", rate: "Agreed amount", timeline: "Timeline",
        businessSigned: "Signed by business", creatorSigned: "Signed by creator", yes: "Yes", no: "Pending",
        document: "Contract document", signHeading: "Electronic signature",
        typeName: "Type your name to sign", namePlaceholder: "Full name", sign: "Sign",
        waitingOther: "You have signed. Waiting for the other party.",
        payment: "Payment (escrow)", fundHint: "Hold the funds in escrow via Mobile Money.",
        fund: "Fund escrow", awaitingFunding: "Waiting for the business to fund.",
        escrowStatus: "Escrow status", amount: "Amount", commission: "Commission",
        dispute: "Open a dispute",
        released: "Escrow released, the payout is on the way.",
        disputed: "Dispute open, an admin will resolve it.",
        refunded: "The escrow was refunded to the business.",
        status_pending_signatures: "Pending signatures", status_signed: "Signed"
      },
      escrow: { status_held: "Held", status_released: "Released", status_disputed: "Disputed", status_refunded: "Refunded" }
    }
  }
};

/* `lng` was the literal "fr" until the switch in the header learned to
   remember anything. It is still "fr" for everybody who has never touched
   that switch: see DEFAULT_LANGUAGE in lib/language.ts for why that default
   is deliberate and why the browser's own language is deliberately not
   consulted. What changed is only that a visitor who did touch it is not made
   to touch it again on every page load.

   THE BUNDLES ADDED AFTER THIS DO NOT CARE which language was chosen:
   addResourceBundle registers both columns of every group whatever `lng`
   says, so nothing below this line has to be reordered. */
i18n.use(initReactI18next).init({
  resources,
  lng: initialLanguage(),
  fallbackLng: "en",
  interpolation: { escapeValue: false }
});

export default i18n;

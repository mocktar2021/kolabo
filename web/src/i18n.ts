import i18n from "i18next";
import { initReactI18next } from "react-i18next";

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
        f1t: "Confiance vérifiée", f1d: "Profils et entreprises vérifiés, pour collaborer en toute sérénité.",
        f2t: "Paiements sécurisés", f2d: "Les fonds sont bloqués en séquestre et libérés une fois le travail livré.",
        f3t: "Bilingue et local", f3d: "Français et anglais, pensée pour les paiements mobiles et les réseaux locaux.",
        searchCreators: "Rechercher", freeToSearch: "La recherche est gratuite, aucun compte requis.",
        featured: "Créateurs en vedette", seeAll: "Voir tout", whyKolabo: "Pourquoi Kolabo"
      },
      auth: {
        loginTitle: "Content de vous revoir", loginSub: "Connectez-vous à votre compte Kolabo.",
        registerTitle: "Créer votre compte", registerSub: "Rejoignez Kolabo en quelques secondes.",
        phone: "Numéro de téléphone", password: "Mot de passe", country: "Pays", role: "Je suis",
        roleInfluencer: "Créateur", roleInfluencerD: "J'ai une audience",
        roleBusiness: "Entreprise", roleBusinessD: "Je cherche des créateurs",
        roleAgency: "Agence", roleAgencyD: "Je gère des campagnes",
        submitLogin: "Se connecter", submitRegister: "Continuer",
        needAccount: "Pas encore de compte?", haveAccount: "Vous avez déjà un compte?",
        signupLink: "Créer un compte", loginLink: "Se connecter",
        otpTitle: "Vérifiez votre numéro", otpSub: "Entrez le code à 6 chiffres envoyé par SMS.",
        otpCode: "Code de vérification", otpSubmit: "Vérifier",
        otpDevHint: "En développement, le code est écrit dans les logs du serveur.",
        working: "Un instant..."
      },
      dash: {
        welcome: "Bienvenue sur Kolabo", sub: "Que voulez-vous faire aujourd'hui?",
        profileTitle: "Compléter mon profil", profileDesc: "Ajoutez vos informations pour être visible et crédible.",
        discoverTitle: "Découvrir des créateurs", discoverDesc: "Recherchez et enregistrez des créateurs pour vos campagnes.",
        campaignTitle: "Mes campagnes", campaignDesc: "Créez et gérez vos campagnes et leurs propositions.",
        invitationsTitle: "Mes invitations", invitationsDesc: "Répondez aux invitations avec une proposition.",
        contractsTitle: "Mes contrats", contractsDesc: "Signez vos contrats et gérez les paiements."
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
        gender: "Genre", genderFemale: "Femme", genderMale: "Homme", genderOther: "Autre", genderNoSay: "Préfère ne pas dire",
        languages: "Langues",
        uploadPhoto: "Ajouter une photo", viewPublic: "Voir ma page publique", portfolio: "Portfolio", addImage: "Ajouter des images",
        uploadingCount: "Envoi {{done}} / {{total}}",
        faqTitle: "FAQ", faqHint: "Vos réponses apparaissent sur votre page publique. Enregistrez le profil pour les sauvegarder.",
        faqAudience: "Qui est votre audience ?", faqBrands: "Avec quelles marques avez-vous travaillé ?",
        packages: "Mes offres", packagesHint: "Proposez des prestations à prix fixe.", packageTitle: "Titre de l'offre", addPackage: "Ajouter une offre",
        minPrice: "Minimum : {{n}} {{currency}}",
        packageQuantity: "Nombre",
        packageDuration: "Durée (optionnel)",
        durationUnitSeconds: "Secondes", durationUnitMinutes: "Minutes", durationUnitHours: "Heures",
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
        deleteForever: "Supprimer définitivement",
        wrongPassword: "Mot de passe incorrect.",
        hasHistory: "Votre compte a un historique de transactions. Contactez le support pour le fermer."
      },
      discover: {
        title: "Découvrir des créateurs", sub: "Trouvez le bon créateur pour votre campagne.",
        category: "Catégorie", country: "Pays", platform: "Plateforme", minFollowers: "Abonnés min.", any: "Tous",
        searchBtn: "Rechercher", loading: "Chargement...", empty: "Aucun créateur trouvé.",
        creator: "Créateur", verified: "Vérifié", followers: "abonnés", favorite: "Enregistrer", viewProfile: "Voir le profil", onRequest: "Prix sur demande"
      },
      public: {
        notFound: "Profil introuvable.", portfolio: "Portfolio", packages: "Offres", noPackages: "Aucune offre pour le moment.",
        order: "Commander (bientôt)", orderSoon: "La commande directe arrive bientôt.",
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
        status_draft: "Brouillon", status_published: "Publiée",
        listTitle: "Mes campagnes", new: "Nouvelle campagne", listEmpty: "Vous n'avez pas encore de campagne.",
        notFound: "Campagne introuvable.",
        inviteFromFavorites: "Inviter depuis mes favoris", noFavorites: "Aucun créateur favori à inviter.",
        invite: "Inviter", invitations: "Invitations", noInvitations: "Aucune invitation pour le moment.",
        proposals: "Propositions", noProposals: "Aucune proposition pour le moment.",
        accept: "Accepter et créer le contrat", viewContract: "Voir le contrat"
      },
      invitation: {
        title: "Mes invitations", sub: "Les campagnes auxquelles vous êtes invité.",
        empty: "Vous n'avez pas encore d'invitation.",
        rate: "Tarif proposé", days: "Délai (jours)", send: "Envoyer", proposalSent: "Proposition envoyée."
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
        release: "Confirmer et libérer", dispute: "Ouvrir un litige",
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
        f1t: "Verified trust", f1d: "Verified profiles and businesses, so you collaborate with confidence.",
        f2t: "Secure payments", f2d: "Funds are held in escrow and released once the work is delivered.",
        f3t: "Bilingual and local", f3d: "English and French, built for mobile money and local networks.",
        searchCreators: "Search", freeToSearch: "Searching is free, no account needed.",
        featured: "Featured creators", seeAll: "See all", whyKolabo: "Why Kolabo"
      },
      auth: {
        loginTitle: "Welcome back", loginSub: "Log in to your Kolabo account.",
        registerTitle: "Create your account", registerSub: "Join Kolabo in seconds.",
        phone: "Phone number", password: "Password", country: "Country", role: "I am",
        roleInfluencer: "Creator", roleInfluencerD: "I have an audience",
        roleBusiness: "Business", roleBusinessD: "I am looking for creators",
        roleAgency: "Agency", roleAgencyD: "I manage campaigns",
        submitLogin: "Log in", submitRegister: "Continue",
        needAccount: "No account yet?", haveAccount: "Already have an account?",
        signupLink: "Sign up", loginLink: "Log in",
        otpTitle: "Verify your number", otpSub: "Enter the 6 digit code sent by SMS.",
        otpCode: "Verification code", otpSubmit: "Verify",
        otpDevHint: "In development the code is written to the server logs.",
        working: "One moment..."
      },
      dash: {
        welcome: "Welcome to Kolabo", sub: "What would you like to do today?",
        profileTitle: "Complete my profile", profileDesc: "Add your details to be visible and credible.",
        discoverTitle: "Discover creators", discoverDesc: "Search and save creators for your campaigns.",
        campaignTitle: "My campaigns", campaignDesc: "Create and manage your campaigns and their proposals.",
        invitationsTitle: "My invitations", invitationsDesc: "Respond to invitations with a proposal.",
        contractsTitle: "My contracts", contractsDesc: "Sign your contracts and manage payments."
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
        gender: "Gender", genderFemale: "Female", genderMale: "Male", genderOther: "Other", genderNoSay: "Prefer not to say",
        languages: "Languages",
        uploadPhoto: "Upload a photo", viewPublic: "View my public page", portfolio: "Portfolio", addImage: "Add images",
        uploadingCount: "Uploading {{done}} / {{total}}",
        faqTitle: "FAQ", faqHint: "Your answers appear on your public page. Save the profile to store them.",
        faqAudience: "Who is your audience?", faqBrands: "What brands have you worked with?",
        packages: "My packages", packagesHint: "Offer fixed-price services.", packageTitle: "Package title", addPackage: "Add a package",
        minPrice: "Minimum: {{n}} {{currency}}",
        packageQuantity: "Quantity",
        packageDuration: "Duration (optional)",
        durationUnitSeconds: "Seconds", durationUnitMinutes: "Minutes", durationUnitHours: "Hours",
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
        deleteForever: "Delete permanently",
        wrongPassword: "Incorrect password.",
        hasHistory: "Your account has transaction history. Contact support to close it."
      },
      discover: {
        title: "Discover creators", sub: "Find the right creator for your campaign.",
        category: "Category", country: "Country", platform: "Platform", minFollowers: "Min. followers", any: "Any",
        searchBtn: "Search", loading: "Loading...", empty: "No creators found.",
        creator: "Creator", verified: "Verified", followers: "followers", favorite: "Save", viewProfile: "View profile", onRequest: "Price on request"
      },
      public: {
        notFound: "Profile not found.", portfolio: "Portfolio", packages: "Packages", noPackages: "No packages yet.",
        order: "Order (soon)", orderSoon: "Direct ordering is coming soon.",
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
        status_draft: "Draft", status_published: "Published",
        listTitle: "My campaigns", new: "New campaign", listEmpty: "You have no campaigns yet.",
        notFound: "Campaign not found.",
        inviteFromFavorites: "Invite from my favorites", noFavorites: "No favorited creators to invite.",
        invite: "Invite", invitations: "Invitations", noInvitations: "No invitations yet.",
        proposals: "Proposals", noProposals: "No proposals yet.",
        accept: "Accept and create contract", viewContract: "View contract"
      },
      invitation: {
        title: "My invitations", sub: "Campaigns you have been invited to.",
        empty: "You have no invitations yet.",
        rate: "Proposed rate", days: "Timeline (days)", send: "Send", proposalSent: "Proposal sent."
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
        release: "Confirm and release", dispute: "Open a dispute",
        released: "Escrow released, the payout is on the way.",
        disputed: "Dispute open, an admin will resolve it.",
        refunded: "The escrow was refunded to the business.",
        status_pending_signatures: "Pending signatures", status_signed: "Signed"
      },
      escrow: { status_held: "Held", status_released: "Released", status_disputed: "Disputed", status_refunded: "Refunded" }
    }
  }
};

i18n.use(initReactI18next).init({
  resources,
  lng: "fr",
  fallbackLng: "en",
  interpolation: { escapeValue: false }
});

export default i18n;

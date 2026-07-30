import i18n from "i18next";
import { initReactI18next } from "react-i18next";

/* Bilingual from day one. French is the default because the pilot markets
   (Benin and Togo) are francophone; English is a first class toggle. */
const cat = {
  fr: { fashion: "Mode", beauty: "Beaute", tech: "Tech", food: "Cuisine", travel: "Voyage", fitness: "Fitness", music: "Musique", comedy: "Humour", lifestyle: "Lifestyle", gaming: "Gaming", business: "Business", education: "Education" },
  en: { fashion: "Fashion", beauty: "Beauty", tech: "Tech", food: "Food", travel: "Travel", fitness: "Fitness", music: "Music", comedy: "Comedy", lifestyle: "Lifestyle", gaming: "Gaming", business: "Business", education: "Education" }
};
const deliverable = {
  fr: { post: "Publication", story: "Story", reel: "Reel", video: "Video", short: "Short" },
  en: { post: "Post", story: "Story", reel: "Reel", video: "Video", short: "Short" }
};

const resources = {
  fr: {
    translation: {
      cat: cat.fr,
      deliverable: deliverable.fr,
      nav: { login: "Se connecter", signup: "Creer un compte", dashboard: "Tableau de bord", discover: "Decouvrir", campaigns: "Campagnes", invitations: "Invitations", contracts: "Contrats", profile: "Profil", logout: "Deconnexion" },
      landing: {
        eyebrow: "Marketing d'influence pour l'Afrique",
        title: "La ou les createurs et les marques se rencontrent",
        lead: "Kolabo connecte les createurs de contenu africains et les entreprises: collaborations securisees, paiements proteges, et resultats mesurables.",
        ctaCreator: "Je suis createur",
        ctaBusiness: "Je suis une marque",
        f1t: "Confiance verifiee", f1d: "Profils et entreprises verifies, pour collaborer en toute serenite.",
        f2t: "Paiements securises", f2d: "Les fonds sont bloques en sequestre et liberes une fois le travail livre.",
        f3t: "Bilingue et local", f3d: "Francais et anglais, pensee pour les paiements mobiles et les reseaux locaux.",
        searchCreators: "Rechercher", freeToSearch: "La recherche est gratuite, aucun compte requis.",
        featured: "Createurs en vedette", seeAll: "Voir tout", whyKolabo: "Pourquoi Kolabo"
      },
      auth: {
        loginTitle: "Content de vous revoir", loginSub: "Connectez-vous a votre compte Kolabo.",
        registerTitle: "Creer votre compte", registerSub: "Rejoignez Kolabo en quelques secondes.",
        phone: "Numero de telephone", password: "Mot de passe", country: "Pays", role: "Je suis",
        roleInfluencer: "Createur", roleInfluencerD: "J'ai une audience",
        roleBusiness: "Entreprise", roleBusinessD: "Je cherche des createurs",
        roleAgency: "Agence", roleAgencyD: "Je gere des campagnes",
        submitLogin: "Se connecter", submitRegister: "Continuer",
        needAccount: "Pas encore de compte?", haveAccount: "Vous avez deja un compte?",
        signupLink: "Creer un compte", loginLink: "Se connecter",
        otpTitle: "Verifiez votre numero", otpSub: "Entrez le code a 6 chiffres envoye par SMS.",
        otpCode: "Code de verification", otpSubmit: "Verifier",
        otpDevHint: "En developpement, le code est ecrit dans les logs du serveur.",
        working: "Un instant..."
      },
      dash: {
        welcome: "Bienvenue sur Kolabo", sub: "Que voulez-vous faire aujourd'hui?",
        profileTitle: "Completer mon profil", profileDesc: "Ajoutez vos informations pour etre visible et credible.",
        discoverTitle: "Decouvrir des createurs", discoverDesc: "Recherchez et enregistrez des createurs pour vos campagnes.",
        campaignTitle: "Mes campagnes", campaignDesc: "Creez et gerez vos campagnes et leurs propositions.",
        invitationsTitle: "Mes invitations", invitationsDesc: "Repondez aux invitations avec une proposition.",
        contractsTitle: "Mes contrats", contractsDesc: "Signez vos contrats et gerez les paiements."
      },
      profile: {
        title: "Votre profil", sub: "Ces informations apparaissent sur la plateforme.",
        asCreator: "Profil createur", asBusiness: "Profil entreprise",
        bio: "Bio", categories: "Categories", followers: "Nombre d'abonnes",
        rate: "Tarif par publication", rateHint: "Montant indicatif en devise locale.",
        company: "Nom de l'entreprise", industry: "Secteur", description: "Description",
        save: "Enregistrer", saved: "Profil enregistre.",
        displayName: "Nom d'affichage", headline: "Titre", headlinePlaceholder: "Ex: Createur lifestyle", location: "Localisation",
        uploadPhoto: "Ajouter une photo", viewPublic: "Voir ma page publique", portfolio: "Portfolio", addImage: "Ajouter une image",
        packages: "Mes offres", packagesHint: "Proposez des prestations a prix fixe.", packageTitle: "Titre de l'offre", addPackage: "Ajouter une offre"
      },
      discover: {
        title: "Decouvrir des createurs", sub: "Trouvez le bon createur pour votre campagne.",
        category: "Categorie", country: "Pays", minFollowers: "Abonnes min.", any: "Tous",
        searchBtn: "Rechercher", loading: "Chargement...", empty: "Aucun createur trouve.",
        creator: "Createur", verified: "Verifie", followers: "abonnes", favorite: "Enregistrer", viewProfile: "Voir le profil", onRequest: "Prix sur demande"
      },
      public: { notFound: "Profil introuvable.", portfolio: "Portfolio", packages: "Offres", noPackages: "Aucune offre pour le moment.", order: "Commander", orderSoon: "La commande directe arrive bientot." },
      campaign: {
        title: "Creer une campagne", sub: "Decrivez votre besoin pour recevoir des propositions.",
        name: "Titre de la campagne", budget: "Budget", currency: "Devise", deadline: "Echeance",
        deliverables: "Livrables", addDeliverable: "Ajouter un livrable", publishNow: "Publier immediatement",
        create: "Creer la campagne", publish: "Publier", published: "Campagne publiee.",
        another: "Creer une autre campagne", noBudget: "Budget non defini",
        status_draft: "Brouillon", status_published: "Publiee",
        listTitle: "Mes campagnes", new: "Nouvelle campagne", listEmpty: "Vous n'avez pas encore de campagne.",
        notFound: "Campagne introuvable.",
        inviteFromFavorites: "Inviter depuis mes favoris", noFavorites: "Aucun createur favori a inviter.",
        invite: "Inviter", invitations: "Invitations", noInvitations: "Aucune invitation pour le moment.",
        proposals: "Propositions", noProposals: "Aucune proposition pour le moment.",
        accept: "Accepter et creer le contrat", viewContract: "Voir le contrat"
      },
      invitation: {
        title: "Mes invitations", sub: "Les campagnes auxquelles vous etes invite.",
        empty: "Vous n'avez pas encore d'invitation.",
        rate: "Tarif propose", days: "Delai (jours)", send: "Envoyer", proposalSent: "Proposition envoyee."
      },
      contract: {
        listTitle: "Mes contrats", listSub: "Signez vos contrats et suivez les paiements.",
        listEmpty: "Vous n'avez pas encore de contrat.", notFound: "Contrat introuvable.",
        title: "Contrat", rate: "Montant convenu", timeline: "Delai",
        businessSigned: "Signe par l'entreprise", creatorSigned: "Signe par le createur", yes: "Oui", no: "En attente",
        document: "Document du contrat", signHeading: "Signature electronique",
        typeName: "Tapez votre nom pour signer", namePlaceholder: "Nom complet", sign: "Signer",
        waitingOther: "Vous avez signe. En attente de l'autre partie.",
        payment: "Paiement (sequestre)", fundHint: "Bloquez les fonds en sequestre via Mobile Money.",
        fund: "Financer le sequestre", awaitingFunding: "En attente du financement par l'entreprise.",
        escrowStatus: "Statut du sequestre", amount: "Montant", commission: "Commission",
        release: "Confirmer et liberer", dispute: "Ouvrir un litige",
        released: "Sequestre libere, le paiement est en route.",
        disputed: "Litige en cours, un administrateur va trancher.",
        refunded: "Le sequestre a ete rembourse a l'entreprise.",
        status_pending_signatures: "En attente de signatures", status_signed: "Signe"
      },
      escrow: { status_held: "Bloque", status_released: "Libere", status_disputed: "En litige", status_refunded: "Rembourse" }
    }
  },
  en: {
    translation: {
      cat: cat.en,
      deliverable: deliverable.en,
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
        uploadPhoto: "Upload a photo", viewPublic: "View my public page", portfolio: "Portfolio", addImage: "Add an image",
        packages: "My packages", packagesHint: "Offer fixed-price services.", packageTitle: "Package title", addPackage: "Add a package"
      },
      discover: {
        title: "Discover creators", sub: "Find the right creator for your campaign.",
        category: "Category", country: "Country", minFollowers: "Min. followers", any: "Any",
        searchBtn: "Search", loading: "Loading...", empty: "No creators found.",
        creator: "Creator", verified: "Verified", followers: "followers", favorite: "Save", viewProfile: "View profile", onRequest: "Price on request"
      },
      public: { notFound: "Profile not found.", portfolio: "Portfolio", packages: "Packages", noPackages: "No packages yet.", order: "Order", orderSoon: "Direct ordering is coming soon." },
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

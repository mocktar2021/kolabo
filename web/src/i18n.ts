import i18n from "i18next";
import { initReactI18next } from "react-i18next";

/* Bilingual from day one. French is the default because the pilot markets
   (Benin and Togo) are francophone; English is a first class toggle. */
const cat = {
  fr: { fashion: "Mode", beauty: "Beaute", tech: "Tech", food: "Cuisine", travel: "Voyage", fitness: "Fitness", music: "Musique", comedy: "Humour", lifestyle: "Lifestyle", gaming: "Gaming", business: "Business", education: "Education" },
  en: { fashion: "Fashion", beauty: "Beauty", tech: "Tech", food: "Food", travel: "Travel", fitness: "Fitness", music: "Music", comedy: "Comedy", lifestyle: "Lifestyle", gaming: "Gaming", business: "Business", education: "Education" }
};

const resources = {
  fr: {
    translation: {
      cat: cat.fr,
      nav: { login: "Se connecter", signup: "Creer un compte", dashboard: "Tableau de bord", discover: "Decouvrir", profile: "Profil", logout: "Deconnexion" },
      landing: {
        eyebrow: "Marketing d'influence pour l'Afrique",
        title: "La ou les createurs et les marques se rencontrent",
        lead: "Kolabo connecte les createurs de contenu africains et les entreprises: collaborations securisees, paiements proteges, et resultats mesurables.",
        ctaCreator: "Je suis createur",
        ctaBusiness: "Je suis une marque",
        f1t: "Confiance verifiee", f1d: "Profils et entreprises verifies, pour collaborer en toute serenite.",
        f2t: "Paiements securises", f2d: "Les fonds sont bloques en sequestre et liberes une fois le travail livre.",
        f3t: "Bilingue et local", f3d: "Francais et anglais, pensee pour les paiements mobiles et les reseaux locaux."
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
        discoverTitle: "Decouvrir des createurs", discoverDesc: "Recherchez et enregistrez des createurs pour vos campagnes."
      },
      profile: {
        title: "Votre profil", sub: "Ces informations apparaissent sur la plateforme.",
        asCreator: "Profil createur", asBusiness: "Profil entreprise",
        bio: "Bio", categories: "Categories", followers: "Nombre d'abonnes",
        rate: "Tarif par publication", rateHint: "Montant indicatif en devise locale.",
        company: "Nom de l'entreprise", industry: "Secteur", description: "Description",
        save: "Enregistrer", saved: "Profil enregistre."
      },
      discover: {
        title: "Decouvrir des createurs", sub: "Trouvez le bon createur pour votre campagne.",
        category: "Categorie", country: "Pays", minFollowers: "Abonnes min.", any: "Tous",
        searchBtn: "Rechercher", loading: "Chargement...", empty: "Aucun createur trouve.",
        creator: "Createur", verified: "Verifie", followers: "abonnes", favorite: "Enregistrer"
      }
    }
  },
  en: {
    translation: {
      cat: cat.en,
      nav: { login: "Log in", signup: "Sign up", dashboard: "Dashboard", discover: "Discover", profile: "Profile", logout: "Log out" },
      landing: {
        eyebrow: "Influencer marketing for Africa",
        title: "Where creators and brands connect",
        lead: "Kolabo connects African content creators with businesses: secure collaborations, protected payments, and results you can measure.",
        ctaCreator: "I am a creator",
        ctaBusiness: "I am a brand",
        f1t: "Verified trust", f1d: "Verified profiles and businesses, so you collaborate with confidence.",
        f2t: "Secure payments", f2d: "Funds are held in escrow and released once the work is delivered.",
        f3t: "Bilingual and local", f3d: "English and French, built for mobile money and local networks."
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
        discoverTitle: "Discover creators", discoverDesc: "Search and save creators for your campaigns."
      },
      profile: {
        title: "Your profile", sub: "This information appears across the platform.",
        asCreator: "Creator profile", asBusiness: "Business profile",
        bio: "Bio", categories: "Categories", followers: "Follower count",
        rate: "Rate per post", rateHint: "Indicative amount in local currency.",
        company: "Company name", industry: "Industry", description: "Description",
        save: "Save", saved: "Profile saved."
      },
      discover: {
        title: "Discover creators", sub: "Find the right creator for your campaign.",
        category: "Category", country: "Country", minFollowers: "Min. followers", any: "Any",
        searchBtn: "Search", loading: "Loading...", empty: "No creators found.",
        creator: "Creator", verified: "Verified", followers: "followers", favorite: "Save"
      }
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

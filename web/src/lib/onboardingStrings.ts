/* Onboarding wizard strings, registered as a resource bundle so the main i18n
   file stays focused on the core app copy. */
import i18n from "../i18n";

const fr = {
  step1: "Votre profil", step2: "Tarifs", step3: "Mise en ligne",
  title1: "Configuration rapide du profil",
  sub1: "Ajoutez vos réseaux sociaux, puis complétez les informations qui manquent.",
  addSocials: "Ajoutez vos réseaux sociaux",
  socialHint: "Le lien du compte est enregistré. La vérification et le remplissage automatique arrivent avec la connexion officielle aux plateformes.",
  added: "Ajouté",
  removeSocial: "Retirer ce compte",
  handleQuestion: "Quel est votre identifiant sur {{platform}}?",
  yourHandle: "votreidentifiant",
  cancel: "Annuler", addToProfile: "Ajouter au profil",
  title2: "Vos tarifs", sub2: "Publiez au moins une offre à prix fixe pour que les marques puissent commander.",
  title3: "Mise en ligne", sub3: "Vérifions que votre profil est complet.",
  checkBio: "Bio renseignée", checkCategories: "Au moins une catégorie",
  checkPricing: "Au moins une offre publiée", checkSocial: "Un réseau social ajouté",
  liveNow: "Votre profil est en ligne et visible dans la recherche.",
  notLive: "Il manque encore des éléments avant la mise en ligne.",
  yourLink: "Votre lien public", copy: "Copier",
  linkHint: "Partagez ce lien dans votre bio pour recevoir des demandes de marques.",
  viewProfile: "Voir mon profil", goDashboard: "Aller au tableau de bord",
  continue: "Continuer", back: "Retour"
};

const en = {
  step1: "Your profile", step2: "Pricing", step3: "Go live",
  title1: "Quick profile set up",
  sub1: "Add your social profiles, then fill in anything still missing.",
  addSocials: "Add your social profiles",
  socialHint: "We save the account link. Verification and auto fill arrive with the official platform connection.",
  added: "Added",
  removeSocial: "Remove this account",
  handleQuestion: "What is your handle on {{platform}}?",
  yourHandle: "yourhandle",
  cancel: "Cancel", addToProfile: "Add to profile",
  title2: "Your pricing", sub2: "Publish at least one fixed price package so brands can order.",
  title3: "Go live", sub3: "Let us check your profile is complete.",
  checkBio: "Bio added", checkCategories: "At least one category",
  checkPricing: "At least one published package", checkSocial: "A social profile added",
  liveNow: "Your profile is live and visible in search.",
  notLive: "A few things are still missing before you can go live.",
  yourLink: "Your public link", copy: "Copy",
  linkHint: "Share this link in your bio to receive requests from brands.",
  viewProfile: "View my profile", goDashboard: "Go to dashboard",
  continue: "Continue", back: "Back"
};

i18n.addResourceBundle("fr", "translation", { onb: fr }, true, true);
i18n.addResourceBundle("en", "translation", { onb: en }, true, true);

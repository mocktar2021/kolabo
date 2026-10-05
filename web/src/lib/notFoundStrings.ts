/* The catch-all page's copy. Owns the notFound.* group outright, so unlike
   the bundles that add keys into a group i18n.ts owns, this one carries no
   ordering constraint in main.tsx.

   PUNCTUATION, because this directory has two conventions and they are not
   interchangeable. The French uses the curly apostrophe the rest of the app's
   French copy uses, and a plain space where a space is needed, the way
   adminStrings.ts does. legalStrings.ts is the one file here that writes
   non-breaking spaces as escapes, and its reasons are its own. Separately,
   punctuation.test.ts walks every .ts and .tsx under web/src and fails the
   build on an em or en dash inside any string, so there are none here. */
import i18n from "../i18n";

const fr = {
  title: "Page introuvable",
  body:
    "Cette adresse ne correspond à aucune page de Kolabo. Elle a peut-être été mal saisie, ou la page a changé de place.",
  home: "Retour à l’accueil",
  discover: "Découvrir les créateurs",
  /* A reviewer who mistypes a legal URL is one of the reasons this page
     exists, so the way back to the policy is ON it rather than a menu away. */
  privacy: "Politique de confidentialité"
};

const en = {
  title: "Page not found",
  body:
    "This address does not match any page on Kolabo. It may have been mistyped, or the page may have moved.",
  home: "Back to the home page",
  discover: "Discover creators",
  privacy: "Privacy policy"
};

i18n.addResourceBundle("fr", "translation", { notFound: fr }, true, true);
i18n.addResourceBundle("en", "translation", { notFound: en }, true, true);

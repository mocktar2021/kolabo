/* The copy for installing Kolabo to a home screen or a desktop.

   OWNS THE install.* GROUP OUTRIGHT, so it carries no ordering constraint in
   main.tsx and joins nothing anybody else owns.

   WHY THERE IS AN iOS BRANCH AT ALL. Chrome, Edge and Samsung Internet fire
   beforeinstallprompt, so there the button can do the whole job in one tap:
   the browser's own install dialog opens and that is that. Safari fires
   nothing and exposes no API, so on an iPhone the only way in is Share then
   "Add to Home Screen", done by hand. The honest answer there is a short set
   of directions rather than a button that would appear to do something and
   then do nothing, which is why these two paths read differently.

   THE SHARE ICON IS DESCRIBED RATHER THAN DRAWN. "the Share button" plus
   where it sits is findable; a glyph copied into a sentence renders as a box
   on half the devices that would need it. */
import i18n from "../i18n";

export const install_fr = {
  button: "Installer l'application",
  dismiss: "Masquer",
  iosTitle: "Installer Kolabo sur votre iPhone",
  iosStep1: "Touchez le bouton Partager en bas de Safari.",
  iosStep2: "Faites défiler et choisissez Sur l'écran d'accueil.",
  iosStep3: "Touchez Ajouter. Kolabo apparaît avec vos autres applications.",
  iosClose: "J'ai compris"
};

export const install_en = {
  button: "Install the app",
  dismiss: "Hide",
  iosTitle: "Install Kolabo on your iPhone",
  iosStep1: "Tap the Share button at the bottom of Safari.",
  iosStep2: "Scroll down and choose Add to Home Screen.",
  iosStep3: "Tap Add. Kolabo appears with your other apps.",
  iosClose: "Got it"
};

i18n.addResourceBundle("fr", "translation", { install: install_fr }, true, true);
i18n.addResourceBundle("en", "translation", { install: install_en }, true, true);

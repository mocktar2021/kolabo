/* Copy for the connected-accounts section of the profile form, registered as
   a resource bundle so the 40 KB i18n.ts stays focused on the core app copy —
   the same arrangement the cart, the open board, the notifications bell, the
   disputes queue, the admin console, the account settings and the two money
   screens use.

   The keys are deep-merged into the profile.* group i18n.ts already owns:
   addResourceBundle runs with deep=true and overwrite=true, and main.tsx
   imports this after "./i18n", so they join that group rather than replacing
   it. */
import i18n from "../i18n";

const fr = {
  /* Pourquoi le champ « abonnés » n'apparaît pas sur certaines plateformes.
     Dit plutôt que laissé à deviner : un créateur qui compte sur son audience
     WhatsApp remarquera l'absence du champ et se demandera ce qui a cassé.
     Le vrai motif est qu'il n'existe aucun chiffre public à vérifier, et un
     nombre que la plateforme ne peut pas confirmer est exactement celui
     qu'une marque utilisera pour choisir avant de découvrir qu'il était
     inventé. */
  noAudienceHint: "Cette plateforme ne publie aucun nombre d'abonnés vérifiable, donc Kolabo n'en demande pas et n'en affiche pas. Votre compte reste visible sur votre profil et vous pouvez vendre dessus normalement."
};

const en = {
  noAudienceHint: "This platform publishes no verifiable follower count, so Kolabo neither asks for one nor shows one. Your account still appears on your profile and you can sell on it as normal."
};

i18n.addResourceBundle("fr", "translation", { profile: fr }, true, true);
i18n.addResourceBundle("en", "translation", { profile: en }, true, true);

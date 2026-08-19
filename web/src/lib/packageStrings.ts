/* Copy for the per-package Active switch in the profile form's packages
   section, registered as a resource bundle for the same reason
   socialStrings.ts is: the 40 KB i18n.ts stays about core app copy.

   The keys are deep-merged into the profile.* group i18n.ts already owns:
   addResourceBundle runs with deep=true and overwrite=true, and main.tsx
   imports this after "./i18n", so they join that group rather than replacing
   it.

   THE THRESHOLD IS NEVER SPELLED OUT AS A DIGIT. {{min}} is interpolated from
   MIN_LIVE_PACKAGES in lib/pricing.ts, which mirrors
   backend/app/core/pricing.py. A "3" typed into these two sentences would be
   two more places to remember on the day the storefront rule changes, and
   both of them would go on reading like the truth. */
import i18n from "../i18n";

const fr = {
  /* Accord au féminin : le reste de cette section dit « offre »
     (profile.packages = « Mes offres »), donc « Active » et « Inactive ». Le
     client mobile dit « pack » et accorde au masculin. */
  packageActive: "Active",
  packageInactive: "Inactive",
  /* Dit au moment où la case est décochée, et seulement quand ce clic-là fait
     passer sous le seuil. Informer, pas empêcher : mettre une offre en pause
     est légitime, disparaître des recherches sans le savoir ne l'est pas. */
  packageDeactivateWarning: "Il vous faut {{min}} offres actives pour apparaître dans les recherches. Si vous la désactivez, les marques ne vous trouveront plus tant que vous n'en réactivez pas une autre."
};

const en = {
  packageActive: "Active",
  packageInactive: "Inactive",
  packageDeactivateWarning: "You need {{min}} active packages to appear in search. Turn this off and brands will not find you until you activate another."
};

i18n.addResourceBundle("fr", "translation", { profile: fr }, true, true);
i18n.addResourceBundle("en", "translation", { profile: en }, true, true);

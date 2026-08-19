import i18n from "../i18n";

/* Copy for the per-package Actif switch in the profile screen's packages
   section, registered at runtime for the same reason paymentStrings.ts is:
   src/strings.ts is 60 KB, and a four-key change lands there invisibly. The
   keys are deep-merged into the profile.* group strings.ts already owns —
   addResourceBundle runs with deep=true and overwrite=true — so
   PackagesSection imports this module for its side effect. Anything that
   outgrows this one switch belongs back in strings.ts.

   THE THRESHOLD IS NEVER SPELLED OUT AS A DIGIT. {{min}} is interpolated from
   MIN_LIVE_PACKAGES in lib/pricing.ts, which mirrors
   backend/app/core/pricing.py. A "3" typed into these sentences would be two
   more places to remember on the day the storefront rule changes, and both of
   them would go on reading like the truth.

   French first, like the other bundle: it is the pilot default. */

const fr = {
  /* Accord au masculin : cette section dit « pack » (profile.packagesTitle =
     « Packs », profile.checkPricing = « Trois packs actifs »), donc « Actif »
     et « Inactif ». Le client web dit « offre » et accorde au féminin — les
     deux sont justes, chacun dans son écran. */
  packageActive: "Actif",
  packageInactive: "Inactif",
  /* Dit au moment où l'interrupteur est basculé, et seulement quand ce
     geste-là fait passer sous le seuil. Informer, pas empêcher : mettre un
     pack en pause est légitime, disparaître des recherches sans le savoir ne
     l'est pas. */
  packageDeactivateWarning: "Il vous faut {{min}} packs actifs pour apparaître dans les recherches. Si vous le désactivez, les marques ne vous trouveront plus tant que vous n'en réactivez pas un autre.",
  packageDeactivateConfirm: "Désactiver quand même",
};

const en = {
  packageActive: "Active",
  packageInactive: "Inactive",
  packageDeactivateWarning: "You need {{min}} active packages to appear in search. Turn this off and brands will not find you until you activate another.",
  packageDeactivateConfirm: "Turn it off anyway",
};

i18n.addResourceBundle("fr", "translation", { profile: fr }, true, true);
i18n.addResourceBundle("en", "translation", { profile: en }, true, true);

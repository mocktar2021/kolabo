import i18n from "../i18n";

/* Copy for the Connect path in the profile screen's socials section,
   registered at runtime for the same reason packageStrings.ts and
   paymentStrings.ts are: src/strings.ts is 60 KB, and a three-key change
   lands there invisibly. The keys are deep-merged into the profile.* group
   strings.ts already owns, beside socialTitle, socialSub, socialAdd and
   handleFor, so SocialsSection imports this module for its side effect.
   Anything that outgrows these three keys belongs back in strings.ts.

   ONLY THREE KEYS, and that is the point rather than an accident. The FAILURE
   sentences are deliberately not here. A social_error code coming back on the
   callback is one of oauth_exchange_failed, oauth_state_expired or
   oauth_state_invalid, and errorMessages.ts already carries every one of them
   in both languages: the backend raises them, and tests/errorMessages.test.ts
   refuses to go green on a backend code with nowhere to land. Writing a
   second sentence for any of them here would put two translations of one
   refusal in the app with nothing to say which is current.

   French first, like the other bundles: it is the pilot default, and three of
   the five launch countries are francophone. */

const fr = {
  socialConnectCta: "Connecter {{platform}}",
  /* Dit ce que la connexion APPORTE au créateur, pas ce qu'elle lui coûte, et
     dit dans la même phrase que le champ en dessous marche toujours. Un
     créateur qui ne veut pas nous confier de jeton doit pouvoir lire cette
     ligne et continuer. */
  socialConnectHint:
    "En vous connectant, {{platform}} confirme la page et son nombre d'abonnés. Vous pouvez aussi saisir votre identifiant vous-même, mais il apparaîtra sans chiffre vérifié.",
  /* Nomme la plateforme deux fois, exprès : ce qui change vraiment ici, c'est
     d'où vient le chiffre, et c'est la seule phrase de l'écran qui le dit. */
  socialConnected:
    "{{platform}} est connecté. Le nombre d'abonnés affiché vient maintenant de {{platform}}.",
};

const en = {
  socialConnectCta: "Connect {{platform}}",
  socialConnectHint:
    "Connecting lets {{platform}} confirm the page and its follower count. You can also type your handle yourself, but it will show with no verified number behind it.",
  socialConnected:
    "{{platform}} is connected. The follower count now comes from {{platform}} itself.",
};

i18n.addResourceBundle("fr", "translation", { profile: fr }, true, true);
i18n.addResourceBundle("en", "translation", { profile: en }, true, true);

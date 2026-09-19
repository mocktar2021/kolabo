import i18n from "../i18n";

/* Copy for the Connect path in the profile screen's socials section,
   registered at runtime for the same reason packageStrings.ts and
   paymentStrings.ts are: src/strings.ts is 61 KB, and a handful of keys lands
   there invisibly. They are deep-merged into the profile.* group strings.ts
   already owns, beside socialTitle, socialSub, socialAdd and handleFor, so
   SocialsSection imports this module for its side effect. Anything that
   outgrows one section's worth of copy belongs back in strings.ts.

   THREE GROUPS NOW, AND THE THIRD IS READ BY A SECOND SCREEN.
   socialConnect* is the handshake. socialPage* is the question that follows
   it for a creator who administers more than one Facebook Page: the
   connection worked perfectly, and the backend recorded no follower count on
   purpose rather than guess which of somebody's businesses is the one they
   sell. See oauth_service.list_pages and select_page.

   socialStatus*, socialFollowers* and socialAudienceTitle are the third
   group: what an account's state is called, and where its follower number
   came from. They are rendered by SocialsSection AND by CreatorPublicScreen,
   which is why that screen now carries the same side-effect import. They
   stay in this bundle rather than moving to strings.ts because they are the
   same feature as the two groups above, and splitting one feature's copy
   across two files is how half of it ends up translated.

   "pending" AND "verified" KEEP THE KEYS THEY ALREADY HAD, profile.pending
   and profile.verified in strings.ts. Only the two states that had no copy
   at all, connected and rejected, are written here. A second translation of
   the word verified in this file would be exactly the duplication the
   paragraph below refuses for error sentences.

   NO FAILURE SENTENCE IS WRITTEN HERE, and that is the point rather than an
   accident. A social_error code coming back on the callback is one of
   oauth_exchange_failed, oauth_state_expired or oauth_state_invalid, and the
   picker can raise oauth_page_not_found, oauth_token_expired or
   oauth_exchange_failed. Every one of those is a backend code, so its French
   and English sentences belong in errorMessages.ts: the backend raises them,
   and tests/errorMessages.test.ts refuses to go green on a backend code with
   nowhere to land. Writing a second sentence for any of them here would put
   two translations of one refusal in the app with nothing to say which is
   current.

   oauth_page_not_found ARRIVES WITH THE ENDPOINTS, not ahead of them. The
   backend PR that adds the two routes adds that code to both catalogues in
   the same change, which is the right place for it. Until that lands,
   errorText falls through to the backend's own English detail, which is the
   documented fallback rather than a hole to paper over from here.

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

  /* La page vendue, quand la plateforme en a renvoyé plusieurs et que le
     backend a refusé de choisir à la place du créateur.

     La phrase doit dire trois choses dans cet ordre : rien n'est cassé,
     voilà pourquoi il n'y a pas de chiffre, voilà quoi faire. Jusqu'ici
     l'écran ne disait aucune des trois. */
  socialPageWhy:
    "{{platform}} n'a pas dit quelle page ce compte vend, donc aucun nombre d'abonnés n'a été enregistré. Choisissez votre page : son nom et ses abonnés remplaceront l'identifiant affiché ici.",
  socialPageChoose: "Choisir votre page",
  socialPageTitle: "Quelle page vendez-vous ?",
  socialPageFollowers: "{{followers}} abonnés",
  /* Une page dont la plateforme n'a pas donné le nombre d'abonnés. On le dit,
     plutôt que d'afficher zéro : zéro est un chiffre, et celui-là n'existe
     pas. */
  socialPageFollowersUnknown: "Nombre d'abonnés non communiqué",
  socialPageUnnamed: "Page sans nom",
  /* Zéro page. Le compte est bien connecté, il n'y a simplement rien à vendre
     dessus, et une phrase vaut mieux qu'une feuille vide, qui ne dit que
     « quelque chose a raté ». */
  socialPageNone:
    "Aucune page n'est rattachée à ce compte {{platform}}. Créez une page sur {{platform}}, puis reconnectez le compte ici.",
  socialPageChosen:
    "Page enregistrée. Le nom et le nombre d'abonnés affichés viennent maintenant de {{platform}}.",

  /* L'état du compte, pour les deux valeurs qui n'avaient aucun libellé.
     « connecté » n'est pas « vérifié » et ne doit pas en avoir l'air : le
     créateur a prouvé qu'il contrôle le compte, personne n'a vérifié qui il
     est. */
  socialStatusConnected: "Connecté",
  socialStatusRejected: "Refusé",

  /* LA PROVENANCE DU CHIFFRE, DITE DES DEUX CÔTÉS.

     Un nombre lu chez la plateforme porte la date de la lecture. Un nombre
     saisi par le créateur le dit franchement. Ne marquer qu'un seul des deux
     et laisser deviner l'autre, c'est exactement le défaut que ces lignes
     corrigent : sur la page qu'une marque lit avant de dépenser, un chiffre
     tapé dans un formulaire s'affichait comme un chiffre contrôlé.

     Le mot « vérifié » ne sort JAMAIS pour un chiffre déclaré, et il nomme
     la plateforme : c'est le compte qui a été vérifié, pas l'identité de la
     personne. */
  socialFollowersChecked: "Vérifié auprès de {{platform}} le {{date}}",
  socialFollowersCheckedUndated: "Vérifié auprès de {{platform}}",
  socialFollowersSelf: "Chiffre annoncé par le créateur, non vérifié",

  /* Le titre de la section sur la page publique, là où une marque lit ces
     chiffres avant de dépenser. */
  socialAudienceTitle: "Audience par plateforme",
};

const en = {
  socialConnectCta: "Connect {{platform}}",
  socialConnectHint:
    "Connecting lets {{platform}} confirm the page and its follower count. You can also type your handle yourself, but it will show with no verified number behind it.",
  socialConnected:
    "{{platform}} is connected. The follower count now comes from {{platform}} itself.",

  socialPageWhy:
    "{{platform}} did not say which Page this account sells on, so no follower count was recorded. Choose your Page and its name and followers will replace the id shown here.",
  socialPageChoose: "Choose your Page",
  socialPageTitle: "Which Page do you sell on?",
  socialPageFollowers: "{{followers}} followers",
  socialPageFollowersUnknown: "No follower count given",
  socialPageUnnamed: "Unnamed Page",
  socialPageNone:
    "There are no Pages on this {{platform}} account. Create one on {{platform}}, then connect the account again here.",
  socialPageChosen:
    "Page saved. The name and follower count shown now come from {{platform}} itself.",

  socialStatusConnected: "Connected",
  socialStatusRejected: "Rejected",

  socialFollowersChecked: "Verified with {{platform}} on {{date}}",
  socialFollowersCheckedUndated: "Verified with {{platform}}",
  socialFollowersSelf: "The creator's own figure, not checked",

  socialAudienceTitle: "Audience by platform",
};

i18n.addResourceBundle("fr", "translation", { profile: fr }, true, true);
i18n.addResourceBundle("en", "translation", { profile: en }, true, true);

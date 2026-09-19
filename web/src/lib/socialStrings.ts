/* Copy for the connected-accounts section of the profile form, registered as
   a resource bundle so the 40 KB i18n.ts stays focused on the core app copy —
   the same arrangement the cart, the open board, the notifications bell, the
   disputes queue, the admin console, the account settings and the two money
   screens use.

   The keys are deep-merged into the profile.* group i18n.ts already owns:
   addResourceBundle runs with deep=true and overwrite=true, and main.tsx
   imports this after "./i18n", so they join that group rather than replacing
   it.

   TWO GROUPS NOW, NOT ONE. public.connectedAccount joins the public.* group
   that i18n.ts also owns, under the same ordering rule and for a plain
   reason: it is the tooltip that sits beside public.verifiedAccount on the
   creator page, and two sentences a reader compares should be findable side
   by side. Everything else stays in profile.*, including the follower
   provenance sentences, which the public page reads from there rather than
   owning a second copy of: one fact, one wording, two screens that cannot
   drift apart. */
import i18n from "../i18n";

const fr = {
  /* Pourquoi le champ « abonnés » n'apparaît pas sur certaines plateformes.
     Dit plutôt que laissé à deviner : un créateur qui compte sur son audience
     WhatsApp remarquera l'absence du champ et se demandera ce qui a cassé.
     Le vrai motif est qu'il n'existe aucun chiffre public à vérifier, et un
     nombre que la plateforme ne peut pas confirmer est exactement celui
     qu'une marque utilisera pour choisir avant de découvrir qu'il était
     inventé. */
  noAudienceHint: "Cette plateforme ne publie aucun nombre d'abonnés vérifiable, donc Kolabo n'en demande pas et n'en affiche pas. Votre compte reste visible sur votre profil et vous pouvez vendre dessus normalement.",
  /* Le chemin « connecter », à côté du chemin « saisir un identifiant ».
     Les deux restent, et la phrase le dit : saisir un identifiant revendique
     un compte, se connecter le prouve. Un créateur qui refuse l'écran de
     consentement, qui n'a pas de Page ou qui ne veut pas donner de
     permissions à une application doit toujours pouvoir dire où il est. */
  socialConnectWith: "Connecter mon compte {{platform}}",
  socialConnectHint: "La connexion demande à {{platform}} de confirmer le compte et son nombre d'abonnés. Vous pouvez aussi ajouter un compte plus bas en saisissant votre identifiant : c'est plus rapide, mais le nombre d'abonnés reste alors déclaratif.",
  /* Au retour de l'écran de consentement. Il n'y a pas de phrase d'échec
     ici : le backend renvoie un code d'erreur qui existait déjà, et les deux
     catalogues portent déjà sa phrase française. En écrire une seconde
     serait une deuxième phrase pour le même fait, libre de diverger. */
  socialConnected: "Votre compte {{platform}} est connecté. Ce que la plateforme publie à son sujet apparaît ci-dessus.",
  /* CHOISIR SA PAGE, et pourquoi cet écran existe.

     Un créateur qui administre plusieurs Pages Facebook repart de l'écran de
     consentement avec une ligne qui porte l'identifiant numérique renvoyé
     par la plateforme et aucun nombre d'abonnés. Le backend refuse de
     deviner laquelle de ces Pages est sa vitrine, ce qui est la bonne
     décision : publier le chiffre d'une Page qu'il n'a pas choisie mettrait
     sur son profil, avec la mention "vérifié par la plateforme", le seul
     nombre qu'une marque lit avant de payer. Ces phrases sont la question
     posée au créateur à la place.

     socialPageWhy ne dit pas combien de Pages il administre, parce que la
     ligne du profil ne le sait pas : elle sait seulement qu'aucun nombre
     n'est enregistré. Zéro Page et quatre Pages arrivent ici de la même
     façon, et la liste est le seul endroit qui peut les distinguer.

     Aucune phrase d'erreur ici. oauth_page_not_found, oauth_token_expired et
     oauth_exchange_failed sont des codes du backend, et errorText va chercher
     leur phrase dans errorMessages.ts comme pour tous les autres refus. */
  socialChoosePage: "Choisir votre Page",
  socialPageWhy: "Aucun nombre d'abonnés n'est enregistré pour ce compte. Choisissez la Page que vous vendez pour afficher son nom et ses abonnés.",
  socialPageTitle: "Sur quelle Page {{platform}} vendez-vous ?",
  socialPageHint: "Kolabo n'en choisit aucune à votre place. Vous gardez une seule Page par compte : celle que vous choisissez ici donne son nom et son nombre d'abonnés à votre profil.",
  socialPageEmpty: "{{platform}} ne nous renvoie aucune Page pour ce compte. Créez une Page, puis reconnectez le compte. En attendant, votre compte reste sur votre profil, sans nombre d'abonnés.",
  socialPageSelected: "C'est noté. Votre profil affiche maintenant {{page}} et son nombre d'abonnés.",
  /* Le nom peut manquer : SocialPageOut le déclare nullable, et une ligne
     sans étiquette n'est pas un choix qu'on peut faire. */
  socialPageUnnamed: "Page sans nom",
  /* LES QUATRE ÉTATS D'UN COMPTE, dits en quatre mots différents.

     « Connecté » n'est pas « En attente ». Un créateur qui s'était connecté
     à Facebook, avait donné les permissions et avait choisi sa Page lisait
     jusqu'ici la même pastille que quelqu'un qui avait tapé un identifiant
     dans une case sans rien prouver. Et « Vérifié » reste réservé à la
     décision d'un administrateur qui a lu une pièce d'identité : une
     connexion sociale prouve qu'on détient les identifiants d'un compte,
     jamais qui on est.

     « Refusé » gagne aussi son propre mot, pour la même raison : il
     s'affichait en « En attente », c'est-à-dire comme une décision qui
     n'aurait pas encore eu lieu, alors qu'elle a eu lieu et qu'elle était
     négative. */
  socialConnectedBadge: "Connecté",
  socialRejected: "Refusé",
  /* D'OÙ VIENT LE NOMBRE D'ABONNÉS, et les deux côtés sont marqués.

     Un chiffre sans mention oblige la marque à deviner ce qu'il vaut, et
     c'est exactement ce qui est corrigé ici : un nombre lu dans l'API de la
     plateforme porte la date de sa lecture, un nombre saisi par le créateur
     le dit. Le mot « vérifié » ne sert jamais au second.

     followerUnknown couvre les lignes écrites avant que l'origine soit
     enregistrée. Elles gardent leur nombre et ne reçoivent aucune des deux
     autres mentions : nous ne savons pas d'où vient ce chiffre, et choisir
     « déclaré » ou « vérifié » au hasard serait affirmer une chose que
     personne n'a constatée.

     Les formes courtes tiennent dans la pastille de la page publique, juste
     après le nombre lui-même ; les formes longues portent la date et
     s'affichent sous le grand chiffre et sur le formulaire du créateur. */
  followerChecked: "Vérifié auprès de la plateforme le {{date}}",
  followerDeclared: "Déclaré par le créateur, non vérifié",
  followerUnknown: "Origine non enregistrée : ce compte est antérieur au suivi de la provenance des chiffres",
  followerCheckedShort: "vérifié",
  followerDeclaredShort: "déclaré",
  followerUnknownShort: "origine inconnue"
};

const en = {
  noAudienceHint: "This platform publishes no verifiable follower count, so Kolabo neither asks for one nor shows one. Your account still appears on your profile and you can sell on it as normal.",
  socialConnectWith: "Connect with {{platform}}",
  socialConnectHint: "Connecting asks {{platform}} itself to confirm the account and its follower count. You can also add an account below by typing your handle: that is quicker, but the follower number is then only your own word for it.",
  socialConnected: "Your {{platform}} account is connected. Whatever the platform publishes about it is shown above.",
  socialChoosePage: "Choose your Page",
  socialPageWhy: "No follower count is recorded for this account. Choose the Page you sell on to show its name and its followers.",
  socialPageTitle: "Which {{platform}} Page do you sell on?",
  socialPageHint: "Kolabo does not pick one for you. You keep one Page per account: the one you choose here gives your profile its name and its follower count.",
  socialPageEmpty: "{{platform}} returns no Page for this account. Create a Page, then reconnect the account. Until then your account stays on your profile, without a follower count.",
  socialPageSelected: "Done. Your profile now shows {{page}} and its follower count.",
  socialPageUnnamed: "Unnamed Page",
  socialConnectedBadge: "Connected",
  socialRejected: "Rejected",
  followerChecked: "Verified with the platform on {{date}}",
  followerDeclared: "Declared by the creator, not checked",
  followerUnknown: "Source not recorded: this account predates the tracking of where follower numbers come from",
  followerCheckedShort: "checked",
  followerDeclaredShort: "declared",
  followerUnknownShort: "source unknown"
};

/* The tooltip on the quiet mark the public page gives a connected account,
   beside the public.verifiedAccount that the strong mark already carries.

   IT SAYS BOTH HALVES, because saying only the flattering one is how
   "connected" would quietly come to mean "verified" in a reader's head. The
   platform confirmed the account. Nobody confirmed the person. */
const publicFr = {
  connectedAccount: "Compte connecté : le créateur s'est authentifié auprès de la plateforme, qui a confirmé le compte. L'identité de la personne n'a pas été vérifiée."
};

const publicEn = {
  connectedAccount: "Connected account: the creator signed in with the platform and the platform confirmed the account. The person's identity has not been checked."
};

i18n.addResourceBundle("fr", "translation", { profile: fr, public: publicFr }, true, true);
i18n.addResourceBundle("en", "translation", { profile: en, public: publicEn }, true, true);

/* Copy for signing in with Google: the two auth screens, and the proof of
   ownership the account screen now accepts in two forms.

   TWO GROUPS, BOTH OF THEM SOMEBODY ELSE'S. `auth` belongs to i18n.ts and
   `account` belongs to accountStrings.ts, so this bundle adds keys to each
   rather than owning a namespace of its own. addResourceBundle is called with
   deep=true and overwrite=true and main.tsx imports this file AFTER both of
   those, which is the whole of the ordering constraint and the same
   arrangement notificationStrings, socialStrings and packageStrings already
   carry. A namespace of its own would have put a role label somewhere nobody
   would look for one.

   The delete panel keeps danger.confirmPassword for its password field and
   reaches for account.proofLabel on the Google branch, rather than carrying a
   third copy of the same four words in a third group.

   THE OBJECTS ARE EXPORTED, unlike the other feature bundles, so that
   googleStrings.test.ts can hold the two languages against each other. The web
   app is bilingual by construction and a key present in one language and not
   the other does not fail anything on its own: i18next falls back, the English
   appears in the middle of a French screen, and the build is green. The same
   reason errorMessages.ts and notificationBodies.ts export theirs.

   WHAT IS DELIBERATELY NOT HERE. The words on the Google button itself.
   Google draws that control and localises its own label from the `locale`
   option, which is why components/GoogleSignInButton.tsx passes i18n.language
   into it and owns no text at all. */
import i18n from "../i18n";

/* Added to the `auth` group i18n.ts owns. */
export const google_auth_fr = {
  googleOr: "ou",
  googleScriptFailed:
    "Le bouton Google n'a pas pu se charger. Connectez-vous avec votre adresse e-mail et votre mot de passe.",
  /* Shown only after a refused sign in, and only beside the password field.
     The server answers the same vague refusal for a wrong password and for an
     account created through Google, on purpose: a distinct code would tell
     anybody holding a list of addresses which of them are registered here. So
     the client cannot know which of the two it was either, and this sentence
     does not pretend to. */
  googleWrongPassword:
    "Si vous avez créé ce compte avec Google, il n'a pas de mot de passe. Utilisez le bouton Google au-dessus.",
  googleAskTitle: "Encore deux questions",
  googleAskIntro:
    "Google nous dit qui vous êtes. Il ne peut pas nous dire dans quel pays vous travaillez, ni si vous venez ici pour vendre ou pour acheter. Répondez, et nous créons votre compte.",
  googleAskSubmit: "Créer mon compte",
  googleAskCancel: "Annuler",
  /* On the register screen only. The button sits under the form because the
     two answers it sends are collected IN that form, so a person who reaches
     for Google first would be signed up as whatever the defaults happen to
     say. Saying so is cheaper than moving the fields. */
  googleUsesAbove:
    "Le bouton Google utilise le rôle et le pays choisis ci-dessus. Aucun mot de passe ne vous sera demandé."
};

export const google_auth_en = {
  googleOr: "or",
  googleScriptFailed:
    "The Google button could not load. Sign in with your email address and password.",
  googleWrongPassword:
    "If you created this account with Google, it has no password. Use the Google button above.",
  googleAskTitle: "Two more questions",
  googleAskIntro:
    "Google tells us who you are. It cannot tell us which country you work in, or whether you came here to sell or to buy. Answer those, and we create your account.",
  googleAskSubmit: "Create my account",
  googleAskCancel: "Cancel",
  googleUsesAbove:
    "The Google button uses the role and the country chosen above. You will not be asked for a password."
};

/* Added to the `account` group accountStrings.ts owns. */
export const google_account_fr = {
  googleTitle: "Connexion avec Google",
  googleLinkedYes:
    "Ce compte est relié à Google. Vous pouvez vous connecter avec le bouton Google, et confirmer avec Google les changements qui demandent normalement votre mot de passe.",
  googleLinkedNo:
    "Ce compte n'est pas relié à Google. Connectez-vous une fois avec le bouton Google, à cette même adresse, et le lien se fera tout seul.",
  /* Said rather than hidden. No endpoint clears the link, so a "Disconnect"
     button would be a button that lies. The row is informational and says so.
     */
  googleNoDisconnect:
    "Il n'y a pas encore de quoi délier ce compte : rien côté serveur n'efface ce lien. Cette ligne est donc informative.",
  proofLabel: "Confirmez que c'est bien vous",
  /* Only offered after Google has been offered first. See the proof control
     in pages/Account.tsx for why that is the order. */
  proofUsePassword: "Utiliser plutôt mon mot de passe",
  proofUseGoogle: "Confirmer plutôt avec Google",
  proofGoogleReady: "Confirmé avec Google. Enregistrez pour appliquer le changement.",
  proofGoogleRedo: "Recommencer avec Google",
  /* The same two paragraphs account.emailWhyPassword and
     account.phoneWhyPassword already say, for an account that may have no
     password to spend. Two variants rather than one vaguer sentence: the
     takeover argument is the reason the price exists, and dropping it to save
     a key would leave the field looking like paperwork. */
  emailWhyProof:
    "Votre adresse e-mail est votre identifiant de connexion. La modifier demande une preuve que c'est bien vous : votre mot de passe actuel, ou une confirmation avec Google. Un appareil resté ouvert ne doit pas suffire à faire basculer un compte vers une autre adresse.",
  phoneWhyProof:
    "Votre numéro sert à vos versements Mobile Money. Il est facultatif et ne sert pas à vous connecter. Le modifier demande une preuve que c'est bien vous : votre mot de passe actuel, ou une confirmation avec Google. Un appareil resté ouvert ne doit pas suffire à rediriger l'argent de quelqu'un.",
  /* Conditional on purpose. The server tells us the account is linked to
     Google; it does not tell us whether the account also has a usable
     password, and no field on /auth/me could without saying more about the
     credentials than a settings screen needs. So this says "if". */
  passwordMaybeFirst:
    "Si ce compte a été créé avec Google, il n'a pas encore de mot de passe. En définir un ici ajoute une deuxième façon d'entrer ; le bouton Google continue de fonctionner."
};

export const google_account_en = {
  googleTitle: "Signing in with Google",
  googleLinkedYes:
    "This account is connected to Google. You can sign in with the Google button, and confirm with Google the changes that normally cost your password.",
  googleLinkedNo:
    "This account is not connected to Google. Sign in once with the Google button, at this same address, and the link makes itself.",
  googleNoDisconnect:
    "There is nothing here to disconnect with yet: nothing server-side clears this link. So this row is informational.",
  proofLabel: "Confirm it is you",
  proofUsePassword: "Use my password instead",
  proofUseGoogle: "Confirm with Google instead",
  proofGoogleReady: "Confirmed with Google. Save to apply the change.",
  proofGoogleRedo: "Start again with Google",
  emailWhyProof:
    "Your email address is your sign-in identity. Changing it costs proof that it is you: your current password, or a confirmation with Google. A device left open must not be enough to move an account onto somebody else's address.",
  phoneWhyProof:
    "Your phone number is where your Mobile Money payouts go. It is optional and it is not how you sign in. Changing it costs proof that it is you: your current password, or a confirmation with Google. A device left open must not be enough to redirect somebody's money.",
  passwordMaybeFirst:
    "If this account was created with Google, it has no password yet. Setting one here adds a second way in, and the Google button keeps working."
};

i18n.addResourceBundle(
  "fr",
  "translation",
  { auth: google_auth_fr, account: google_account_fr },
  true,
  true
);
i18n.addResourceBundle(
  "en",
  "translation",
  { auth: google_auth_en, account: google_account_en },
  true,
  true
);

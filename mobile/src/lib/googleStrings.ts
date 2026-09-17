import i18n from "../i18n";

/* Copy for signing in with Google: the two auth screens, and the proof of
   ownership the account screen now accepts in two forms.

   REGISTERED AT RUNTIME, like parityStrings.ts and paymentStrings.ts and for
   the same reason: src/strings.ts is 60 KB and a twenty key change lands in
   it invisibly. The consequence is the thing to remember: every screen that
   uses a key below must import this module FOR ITS SIDE EFFECT, or it renders
   the raw key at the reader. Three screens do, and all three of them are in
   this change: LoginScreen, RegisterScreen and AccountScreen.

   TWO GROUPS, BOTH OF THEM SOMEBODY ELSE'S. `auth` and `acct` are both
   strings.ts's, so this bundle adds keys to each rather than owning a
   namespace of its own. addResourceBundle is called deep and overwrite, and
   i18n.ts folds strings.ts in at init before any screen can import this file,
   so there is no ordering trap of the kind web/src/main.tsx has to keep: on
   this client both groups exist before this module can run. A namespace of
   its own would have put a role label somewhere nobody would look for one.

   THE SENTENCES ARE WEB'S, WORD FOR WORD, from web/src/lib/googleStrings.ts,
   because divergence between two clients' wording for one act is itself a
   defect: the same row on the same account has to read the same whether
   somebody opened it in a browser or on a phone. Two keys are NOT web's, and
   both are marked below.

   WHAT IS DELIBERATELY NOT HERE. The words on the Google button itself.
   Google draws that control on both platforms, from the native SDK, and
   localises its own label, which is why components/GoogleSignInButton.tsx
   owns no text at all. Note the one thing the phone loses by that: the native
   button takes its language from the DEVICE, not from the in app language
   switch, so a French UI on an English handset draws an English Google
   button. Google's own branding terms are about their button specifically and
   a hand drawn lookalike is the worse trade.

   French first, like the other bundles: three of the five launch markets are
   francophone. */

const fr = {
  auth: {
    googleOr: "ou",
    /* NOT WEB'S SENTENCE. Web's googleScriptFailed is about a script that did
       not load, which is not a thing that can happen on a phone: the code is
       in the bundle. What can happen here is an Android handset with no
       usable Google Play services, or a native call that fails for a reason
       the SDK will not name. The next step is the same either way and it is
       the form underneath. */
    googleUnavailable:
      "La connexion avec Google n'est pas possible sur cet appareil. Connectez-vous avec votre adresse e-mail et votre mot de passe.",
    /* Shown only after a refused sign in, and only beside the password field.
       The server answers the same vague refusal for a wrong password and for
       an account created through Google, on purpose: a distinct code would
       tell anybody holding a list of addresses which of them are registered
       here. So the client cannot know which of the two it was either, and
       this sentence does not pretend to. */
    googleWrongPassword:
      "Si vous avez créé ce compte avec Google, il n'a pas de mot de passe. Utilisez le bouton Google au-dessus.",
    googleAskTitle: "Encore deux questions",
    googleAskIntro:
      "Google nous dit qui vous êtes. Il ne peut pas nous dire dans quel pays vous travaillez, ni si vous venez ici pour vendre ou pour acheter. Répondez, et nous créons votre compte.",
    googleAskSubmit: "Créer mon compte",
    googleAskCancel: "Annuler",
    /* On the register screen only. The button sits under the form because the
       two answers it sends are collected IN that form, so a person who
       reaches for Google first would be signed up as whatever the defaults
       happen to say. Saying so is cheaper than moving the fields. */
    googleUsesAbove:
      "Le bouton Google utilise le rôle et le pays choisis ci-dessus. Aucun mot de passe ne vous sera demandé.",
  },

  acct: {
    googleTitle: "Connexion avec Google",
    googleLinkedYes:
      "Ce compte est relié à Google. Vous pouvez vous connecter avec le bouton Google, et confirmer avec Google les changements qui demandent normalement votre mot de passe.",
    googleLinkedNo:
      "Ce compte n'est pas relié à Google. Connectez-vous une fois avec le bouton Google, à cette même adresse, et le lien se fera tout seul.",
    /* Said rather than hidden. No endpoint clears users.google_sub, so a
       "Disconnect" button would be a button that lies. The row is
       informational and says as much. */
    googleNoDisconnect:
      "Il n'y a pas encore de quoi délier ce compte : rien côté serveur n'efface ce lien. Cette ligne est donc informative.",
    proofLabel: "Confirmez que c'est bien vous",
    /* Only offered after Google has been offered first. See ProofField in
       screens/AccountScreen.tsx for why that is the order. */
    proofUsePassword: "Utiliser plutôt mon mot de passe",
    proofUseGoogle: "Confirmer plutôt avec Google",
    proofGoogleReady: "Confirmé avec Google. Enregistrez pour appliquer le changement.",
    proofGoogleRedo: "Recommencer avec Google",
    /* The same two paragraphs acct.emailWhyPassword and acct.phoneWhyPassword
       already say, for an account that may have no password to spend. Two
       variants rather than one vaguer sentence: the takeover argument is the
       reason the price exists, and dropping it to save a key would leave the
       field looking like paperwork. */
    emailWhyProof:
      "Votre adresse e-mail est votre identifiant de connexion. La modifier demande une preuve que c'est bien vous : votre mot de passe actuel, ou une confirmation avec Google. Un appareil resté ouvert ne doit pas suffire à faire basculer un compte vers une autre adresse.",
    phoneWhyProof:
      "Votre numéro sert à vos versements Mobile Money. Il est facultatif et ne sert pas à vous connecter. Le modifier demande une preuve que c'est bien vous : votre mot de passe actuel, ou une confirmation avec Google. Un appareil resté ouvert ne doit pas suffire à rediriger l'argent de quelqu'un.",
    /* Conditional on purpose. The server tells us the account is linked to
       Google; it does not tell us whether the account also has a usable
       password, and no field on /auth/me could without saying more about the
       credentials than a settings screen needs. So this says "si". */
    passwordMaybeFirst:
      "Si ce compte a été créé avec Google, il n'a pas encore de mot de passe. En définir un ici ajoute une deuxième façon d'entrer ; le bouton Google continue de fonctionner.",
  },
};

const en = {
  auth: {
    googleOr: "or",
    googleUnavailable:
      "Signing in with Google is not possible on this device. Sign in with your email address and password.",
    googleWrongPassword:
      "If you created this account with Google, it has no password. Use the Google button above.",
    googleAskTitle: "Two more questions",
    googleAskIntro:
      "Google tells us who you are. It cannot tell us which country you work in, or whether you came here to sell or to buy. Answer those, and we create your account.",
    googleAskSubmit: "Create my account",
    googleAskCancel: "Cancel",
    googleUsesAbove:
      "The Google button uses the role and the country chosen above. You will not be asked for a password.",
  },

  acct: {
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
      "If this account was created with Google, it has no password yet. Setting one here adds a second way in, and the Google button keeps working.",
  },
};

i18n.addResourceBundle("fr", "translation", fr, true, true);
i18n.addResourceBundle("en", "translation", en, true, true);

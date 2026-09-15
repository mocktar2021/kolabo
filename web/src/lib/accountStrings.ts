/* Account settings and password recovery copy, registered as a resource
   bundle so the 40 KB i18n.ts stays focused on the core app copy — the same
   arrangement the cart, the disputes queue, the admin console and the
   messaging screen already use.

   TWO NAMESPACES IN ONE FILE, and they are two screens: `account` is what a
   signed-in user changes about themselves, `reset` is how a locked-out user
   gets back in. They live together because they turn on one fact — THE EMAIL
   ADDRESS IS THE LOGIN IDENTITY — which is also exactly why the backend keeps
   them in one module (backend/app/modules/auth/account.py) rather than
   splitting settings from recovery and restating the rule in both.

   THE PHONE NUMBER IS STILL HERE AND IS NO LONGER THAT. It is optional, it is
   not collected at signup, and the one thing it is for is a Mobile Money
   payout. The copy below has to keep saying which of the two is which: a
   settings screen that still calls the number an identifiant is how somebody
   ends up changing the wrong field and locking themselves out.

   nav.account is deep-merged into the nav group i18n.ts owns.
   addResourceBundle is called with deep=true and overwrite=true and main.tsx
   imports this file after "./i18n", so the key joins the existing menu rather
   than replacing it. One key is not a group, and giving the account link its
   own namespace would put it somewhere nobody would look for a nav label. */
import i18n from "../i18n";

const fr = {
  title: "Mon compte",
  sub: "L'adresse avec laquelle vous vous connectez, votre mot de passe, et ce que la plateforme vous envoie.",

  tabDetails: "Détails",
  tabPayment: "Paiement",
  tabNotifications: "Notifications",
  tabAccount: "Compte",

  emailTitle: "Adresse e-mail",
  /* Said before the form, not after the refusal: somebody who does not know
     the address is their identifiant reads the password field as de la
     paperasse. */
  emailWhyPassword: "Votre adresse e-mail est votre identifiant de connexion. La modifier demande votre mot de passe actuel : un appareil resté ouvert ne doit pas suffire à faire basculer un compte vers une autre adresse.",
  emailCurrent: "Adresse actuelle",
  emailNew: "Nouvelle adresse",
  emailSave: "Enregistrer l'adresse",
  emailSaved: "Adresse mise à jour. C'est désormais celle de votre connexion.",

  phoneTitle: "Numéro de téléphone",
  /* The number is optional and it is not the login. Saying what it IS for is
     what stops somebody adding one because they think they have to. */
  phoneWhyPassword: "Votre numéro sert à vos versements Mobile Money. Il est facultatif et ne sert pas à vous connecter. Le modifier demande votre mot de passe actuel : un appareil resté ouvert ne doit pas suffire à rediriger l'argent de quelqu'un.",
  phoneCurrent: "Numéro actuel",
  phoneNone: "Aucun numéro enregistré",
  phoneNew: "Nouveau numéro",
  phoneSave: "Enregistrer le numéro",
  phoneSaved: "Numéro mis à jour. C'est celui que nous utiliserons pour vos versements.",

  passwordTitle: "Mot de passe",
  passwordCurrent: "Mot de passe actuel",
  passwordNew: "Nouveau mot de passe",
  passwordConfirm: "Confirmer le nouveau mot de passe",
  passwordSave: "Changer le mot de passe",
  passwordSaved: "Mot de passe mis à jour.",
  passwordTooShort: "{{n}} caractères minimum.",
  passwordMismatch: "Les deux mots de passe ne sont pas identiques.",

  paymentTitle: "Comment vous êtes payé",
  paymentBody: "Les paiements passent par Mobile Money. L'argent d'une commande est bloqué en séquestre à la commande, puis libéré vers vous à la livraison. C'est ce séquestre qui vous protège d'un client qui disparaît, et le client d'une livraison qui n'arrive pas.",
  /* Why there is no form here. Nothing in this system stores an instrument de
     paiement, aucun endpoint n'en accepte, et un formulaire qui collecte des
     coordonnées que personne ne lit est pire que la phrase honnête : il
     promet un versement automatique qui n'existe pas encore. */
  paymentPending: "Les coordonnées de versement (opérateur et numéro de retrait) arriveront avec l'intégration du prestataire de paiement. Tant qu'aucun versement ne part d'ici, il n'y a rien à saisir sur cette page.",
  paymentMeanwhile: "D'ici là, les versements sont déclenchés manuellement vers le numéro de votre compte.",

  notifTitle: "Ce que nous vous envoyons",
  notifIntro: "Les événements qui déclenchent une notification aujourd'hui :",
  notifInvitation: "Une marque vous invite sur un brief, ou retire son invitation.",
  notifProposal: "Une proposition est envoyée, reçoit une réponse, ou est retirée.",
  notifContract: "Un contrat est généré, signé par l'autre partie, ou annulé.",
  notifPayment: "Un paiement est bloqué en séquestre, libéré, ou remboursé.",
  notifDispute: "Un litige est ouvert, reçoit une réponse, ou est tranché.",
  notifMessage: "Un message vous est adressé.",
  notifSecurity: "Votre mot de passe change, y compris quand ce n'est pas vous qui l'avez changé.",
  /* Read-only on purpose. Il n'existe pas de préférences de notification
     côté serveur : des interrupteurs qui ne coupent rien seraient un mensonge
     avec une jolie animation, et la première notification reçue après les
     avoir coupés est celle qui fait désinstaller. */
  notifReadOnly: "Cette liste est en lecture seule. Il n'existe pas encore de préférences côté serveur, et des interrupteurs qui ne couperaient rien vaudraient moins que cette phrase.",

  sessionTitle: "Session",
  sessionDesc: "Vous déconnecter n'efface rien : vos contrats, vos messages et vos paiements vous attendent à la prochaine connexion.",
  signOut: "Se déconnecter",

  loadFailed: "Impossible de charger votre compte pour l'instant."
};

const en = {
  title: "My account",
  sub: "The address you sign in with, your password, and what the platform sends you.",

  tabDetails: "Details",
  tabPayment: "Payment",
  tabNotifications: "Notifications",
  tabAccount: "Account",

  emailTitle: "Email address",
  emailWhyPassword: "Your email address is your sign-in identity. Changing it costs your current password: a device left open must not be enough to move an account onto somebody else's address.",
  emailCurrent: "Current address",
  emailNew: "New address",
  emailSave: "Save the address",
  emailSaved: "Address updated. This is the one you sign in with now.",

  phoneTitle: "Phone number",
  phoneWhyPassword: "Your phone number is where your Mobile Money payouts go. It is optional and it is not how you sign in. Changing it costs your current password: a device left open must not be enough to redirect somebody's money.",
  phoneCurrent: "Current number",
  phoneNone: "No number saved",
  phoneNew: "New number",
  phoneSave: "Save the number",
  phoneSaved: "Number updated. This is the one we will use for your payouts.",

  passwordTitle: "Password",
  passwordCurrent: "Current password",
  passwordNew: "New password",
  passwordConfirm: "Confirm the new password",
  passwordSave: "Change the password",
  passwordSaved: "Password updated.",
  passwordTooShort: "{{n}} characters minimum.",
  passwordMismatch: "The two passwords do not match.",

  paymentTitle: "How you get paid",
  paymentBody: "Payments run on Mobile Money. An order's money is held in escrow when it is placed and released to you on delivery. That escrow is what protects you from a client who disappears, and the client from a delivery that never arrives.",
  paymentPending: "Payout details (operator and withdrawal number) arrive with the payment provider integration. While no payout leaves from here, there is nothing on this page to fill in.",
  paymentMeanwhile: "Until then, payouts are triggered manually to the number on your account.",

  notifTitle: "What we send you",
  notifIntro: "The events that trigger a notification today:",
  notifInvitation: "A brand invites you to a brief, or withdraws its invitation.",
  notifProposal: "A proposal is sent, answered, or withdrawn.",
  notifContract: "A contract is generated, signed by the other party, or cancelled.",
  notifPayment: "A payment is held in escrow, released, or refunded.",
  notifDispute: "A dispute is opened, answered, or decided.",
  notifMessage: "Somebody writes to you.",
  notifSecurity: "Your password changes, including when you are not the one who changed it.",
  notifReadOnly: "This list is read-only. There are no notification preferences server-side yet, and switches that switched nothing would be worth less than this sentence.",

  sessionTitle: "Session",
  sessionDesc: "Signing out erases nothing: your contracts, your messages and your payments are waiting at the next sign-in.",
  signOut: "Sign out",

  loadFailed: "Your account could not be loaded right now."
};

/* Getting back in. Separate from `account` because the reader is in the
   opposite situation: they hold no session at all, which is precisely why
   this flow can never ask them for their current password. */
const resetFr = {
  forgot: "Mot de passe oublié ?",
  title: "Réinitialiser le mot de passe",
  intro: "Nous envoyons un code à six chiffres par e-mail à l'adresse de votre compte.",
  phoneLabel: "Adresse e-mail",
  request: "Envoyer le code",
  /* WORDED FOR AN ANSWER THAT IS DELIBERATELY THE SAME EITHER WAY. The API
     returns an identical 202 for a registered address and for one it has
     never seen, so this sentence must not say "un code a été envoyé" — that
     would turn the screen into the free "is this person on Kolabo ?" lookup
     the endpoint refuses to be. "Si cette adresse est enregistrée" is the
     only honest thing the client knows. */
  sent: "Si cette adresse est enregistrée, un code à six chiffres vient d'y être envoyé par e-mail.",
  sentHint: "Nous ne pouvons pas vous dire si cette adresse a un compte : ce serait un moyen, pour n'importe qui, de savoir qui est sur Kolabo.",
  codeLabel: "Code reçu par e-mail",
  newPassword: "Nouveau mot de passe",
  confirmPassword: "Confirmer le mot de passe",
  confirm: "Réinitialiser le mot de passe",
  back: "Revenir à la connexion",
  changePhone: "Utiliser une autre adresse",
  success: "Mot de passe réinitialisé. Connectez-vous avec le nouveau.",
  tooShort: "{{n}} caractères minimum.",
  mismatch: "Les deux mots de passe ne sont pas identiques."
};

const resetEn = {
  forgot: "Forgot your password?",
  title: "Reset your password",
  intro: "We send a six digit code by email to your account's address.",
  phoneLabel: "Email address",
  request: "Send the code",
  sent: "If that address is registered, a six digit code has just been sent to it by email.",
  sentHint: "We cannot tell you whether that address has an account: it would be a way for anyone to find out who is on Kolabo.",
  codeLabel: "Code received by email",
  newPassword: "New password",
  confirmPassword: "Confirm the password",
  confirm: "Reset the password",
  back: "Back to sign in",
  changePhone: "Use a different address",
  success: "Password reset. Sign in with the new one.",
  tooShort: "{{n}} characters minimum.",
  mismatch: "The two passwords do not match."
};

i18n.addResourceBundle("fr", "translation", { account: fr, reset: resetFr, nav: { account: "Compte" } }, true, true);
i18n.addResourceBundle("en", "translation", { account: en, reset: resetEn, nav: { account: "Account" } }, true, true);

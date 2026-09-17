import {
  GoogleSignin,
  isErrorWithCode,
  isSuccessResponse,
  statusCodes,
} from "@react-native-google-signin/google-signin";
import { api, ApiError, type TokenResponse } from "./api";
import { GOOGLE_IOS_CLIENT_ID, GOOGLE_WEB_CLIENT_ID } from "./config";

/* Signing in with Google, on a phone: the chooser, the ID token, and the one
   endpoint that takes it.

   WHAT THIS IS NOT. It is not the subsystem behind lib/socialPlatforms.ts and
   backend/app/modules/profiles/oauth.py. That one asks a creator for
   permission over their own Facebook Page and stores a token belonging to
   THEM, against an account that is already signed in. This one answers a
   different question entirely: who is at the door. Nothing here is a
   credential of ours, there is no redirect uri, no callback route and no
   client secret, because there is no server side code exchange. Google hands
   the app an ID token, this module hands it to POST /auth/google, and
   backend/app/modules/auth/google.py decides whether to believe it.

   THE MOBILE TWIN OF web/src/lib/googleSignIn.ts, and only in behaviour. The
   web module loads a script, draws a button Google owns and dispatches a
   callback Google fires. None of that exists here: the platform is a native
   SDK, the chooser is a system screen, and the credential is the resolved
   value of a promise. What IS the same, deliberately, is every decision, so
   the two clients cannot drift: unset means absent, one endpoint does both
   sign in and sign up, the second leg sends the SAME token, and a refused
   password only ever produces a hint.

   WHICH LIBRARY, AND WHY THIS ONE. Expo's current Google authentication
   guide lists two, react-native-nitro-google-signin and
   @react-native-google-signin/google-signin, and says of both that they
   "can't be used in Expo Go because they require custom native code". This
   one is chosen because it publishes a supported range that this app sits
   inside (Expo 52.0.40 to 57, React Native 0.76.0 to 0.87; this app is Expo
   SDK 54 on React Native 0.81.5), it has no runtime dependencies of its own,
   and its free tier returns exactly the one thing the backend wants, an ID
   token. The alternative additionally pulls in react-native-nitro-modules and
   documents no supported Expo range at all.

   THIS MEANS A DEVELOPMENT BUILD. Neither library runs in Expo Go, so from
   the first build that contains this module the phone in somebody's hand has
   to be an eas build (or a local prebuild), not the Expo Go app. Nothing else
   in this repo changes: the JS still reloads over the dev server.

   UNSET MEANS ABSENT, NOT BROKEN, and it is the rule the whole file is built
   around. Nothing below is called, and no native code is touched, until
   googleConfigured() answers true. A build with no client ids behaves exactly
   as this app behaved before the button existed. See lib/config.ts for where
   the ids come from and what each one is. */

/* Whether a credential can be obtained at all. Asked before anything is
   drawn, everywhere. The WEB id alone decides it: it is what makes Google
   issue an ID token, and without one a sign in would succeed and hand back
   idToken null, which is a worse failure than no button because it looks like
   the app broke. The iOS id is not part of the test because a build that has
   the web id and not the iOS one still works on Android, which is the
   platform this pilot ships on first. */
export function googleConfigured(): boolean {
  return GOOGLE_WEB_CLIENT_ID !== "";
}

/* configure() is global to the native module and idempotent, so it is called
   once and then never thought about again. It is NOT called at import time:
   this module is imported by two auth screens and the account screen, and
   touching a native module during the first render pass of an app that may
   have no Google configuration at all is how an unrelated screen acquires a
   crash. */
let configured = false;

function ensureConfigured(): void {
  if (configured) return;
  GoogleSignin.configure({
    /* THE SERVER CLIENT ID, under a name that does not say so. This is the
       WEB client, not a mobile one, and it is what makes Google put an ID
       token on the response and address it to us. Google's own backend
       verification guidance is to check `aud` against this same web client
       id, which is exactly what backend/app/modules/auth/google.py does with
       GOOGLE_CLIENT_IDS. */
    webClientId: GOOGLE_WEB_CLIENT_ID,
    /* iOS only, and undefined rather than empty string when it is unset: the
       library reads this key to decide whether an explicit id was given, and
       an empty string is a given id that no client matches. */
    iosClientId: GOOGLE_IOS_CLIENT_ID || undefined,
    /* NOT ASKED FOR. offlineAccess makes Google return a serverAuthCode so a
       server can mint refresh tokens and act for the user later. Nothing in
       this platform does that, /auth/google reads an ID token and nothing
       else, and a refresh token we have nowhere to put is a credential we
       would be holding for no reason. */
    offlineAccess: false,
  });
  configured = true;
}

/* What one trip through the chooser can produce. A union rather than a
   throw, because exactly one of these three is an error and the other two are
   ordinary things people do, and a caller that has to read an exception to
   tell them apart gets it wrong once and then shows a red banner to somebody
   who simply changed their mind. */
export type GoogleCredentialResult =
  | { status: "ok"; credential: string }
  | { status: "cancelled" }
  | { status: "unavailable" };

/* Open the chooser and come back with an ID token.

   THE LOCAL GOOGLE SESSION IS DROPPED FIRST, on purpose. The library keeps
   one, and with it signIn() can hand back the last account without showing
   anybody anything. That is wrong twice over here: somebody with two Google
   accounts could never reach the second one, and on the account screen the
   "start again with Google" control would silently return the same token it
   just returned. Signing out first costs one native call and makes the
   chooser mean what it looks like it means. It drops the LIBRARY's session
   only; this app has never had a Google session of its own, and the ID token
   below is handed straight to the API and stored nowhere.

   PLAY SERVICES IS CHECKED BEFORE THE CHOOSER, not after a failure. On
   Android without it there is no Google sign in at all, and the honest place
   to say so is before a screen is opened. It always resolves true on iOS.

   A NULL idToken IS TREATED AS UNAVAILABLE RATHER THAN AS SUCCESS. It is
   what a configure() without a web client id produces, which googleConfigured
   already prevents, so reaching it means the build is configured in a way
   this module did not anticipate. Posting null to /auth/google would come
   back 401 and read to the user as though Google refused them. */
export async function getGoogleCredential(): Promise<GoogleCredentialResult> {
  if (!googleConfigured()) return { status: "unavailable" };
  try {
    ensureConfigured();
    await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
    try {
      await GoogleSignin.signOut();
    } catch {
      /* Nothing was signed in, or the native side declined to say. Either way
         the chooser below is what matters and it is about to run. */
    }
    const response = await GoogleSignin.signIn();
    if (!isSuccessResponse(response)) return { status: "cancelled" };
    const credential = response.data.idToken;
    if (!credential) return { status: "unavailable" };
    return { status: "ok", credential };
  } catch (err) {
    /* A second tap while the first chooser is still open is not a failure and
       must not draw an error: the screen the person is looking at is the one
       they asked for. Every other code means the same thing to this function
       and to the reader, which is that Google is not going to work on this
       handset right now. */
    if (isErrorWithCode(err) && err.code === statusCodes.IN_PROGRESS) {
      return { status: "cancelled" };
    }
    return { status: "unavailable" };
  }
}

/* What the two questions are worth once they have been asked. Both are
   optional on the request for the reason the backend schema gives: the call is
   made twice, and the second call carries the same token plus the answers. */
export type GoogleProfileAnswers = {
  role: string;
  country_code: string;
};

/* POST /auth/google, in one place so the three screens that call it cannot
   drift on the field names. The backend takes `id_token`, not `credential`,
   and the difference has no type checker behind it. */
export function signInWithGoogle(
  credential: string,
  answers?: GoogleProfileAnswers,
  referralCode?: string | null
): Promise<TokenResponse> {
  return api<TokenResponse>("/auth/google", {
    method: "POST",
    body: {
      id_token: credential,
      ...(answers ? { role: answers.role, country_code: answers.country_code } : {}),
      ...(referralCode ? { referral_code: referralCode } : {}),
    },
  });
}

/* NOT AN ERROR, the first leg of a two step flow: a Google address with no
   Kolabo account behind it, and a server that cannot invent a country or a
   role. The caller asks both questions and calls again with the SAME token.
   Named here so no screen has to spell the code out and get it slightly
   wrong. */
export function needsProfileAnswers(err: unknown): boolean {
  return err instanceof ApiError && err.code === "auth_google_profile_required";
}

/* A password that did not work, which for a Google created account is what
   ALWAYS happens: its stored hash is of a secret nobody has ever seen, so
   login() refuses it exactly as it refuses a wrong one. The backend answers
   the same vague auth_bad_credentials either way on purpose, because a code
   that said "this address signs in with Google" would tell anyone holding a
   list of addresses which of them are registered here. The client cannot tell
   the two apart either, so it does not try: it points at the button, beside
   the field, and only after an attempt has failed. */
export function looksLikeWrongPassword(err: unknown): boolean {
  return err instanceof ApiError && err.code === "auth_bad_credentials";
}

/* PROOF THAT THE CALLER OWNS THIS ACCOUNT, in whichever of the two forms it
   has. The backend calls this re-authentication and states the rule once, in
   auth.account.require_reauth: a current password, or a freshly verified
   Google ID token for this account's own address, and EXACTLY ONE of the two.
   A bearer token is not enough on its own, because it says a session exists
   and cannot tell an owner from whoever picked the handset up. */
export type Proof = { kind: "password"; secret: string } | { kind: "google"; secret: string };

/* THE TWO ENDPOINTS SPELL THE PASSWORD FIELD DIFFERENTLY, and nothing in the
   type system says so. PATCH /auth/me takes `current_password` (AccountPatch)
   and DELETE /auth/me takes `password` (DeleteAccountRequest). Sending the
   wrong one is not a 422 either: pydantic drops the unknown key, the request
   arrives carrying no proof at all, and require_reauth answers 403
   auth_reauth_required, which reads like a rejected password. Both spellings
   live here so there is one place to be wrong in, which is the same thing
   web/src/pages/Account.tsx does with the same two helpers. */
export function patchProof(proof: Proof): Record<string, string> {
  return proof.kind === "password"
    ? { current_password: proof.secret }
    : { google_token: proof.secret };
}

export function deleteProof(proof: Proof): Record<string, string> {
  return proof.kind === "password" ? { password: proof.secret } : { google_token: proof.secret };
}

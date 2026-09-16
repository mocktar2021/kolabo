import Constants from "expo-constants";

/* Where the API lives.

   Resolved in priority order so the same build can point anywhere:
     1. EXPO_PUBLIC_API_URL — an env var read at bundle time (expo start /
        eas build), the usual way to switch environments.
     2. expo.extra.apiBaseUrl in app.json — a committed default per build
        profile.
     3. http://localhost:8000 — the docker-compose backend.

   NOTE FOR DEVICE TESTING: a phone running Expo Go cannot reach "localhost" —
   that resolves to the phone itself, not your laptop. Set EXPO_PUBLIC_API_URL
   to your machine's LAN address (e.g. http://192.168.1.20:8000) or a tunnel
   URL before `npx expo start`. The web app has the same rule via VITE_API_URL. */
const extra = (Constants.expoConfig?.extra ?? {}) as {
  apiBaseUrl?: string;
  googleWebClientId?: string;
  googleIosClientId?: string;
};

export const API_BASE: string =
  process.env.EXPO_PUBLIC_API_URL || extra.apiBaseUrl || "http://localhost:8000";

/* The two Google OAuth client ids the sign in button needs, resolved through
   the SAME two steps apiBaseUrl above is resolved through: an EXPO_PUBLIC_
   variable baked in at bundle time, else a committed default in
   expo.extra. They live here rather than in lib/googleSignIn.ts because this
   module is the one place in the app that reads Constants.expoConfig.extra,
   and a second reader would be a second place to look when a value does not
   arrive.

   EMPTY IS A REAL SETTING AND THE RIGHT ONE UNTIL THE CLIENTS EXIST. With no
   web client id there is no audience Google could stamp into a token, so a
   button would open a chooser and then be refused by the server with
   auth_google_unavailable: a control that exists only to fail. Empty means the
   button is ABSENT instead, which is the rule this platform already applies to
   the YouTube key, the Meta credentials, the Anthropic key and the FedaPay
   keys. lib/googleSignIn.ts googleConfigured() is what every caller asks
   before drawing anything.

   TRIMMED, because an operator who leaves a stray space around a value means
   the same thing as one who does not, and a client id with a space in it is
   one no token can ever be addressed to. The backend trims its comma
   separated list the same way.

   WHICH ID IS WHICH, because the names are not interchangeable and the
   failure is silent:

     googleWebClientId is the WEB client, and it is what the native library
     takes as `webClientId`, its server client id. It is what makes Google
     issue an ID TOKEN at all (without it the sign in succeeds and idToken
     comes back null), and per Google's own backend verification guidance it
     is the id the token's `aud` is checked against. It is the SAME value the
     browser build already uses as VITE_GOOGLE_CLIENT_ID, and the same one
     that has to appear in the backend's GOOGLE_CLIENT_IDS.

     googleIosClientId is the IOS client, and it is needed only on iOS, where
     the Google SDK identifies the app with it. It is NOT what the token is
     addressed to. Leaving it empty on Android costs nothing.

   THE ANDROID CLIENT HAS NO ID HERE ON PURPOSE. An Android OAuth client is
   matched by the app's package name and the SHA-1 of the certificate it was
   signed with, not by a value in the bundle, so there is nothing to configure
   for it in this file. It still has to EXIST in the Google Cloud project, or
   Android sign in fails with DEVELOPER_ERROR. See mobile/MOBILE_BUILD.md. */
export const GOOGLE_WEB_CLIENT_ID: string = (
  process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ||
  extra.googleWebClientId ||
  ""
).trim();

export const GOOGLE_IOS_CLIENT_ID: string = (
  process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID ||
  extra.googleIosClientId ||
  ""
).trim();

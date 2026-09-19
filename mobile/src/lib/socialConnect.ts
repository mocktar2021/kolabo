/* The two pure pieces of the mobile OAuth connect flow: where the system
   browser is told to come back to, and what the URL it comes back with
   actually says.

   PURE, AND IN lib/ RATHER THAN IN THE COMPONENT, for one reason: this is the
   half that is easy to get quietly wrong and impossible to notice going
   wrong. A misparsed callback does not throw. It reads as "the connect button
   did nothing", on a handset, after a consent screen, which is the least
   debuggable place in the product. Here it is a string in and an object out,
   so tests/socialConnect.test.ts can hold every shape the backend can send
   without a browser, a phone or an approved Meta app.

   NOTHING HERE IMPORTS FROM react-native, deliberately. vitest runs in a node
   environment (see vitest.config.ts) and an RN import in this file would make
   the test suite need a renderer to check a query string. */

/* expo.scheme in mobile/app.json, and the second half of the backend
   allowlist. oauth_service.MOBILE_REDIRECT_SCHEME is the literal "kolabo://"
   and redirect_allowed accepts any target beginning with it.

   THE TWO ARE MATCHED BY HAND, across a JSON file, a Python constant and this
   line, and nothing checks them against each other. Renaming any one of the
   three produces no error anywhere: start_authorization quietly drops the
   redirect_to, logs a WARNING line nobody is watching, and the creator
   finishes a real consent screen only to land on the callback's raw JSON in a
   browser tab that never closes. */
const SCHEME = "kolabo://";

/* Where the consent flow ends up, and what openAuthSessionAsync watches for.

   THE LITERAL SCHEME, NOT Linking.createURL(). createURL is the usual way to
   build this and it is the wrong tool here, because under Expo Go it yields
   an exp://127.0.0.1:8081/... URL. That fails redirect_allowed, and a refused
   redirect_to is discarded rather than refused, so the failure has no symptom
   until a creator is stranded on a JSON page.

   THE CONSEQUENCE IS A DEVELOPMENT BUILD. A custom scheme is only registered
   with the operating system by a build that declares it, so this flow does
   not work inside Expo Go at all. That is the same constraint
   lib/googleSignIn.ts already carries and for the same underlying reason, so
   it asks nothing new of the pilot.

   The platform rides in the path rather than only in the query string so that
   a URL sitting in a log or a debugger says which handshake it belongs to
   even when the query says social_error and names no platform. */
export function oauthReturnUrl(platform: string): string {
  return `${SCHEME}oauth/${platform}`;
}

/* What the backend put on the query string of the URL it sent us back to.

   Exactly one of these is ever set. oauth_service._client_redirect appends a
   single pair, "connected=<platform>" on success or "social_error=<code>" on
   failure, so a result with both, or with neither, is a URL this app did not
   cause and the caller should treat as nothing having happened. */
export type SocialCallback = {
  connected: string | null;
  socialError: string | null;
};

export function readCallbackParams(url: string): SocialCallback {
  return {
    connected: queryValue(url, "connected"),
    socialError: queryValue(url, "social_error"),
  };
}

/* One query parameter, decoded, or null.

   HAND ROLLED RATHER THAN new URL(url).searchParams, and that is not
   preference. React Native ships an incomplete URL polyfill: it does not
   implement searchParams at all on Android, and what it does implement is
   written around http and https rather than around a custom scheme. A parser
   that works in node and fails on a handset is worse than no parser, because
   the test suite would be green the whole time.

   THE LAST OCCURRENCE WINS. _client_redirect appends its marker to whatever
   query string redirect_to already carried, so the backend's value is by
   construction the last one. Our own return URL carries no query string, so
   in practice there is never more than one; reading the last is simply the
   rule that stays correct if that ever stops being true.

   AN EMPTY VALUE READS AS ABSENT. "connected=" names no platform and
   "social_error=" names no code, and treating either as present would hand
   the caller an empty string to render or to look up. */
function queryValue(url: string, name: string): string | null {
  const start = url.indexOf("?");
  if (start === -1) return null;
  /* The fragment is not part of the query and may itself contain an
     ampersand, so it is cut off before anything is split. */
  const hash = url.indexOf("#", start);
  const query = hash === -1 ? url.slice(start + 1) : url.slice(start + 1, hash);

  let found: string | null = null;
  for (const pair of query.split("&")) {
    if (pair === "") continue;
    const eq = pair.indexOf("=");
    /* The WHOLE key is compared, decoded, so "not_connected" and
       "social_errors" are different parameters and not near misses. */
    const key = decodePart(eq === -1 ? pair : pair.slice(0, eq));
    if (key !== name) continue;
    const value = eq === -1 ? "" : decodePart(pair.slice(eq + 1));
    found = value === "" ? null : value;
  }
  return found;
}

/* decodeURIComponent throws a URIError on a stray percent sign, and a
   creator's connection must not die on one. "+" is a space because that is
   what urlencode() in the backend writes for one. */
function decodePart(raw: string): string {
  const plussed = raw.replace(/\+/g, " ");
  try {
    return decodeURIComponent(plussed);
  } catch {
    return plussed;
  }
}

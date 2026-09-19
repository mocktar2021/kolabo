/* Reading the marker the OAuth callback sends a creator back with: the mobile
   twin of web/src/lib/socialConnect.ts.

   SAME RETURN SHAPE AND SAME DECISIONS, DIFFERENT PARSER, which is the split
   urls.ts already lives with in this folder. React Native's global URL is a
   stub, so there is no URLSearchParams to lean on and the query is taken
   apart by hand. Two implementations of one contract need two tests, and
   tests/socialConnect.test.ts deliberately asserts the same cases the web
   suite does: if an answer stops matching, the two apps have started reading
   the same callback differently, and that is the bug.

   WHAT IT IS GIVEN IS A WHOLE URL, not a query string, because that is what
   WebBrowser.openAuthSessionAsync hands back on success. Web is given
   window.location.search for the same reason: each takes what its own
   platform actually produces.

   The marker names come from backend/app/modules/profiles/oauth_service.py:
   success_redirect appends `connected=<platform>`, failure_redirect appends
   `social_error=<code>`. Every code it can carry already has a French and an
   English sentence in lib/errorMessages.ts, so no failure copy is written
   here. */

export const CONNECTED_PARAM = "connected";
export const ERROR_PARAM = "social_error";

export type ConnectResult =
  | { kind: "connected"; platform: string }
  | { kind: "failed"; code: string };

/* Lower-case letters, digits and underscores: a platform id and an AppError
   code, and nothing else. See the web twin for the whole argument. */
const SAFE = /^[a-z0-9_]+$/;

/* The query of a url, with any fragment taken off first.

   THE FRAGMENT IS CUT BEFORE THE QUESTION MARK IS LOOKED FOR, because a "?"
   can legally appear inside a fragment and everything after a "#" is not
   query at all. A url with no "?" has no query, which is the honest reading:
   this is handed whole urls, so treating a bare path as though it were a
   query string would find parameters in a path segment. */
function queryOf(url: string): string {
  const hash = url.indexOf("#");
  const withoutFragment = hash === -1 ? url : url.slice(0, hash);
  const question = withoutFragment.indexOf("?");
  return question === -1 ? "" : withoutFragment.slice(question + 1);
}

/* One parameter out of a raw query string, decoded, or null.

   The "+" replacement is the half of form encoding that decodeURIComponent
   does not do: it understands %20 and knows nothing about "+", so a value
   that travelled as a form-encoded space would otherwise keep the plus. The
   backend builds these with urlencode, which spells a space "+".

   A MALFORMED PERCENT ESCAPE ANSWERS null RATHER THAN THROWING.
   decodeURIComponent raises URIError on something like "%zz", and that string
   arrives from outside the app, so a throw here would turn a nonsense query
   into a crash on the profile screen. */
function valueOf(query: string, name: string): string | null {
  for (const pair of query.split("&")) {
    if (!pair) continue;
    const equals = pair.indexOf("=");
    const key = equals === -1 ? pair : pair.slice(0, equals);
    const raw = equals === -1 ? "" : pair.slice(equals + 1);
    try {
      if (decodeURIComponent(key.replace(/\+/g, " ")) !== name) continue;
      return decodeURIComponent(raw.replace(/\+/g, " "));
    } catch {
      return null;
    }
  }
  return null;
}

/* What the callback said, or null when the url carries no marker at all.

   Success is read first, for the reason the web twin gives: the backend
   appends exactly one marker, so two at once is somebody's paste, and a
   creator whose account really did connect should not be told it failed. */
export function readConnectResult(url: string): ConnectResult | null {
  const query = queryOf(url);

  const platform = valueOf(query, CONNECTED_PARAM);
  if (platform && SAFE.test(platform)) return { kind: "connected", platform };

  const code = valueOf(query, ERROR_PARAM);
  if (code && SAFE.test(code)) return { kind: "failed", code };

  return null;
}

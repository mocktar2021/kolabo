/* Reading the marker the OAuth callback sends a creator back with.

   PURE, AND IN A LIB FILE, because the alternative is a component test that
   needs a DOM in order to assert a string split. ProfileSetup.tsx reads
   window.location.search and hands the string to these two functions;
   everything that can be got wrong about it lives here, where a unit test can
   call it directly.

   THE TWO MARKERS ARE THE BACKEND'S, and the names are read off
   backend/app/modules/profiles/oauth_service.py rather than guessed:
   success_redirect appends `connected=<platform>` and failure_redirect
   appends `social_error=<code>`. The error code is one the API already had
   (oauth_exchange_failed, oauth_state_expired, oauth_state_invalid), so
   lib/errorMessages.ts already carries a French and an English sentence for
   each and this feature invents no failure copy at all.

   The mobile twin is mobile/src/lib/socialConnect.ts. It returns the same
   shape and makes the same decisions; it parses by hand because React
   Native's global URL is a stub, the same split urls.ts already lives with. */

export const CONNECTED_PARAM = "connected";
export const ERROR_PARAM = "social_error";

export type ConnectResult =
  | { kind: "connected"; platform: string }
  | { kind: "failed"; code: string };

/* Both values are narrowed to the shape the backend can actually produce:
   lower-case letters, digits and underscores, which is what a platform id and
   an AppError code are.

   It matters because this arrives from a query string, and a query string is
   whatever the person in front of the browser last typed into it. The code is
   handed to errorText, which looks up `apiError.<code>` and falls back to a
   generic sentence on a miss, so an invented value could never put text of
   somebody's choosing on the screen even without this guard. Narrowing here
   means the component never has to know that. */
const SAFE = /^[a-z0-9_]+$/;

function paramsOf(search: string): URLSearchParams {
  return new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
}

/* What the callback said, or null when this is an ordinary visit to the page.

   SUCCESS IS READ FIRST, so a URL carrying both markers counts as a success.
   Nothing the backend does produces both — the callback appends exactly one —
   so the only way to see them together is somebody pasting one onto the other,
   and a creator whose account really did connect should not be told it failed. */
export function readConnectResult(search: string): ConnectResult | null {
  const params = paramsOf(search);

  const platform = params.get(CONNECTED_PARAM);
  if (platform && SAFE.test(platform)) return { kind: "connected", platform };

  const code = params.get(ERROR_PARAM);
  if (code && SAFE.test(code)) return { kind: "failed", code };

  return null;
}

/* The same query string with both markers removed, for history.replaceState.

   RETURNED RATHER THAN APPLIED, so this file stays pure and testable and the
   one call to replaceState sits in the component beside the rest of its
   browser work.

   IT REMOVES A MARKER readConnectResult REFUSED TO READ, deliberately: a
   malformed `connected` value still has no business surviving a refresh, and
   leaving it behind would mean a creator reloading the page carried a stale
   marker forever. Anything else on the query string is kept exactly as it
   was, because it is not ours. */
export function stripConnectMarkers(search: string): string {
  const params = paramsOf(search);
  params.delete(CONNECTED_PARAM);
  params.delete(ERROR_PARAM);
  const rest = params.toString();
  return rest ? `?${rest}` : "";
}

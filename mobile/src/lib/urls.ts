/* Is this a link the phone should be told to open? The twin of
   web/src/lib/urls.ts, and deliberately the same rules in the same order.

   WHY A CLIENT SIDE GUARD AT ALL. A deliverable's link_url is typed by one
   person and handed to Linking.openURL in front of another. openURL hands the
   string to the operating system, which resolves it against every scheme any
   installed app has registered, so an unchecked value is not merely a bad web
   page: it is whatever "tel:", "intent:" or a rival app's private scheme does
   on that handset, launched by a tap on a screen where a brand releases
   money.

   WHY IT IS NOT ENOUGH THAT THE SERVER NOW CHECKS. Validation on submission
   only covers rows written after it ships. link_url was accepted unvalidated
   from the day deliverables landed until this change, so every row already in
   the database went in unchecked, and this panel renders those rows tomorrow
   exactly as it renders new ones. A server side rule cannot reach backwards.

   WHY THIS ONE IS HAND ROLLED AND WEB USES new URL. React Native's global URL
   is a stub, not the WHATWG parser: its constructor accepts anything without
   throwing, and its .protocol getter throws "not implemented" outright. Under
   vitest this file runs on Node, where URL is real and complete, so a version
   built on new URL would pass every test here and then reject every link on a
   real handset (or crash on the first one). A test that is green precisely
   where the code is broken is worse than no test, so the rules below are
   spelled out instead of delegated.

   HOW FAR THE TWO CAN DIVERGE. On every input either app will really see, the
   two agree, and that includes every case in both test files. They part only
   on malformed input the WHATWG parser silently repairs and this one refuses,
   such as "https:/one-slash.com" with its single slash, or a bracketed IPv6
   literal. Mobile is the stricter of the two there, which is the safe
   direction: the worst case is a real link shown as plain text with the hint
   beside it, never an unsafe one opened.

   WHAT IS HANDED BACK is the submitted string (with https:// in front if it
   needed one), never a normalised rewrite of it, because the web twin cannot
   normalise either without the two apps disagreeing about what they render. */

const WHITESPACE = /\s/;
const SCHEME = /^[a-zA-Z][a-zA-Z0-9+.-]*:/;
const HTTP_PREFIX = /^https?:\/\//i;
const AUTHORITY_END = /[\/?#]/;

function hasControlOrSpace(value: string): boolean {
  if (WHITESPACE.test(value)) return true;
  for (let i = 0; i < value.length; i += 1) {
    const code = value.charCodeAt(i);
    if (code <= 0x20 || (code >= 0x7f && code <= 0x9f)) return true;
  }
  return false;
}

export function safeExternalHref(raw: string | null | undefined): string | null {
  if (typeof raw !== "string") return null;
  const value = raw.trim();
  if (value === "") return null;
  if (hasControlOrSpace(value)) return null;
  if (value.includes("\\")) return null;
  /* "//evil.com" and "/x" are both repaired into something valid by the
     https:// retry below. Refuse them instead, so what is handed back is
     always recognisably what was written. */
  if (value.startsWith("/")) return null;

  /* A value carrying any scheme is used as it stands, so "javascript:" and
     "data:" fall to the http test below instead of being prefixed into
     something that would pass it. Only a value with no scheme at all is
     retried as https://, which is what a creator pasting "instagram.com/p/abc"
     means and by far the commonest real input. */
  const candidate = SCHEME.test(value) ? value : `https://${value}`;
  if (!HTTP_PREFIX.test(candidate)) return null;

  /* A scheme is not enough: "https://" and "https://:443" carry no host, and
     openURL would be handed something that resolves to nothing. Userinfo is
     dropped before the check so that "https://user@host/x" is judged on
     "host", and the port is dropped so that "host:8080" is judged on "host". */
  const rest = candidate.replace(HTTP_PREFIX, "");
  const authority = rest.split(AUTHORITY_END)[0];
  const at = authority.lastIndexOf("@");
  const hostAndPort = at === -1 ? authority : authority.slice(at + 1);
  const host = hostAndPort.split(":")[0];
  if (host === "") return null;

  return candidate;
}

/* Is this a link the browser should be told to follow?

   WHY A CLIENT-SIDE GUARD AT ALL. A deliverable's link_url is typed by one
   person and rendered to another. Put an unchecked value straight into an
   href and "javascript:..." runs as script in THIS origin, with the reading
   brand's own session: the anchor becomes a one click account takeover,
   offered by us, on the one page a brand has every reason to trust because it
   is where they release money. target="_blank" and rel="noreferrer" do
   nothing about that. They are about the destination page, not about whether
   the destination is a page at all.

   WHY IT IS NOT ENOUGH THAT THE SERVER NOW CHECKS. Validation on submission
   only covers rows written after it ships. link_url was accepted unvalidated
   from the day deliverables landed until this change, so every row already in
   the database went in unchecked, and this component will render those rows
   tomorrow exactly as it renders new ones. A server side rule cannot reach
   backwards. The client has to decide for itself what it is willing to put in
   an href, which is the whole reason this function exists rather than a
   comment saying the API handles it.

   WHAT COUNTS AS SAFE: non blank once trimmed, no whitespace and no control
   character anywhere inside (that is what "java\nscript:" is for), no
   backslash (the character parsers disagree about, and never legitimate in a
   pasted post link), not starting with "/", parses, and lands on exactly
   http: or https:. Everything else returns null and the caller shows the text
   without making it clickable.

   THE ONE REPAIR MADE is a missing scheme. "instagram.com/p/abc" is the
   commonest thing a creator actually pastes and it is not an attack, so it is
   retried once as https://. Note that a value carrying any scheme is never
   retried: new URL only fails on a scheme it can parse when the rest is
   broken, and repairing that would turn a malformed link into a different
   working one.

   WHAT IS HANDED BACK is the submitted string (with https:// in front if it
   needed one), not the parser's normalised form of it. The mobile twin in
   mobile/src/lib/urls.ts cannot use this parser and has to match this
   behaviour exactly, so neither side is allowed to rewrite the value. */

const WHITESPACE = /\s/;
const SCHEME = /^[a-zA-Z][a-zA-Z0-9+.-]*:/;

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

  const candidate = SCHEME.test(value) ? value : `https://${value}`;
  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    return null;
  }
  /* Exactly these two. The protocol comes back lowercased by the parser, so
     "JavaScript:" is caught here and not by a case sensitive comparison
     somebody would eventually write by hand. */
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
  return candidate;
}

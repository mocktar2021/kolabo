import { describe, expect, it } from "vitest";
import { safeExternalHref } from "./urls";

/* The guard on a link one user typed and another user clicks.

   WHY THIS IS TESTED AND NOT JUST REVIEWED. Every case below is a string a
   creator can put in the deliverable link field today, and the difference
   between the safe answer and the dangerous one is one character of a regex.
   The dangerous answer is also the silent one: a javascript: href looks
   exactly like a working link until somebody taps it, and by then it has run
   with the reader's session in the app's own origin.

   The rows already in the database are the reason this lives on the client at
   all. link_url was stored unvalidated from the day deliverables shipped, so
   "the API rejects that now" is a statement about tomorrow's rows only.

   The mobile twin of this file is mobile/tests/urls.test.ts, which asserts the
   same answers against a different implementation. Keep the two in step. */

describe("safeExternalHref refuses what must never reach an href", () => {
  it("refuses javascript:, which would run in the app's own origin", () => {
    expect(safeExternalHref("javascript:alert(1)")).toBeNull();
  });

  it("refuses it however it is capitalised", () => {
    /* The parser lowercases the protocol, so this is caught by the same
       comparison rather than by a second one somebody has to remember. */
    expect(safeExternalHref("JavaScript:alert(1)")).toBeNull();
    expect(safeExternalHref("JAVASCRIPT:alert(1)")).toBeNull();
  });

  it("refuses a scheme split by whitespace", () => {
    /* The oldest trick against a naive startsWith check: browsers strip these
       characters out of the scheme before resolving, so "java\nscript:" is
       javascript: by the time it matters. Whitespace anywhere inside is
       refused outright, which is cheaper than trying to guess where it is
       load bearing. */
    expect(safeExternalHref("java\nscript:alert(1)")).toBeNull();
    expect(safeExternalHref("java\tscript:alert(1)")).toBeNull();
    expect(safeExternalHref("https://exam ple.com/p")).toBeNull();
  });

  it("refuses data:, which can carry a whole page", () => {
    expect(safeExternalHref("data:text/html,x")).toBeNull();
    expect(safeExternalHref("data:text/html;base64,PHNjcmlwdD4=")).toBeNull();
  });

  it("refuses the other schemes a pasted link is never written in", () => {
    expect(safeExternalHref("vbscript:msgbox(1)")).toBeNull();
    expect(safeExternalHref("file:///etc/passwd")).toBeNull();
    expect(safeExternalHref("mailto:someone@example.com")).toBeNull();
  });

  it("refuses a value with nothing in it", () => {
    expect(safeExternalHref(null)).toBeNull();
    expect(safeExternalHref(undefined)).toBeNull();
    expect(safeExternalHref("")).toBeNull();
    expect(safeExternalHref("   ")).toBeNull();
  });

  it("refuses an http url with no host to go to", () => {
    expect(safeExternalHref("https://")).toBeNull();
    expect(safeExternalHref("http://")).toBeNull();
  });

  it("refuses a protocol relative or rooted path", () => {
    /* Both would be turned into something valid by the https:// retry, and a
       value that only becomes a url because we rewrote it is not a value the
       creator can recognise as what they submitted. */
    expect(safeExternalHref("//evil.example.com")).toBeNull();
    expect(safeExternalHref("/p/abc")).toBeNull();
  });
});

describe("safeExternalHref keeps the links creators really submit", () => {
  it("keeps a normal https url exactly as it was written", () => {
    /* Exactly: the value is validated, not normalised. A parser rewrite here
       would put a different string on screen from the one mobile shows. */
    expect(safeExternalHref("https://www.instagram.com/p/abc")).toBe(
      "https://www.instagram.com/p/abc"
    );
    expect(safeExternalHref("https://www.tiktok.com/@name/video/123?is_from=1")).toBe(
      "https://www.tiktok.com/@name/video/123?is_from=1"
    );
  });

  it("keeps plain http, which plenty of small business sites are still on", () => {
    expect(safeExternalHref("http://example.com/post")).toBe("http://example.com/post");
  });

  it("adds the scheme a creator left off", () => {
    /* By far the commonest real input: the address bar hides the scheme, so
       what gets pasted is what was on screen. Refusing this would read as the
       app rejecting a perfectly good link. */
    expect(safeExternalHref("instagram.com/p/abc")).toBe("https://instagram.com/p/abc");
    expect(safeExternalHref("www.facebook.com/kolabo/posts/1")).toBe(
      "https://www.facebook.com/kolabo/posts/1"
    );
  });

  it("trims the whitespace a paste brings with it", () => {
    expect(safeExternalHref("  https://example.com/p  ")).toBe("https://example.com/p");
  });
});

import { describe, expect, it } from "vitest";

import { safeExternalHref } from "../src/lib/urls";

/* The guard on a link one user typed and another user taps.

   WHY IT LIVES UNDER tests/ AND NOT BESIDE THE SOURCE. The include glob in
   vitest.config.ts collects test files under tests/ and nowhere else, so a
   test file under src/ is collected by nothing. It would never run and would
   therefore never fail, which reads in a diff exactly like a test that
   passes. Every mobile test is here for that reason.

   The glob is described in words rather than quoted, and it has to be: the
   star and slash in the middle of it close a block comment, so writing it out
   here ends this one early and hands the rest of the file to the parser as
   code. That is a syntax error, not a stylistic one.

   WHY IT IS TESTED SEPARATELY FROM WEB rather than sharing a file. The two
   packages share no module, and mobile/src/lib/urls.ts is a different
   implementation of the same rules: React Native's global URL is a stub whose
   .protocol getter throws, so mobile cannot use the parser web uses. Two
   implementations of one contract need two tests, and these cases are
   deliberately the same cases web/src/lib/urls.test.ts asserts. If an answer
   below stops matching the answer there, one of the two apps has started
   treating a link differently from the other and that is the bug.

   The rows already in the database are the reason this exists on the client
   at all. link_url was stored unvalidated from the day deliverables shipped,
   so "the API rejects that now" is a statement about tomorrow's rows only. */

describe("safeExternalHref refuses what must never reach openURL", () => {
  it("refuses javascript:", () => {
    expect(safeExternalHref("javascript:alert(1)")).toBeNull();
  });

  it("refuses it however it is capitalised", () => {
    /* Web gets this free from a parser that lowercases the protocol. This
       implementation has to be case insensitive on purpose, so the case is
       worth naming. */
    expect(safeExternalHref("JavaScript:alert(1)")).toBeNull();
    expect(safeExternalHref("JAVASCRIPT:alert(1)")).toBeNull();
  });

  it("refuses a scheme split by whitespace", () => {
    expect(safeExternalHref("java\nscript:alert(1)")).toBeNull();
    expect(safeExternalHref("java\tscript:alert(1)")).toBeNull();
    expect(safeExternalHref("https://exam ple.com/p")).toBeNull();
  });

  it("refuses data:", () => {
    expect(safeExternalHref("data:text/html,x")).toBeNull();
    expect(safeExternalHref("data:text/html;base64,PHNjcmlwdD4=")).toBeNull();
  });

  it("refuses the schemes only the handset would understand", () => {
    /* The mobile specific half of the risk. openURL hands the string to the
       operating system, which resolves it against every scheme an installed
       app has registered, so the set of dangerous values here is larger than
       the browser's and not knowable from this side. Allowing exactly two
       schemes is the only version of this that stays correct on a handset
       nobody has tested. */
    expect(safeExternalHref("tel:+22997000000")).toBeNull();
    expect(safeExternalHref("intent://scan/#Intent;scheme=zxing;end")).toBeNull();
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
    expect(safeExternalHref("https://:443")).toBeNull();
  });

  it("refuses a protocol relative or rooted path", () => {
    expect(safeExternalHref("//evil.example.com")).toBeNull();
    expect(safeExternalHref("/p/abc")).toBeNull();
  });
});

describe("safeExternalHref keeps the links creators really submit", () => {
  it("keeps a normal https url exactly as it was written", () => {
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
    expect(safeExternalHref("instagram.com/p/abc")).toBe("https://instagram.com/p/abc");
    expect(safeExternalHref("www.facebook.com/kolabo/posts/1")).toBe(
      "https://www.facebook.com/kolabo/posts/1"
    );
  });

  it("trims the whitespace a paste brings with it", () => {
    expect(safeExternalHref("  https://example.com/p  ")).toBe("https://example.com/p");
  });

  it("keeps userinfo and a port without being fooled by either", () => {
    /* "https://user@host/x" is judged on host, not on the part before the @,
       which is the trick that makes a link look like it goes somewhere else.
       It is still a real https url, so it is kept as written. */
    expect(safeExternalHref("https://user@host.com/x")).toBe("https://user@host.com/x");
  });
});

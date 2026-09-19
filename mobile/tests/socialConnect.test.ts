/* The callback parser, against every URL the backend can actually send.

   WHY THIS FILE EXISTS. The failure it guards is silent. If readCallbackParams
   stops seeing "connected", nothing throws: the browser closes, the section
   does not reload, and a creator who just granted Facebook permissions is
   looking at an unchanged screen. There is no stack trace, no red banner and
   no log line to find, because from the app's side nothing went wrong. Every
   case below is a URL shape that oauth_service._client_redirect can produce,
   pinned here so that shape is checked by a test run rather than by somebody
   with a handset and an approved Meta app.

   IT HAS TO LIVE UNDER mobile/tests/. The include glob in vitest.config.ts
   collects test files under tests/ and nowhere else, so the same file under
   mobile/src/ would be collected by nothing and would pass by never running,
   which is the note punctuation.test.ts carries for the same reason. */
import { describe, expect, it } from "vitest";

import { oauthReturnUrl, readCallbackParams } from "../src/lib/socialConnect";

const RETURN_URL = "kolabo://oauth/facebook";

describe("the return url", () => {
  it("is the literal scheme and the platform", () => {
    expect(oauthReturnUrl("facebook")).toBe(RETURN_URL);
  });

  it("starts with the prefix the backend allowlist accepts", () => {
    /* oauth_service.MOBILE_REDIRECT_SCHEME. This assertion is the whole
       contract between the two halves: redirect_allowed takes the prefix
       check first, so a return url that fails it is DISCARDED rather than
       refused and the creator finds out by landing on raw JSON. */
    expect(oauthReturnUrl("facebook").startsWith("kolabo://")).toBe(true);
    expect(oauthReturnUrl("tiktok").startsWith("kolabo://")).toBe(true);
  });

  it("is never an exp:// url, which is what Linking.createURL would give", () => {
    expect(oauthReturnUrl("facebook")).not.toContain("exp://");
    expect(oauthReturnUrl("facebook")).not.toContain("127.0.0.1");
  });
});

describe("a callback the backend sent", () => {
  it("reads the success marker", () => {
    expect(readCallbackParams(`${RETURN_URL}?connected=facebook`)).toEqual({
      connected: "facebook",
      socialError: null,
    });
  });

  it("reads a failure code", () => {
    expect(readCallbackParams(`${RETURN_URL}?social_error=oauth_state_expired`)).toEqual({
      connected: null,
      socialError: "oauth_state_expired",
    });
  });

  it("reads each of the three codes the callback can carry", () => {
    for (const code of ["oauth_exchange_failed", "oauth_state_expired", "oauth_state_invalid"]) {
      expect(readCallbackParams(`${RETURN_URL}?social_error=${code}`).socialError).toBe(code);
    }
  });

  it("keeps a query string the destination already carried", () => {
    /* _client_redirect appends with urllib rather than by concatenation
       precisely so this works. Nothing sends a return url with a query today,
       so this pins the behaviour before something does. */
    expect(readCallbackParams(`${RETURN_URL}?from=profile&connected=facebook`)).toEqual({
      connected: "facebook",
      socialError: null,
    });
  });

  it("takes the backend's marker when a key appears twice", () => {
    /* urlencode appends, so the backend's value is the last one. */
    expect(readCallbackParams(`${RETURN_URL}?connected=x&connected=facebook`).connected).toBe(
      "facebook"
    );
  });
});

describe("a callback that says nothing happened", () => {
  it("finds neither marker on the bare return url", () => {
    expect(readCallbackParams(RETURN_URL)).toEqual({ connected: null, socialError: null });
  });

  it("finds neither on a url with an empty query string", () => {
    expect(readCallbackParams(`${RETURN_URL}?`)).toEqual({ connected: null, socialError: null });
  });

  it("treats an empty value as absent", () => {
    /* "connected=" names no platform, and an empty string handed back would
       be rendered or looked up as though it were one. */
    expect(readCallbackParams(`${RETURN_URL}?connected=`).connected).toBeNull();
    expect(readCallbackParams(`${RETURN_URL}?social_error=`).socialError).toBeNull();
  });

  it("treats a bare key with no equals sign as absent", () => {
    expect(readCallbackParams(`${RETURN_URL}?connected`).connected).toBeNull();
  });
});

describe("the parser is not fooled by a near miss", () => {
  it("does not read a key that merely ends with the name", () => {
    expect(readCallbackParams(`${RETURN_URL}?not_connected=facebook`).connected).toBeNull();
  });

  it("does not read a key that merely starts with the name", () => {
    expect(readCallbackParams(`${RETURN_URL}?social_errors=boom`).socialError).toBeNull();
    expect(readCallbackParams(`${RETURN_URL}?connected_at=today`).connected).toBeNull();
  });

  it("does not read the marker out of a fragment", () => {
    /* A fragment is never sent to a server and is not part of the query. It
       is cut off before the split, so an ampersand inside one cannot invent a
       parameter. */
    expect(readCallbackParams(`${RETURN_URL}#connected=facebook`).connected).toBeNull();
    expect(
      readCallbackParams(`${RETURN_URL}?connected=facebook#x=1&social_error=boom`)
    ).toEqual({ connected: "facebook", socialError: null });
  });

  it("does not read a marker out of the path", () => {
    expect(readCallbackParams("kolabo://oauth/connected=facebook").connected).toBeNull();
  });
});

describe("the parser decodes what the backend encoded", () => {
  it("percent-decodes a value", () => {
    expect(readCallbackParams(`${RETURN_URL}?connected=face%62ook`).connected).toBe("facebook");
  });

  it("reads a plus as a space, which is what urlencode writes for one", () => {
    expect(readCallbackParams(`${RETURN_URL}?social_error=two+words`).socialError).toBe(
      "two words"
    );
  });

  it("survives a stray percent sign instead of throwing", () => {
    /* decodeURIComponent raises URIError on this. A creator's connection must
       not end on a malformed byte somebody appended to a URL. */
    expect(() => readCallbackParams(`${RETURN_URL}?connected=100%`)).not.toThrow();
    expect(readCallbackParams(`${RETURN_URL}?connected=100%`).connected).toBe("100%");
  });

  it("percent-decodes the key as well as the value", () => {
    expect(readCallbackParams(`${RETURN_URL}?connect%65d=facebook`).connected).toBe("facebook");
  });
});

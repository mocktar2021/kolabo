import { describe, expect, it } from "vitest";

import { readConnectResult } from "../src/lib/socialConnect";

/* The url WebBrowser.openAuthSessionAsync hands back when the creator returns
   from a consent screen.

   WHY IT LIVES UNDER tests/ AND NOT BESIDE THE SOURCE. The include glob in
   vitest.config.ts collects test files under tests/ and nowhere else, so a
   test file under src/ is collected by nothing. It would never run and would
   therefore never fail, which reads in a diff exactly like a test that
   passes. Every mobile test is here for that reason.

   WHY IT IS TESTED SEPARATELY FROM WEB rather than sharing a file. The two
   packages share no module, and mobile/src/lib/socialConnect.ts is a
   different implementation of the same rules: React Native's global URL is a
   stub, so there is no URLSearchParams here and the query is taken apart by
   hand. The cases below are deliberately the same cases
   web/src/lib/socialConnect.test.ts asserts. If an answer here stops matching
   the answer there, the two apps have started reading the same redirect
   differently, and that is the bug.

   The one difference in the inputs is not a difference in the rule: this side
   is handed a whole url, because that is what openAuthSessionAsync returns,
   and web is handed window.location.search. */

describe("readConnectResult reads what the callback said", () => {
  it("reads a success off a deep link and names the platform", () => {
    expect(readConnectResult("kolabo://profile?connected=facebook")).toEqual({
      kind: "connected",
      platform: "facebook"
    });
  });

  it("reads a failure and carries the code through untouched", () => {
    /* Untouched is the point: the code goes straight to errorText, which
       looks up the sentence errorMessages.ts already holds for it. */
    expect(readConnectResult("kolabo://profile?social_error=oauth_exchange_failed")).toEqual({
      kind: "failed",
      code: "oauth_exchange_failed"
    });
    expect(readConnectResult("kolabo://profile?social_error=oauth_state_expired")).toEqual({
      kind: "failed",
      code: "oauth_state_expired"
    });
    expect(readConnectResult("kolabo://profile?social_error=oauth_state_invalid")).toEqual({
      kind: "failed",
      code: "oauth_state_invalid"
    });
  });

  it("reads the marker whatever the path in front of it looks like", () => {
    /* Linking.createURL spells the same destination differently depending on
       how the app was launched, and none of that changes the answer. */
    expect(readConnectResult("kolabo://?connected=facebook")).toEqual({
      kind: "connected",
      platform: "facebook"
    });
    expect(readConnectResult("kolabo://profile/social-connected?connected=facebook")).toEqual({
      kind: "connected",
      platform: "facebook"
    });
  });

  it("finds the marker among other parameters, in any position", () => {
    expect(readConnectResult("kolabo://profile?ref=email&connected=facebook&x=1")).toEqual({
      kind: "connected",
      platform: "facebook"
    });
  });

  it("answers null for a url carrying no marker", () => {
    expect(readConnectResult("kolabo://profile")).toBeNull();
    expect(readConnectResult("kolabo://profile?")).toBeNull();
    expect(readConnectResult("kolabo://profile?tab=packages")).toBeNull();
    expect(readConnectResult("")).toBeNull();
  });

  it("answers null for a marker with no value", () => {
    expect(readConnectResult("kolabo://profile?connected=")).toBeNull();
    expect(readConnectResult("kolabo://profile?social_error=")).toBeNull();
    expect(readConnectResult("kolabo://profile?connected")).toBeNull();
  });

  it("prefers success when somebody has pasted both markers together", () => {
    expect(
      readConnectResult("kolabo://profile?connected=facebook&social_error=oauth_state_invalid")
    ).toEqual({ kind: "connected", platform: "facebook" });
  });

  it("refuses a value outside the shape the backend can produce", () => {
    expect(readConnectResult("kolabo://profile?connected=<script>")).toBeNull();
    expect(readConnectResult("kolabo://profile?connected=Facebook")).toBeNull();
    expect(readConnectResult("kolabo://profile?social_error=oauth exchange failed")).toBeNull();
    expect(readConnectResult("kolabo://profile?social_error=../../etc/passwd")).toBeNull();
  });

  it("does not read a query out of a fragment", () => {
    /* Everything after a "#" is not query, and a "?" inside one is ordinary
       text. Web gets this free from URLSearchParams; this side has to cut the
       fragment off by hand, so the case is worth naming. */
    expect(readConnectResult("kolabo://profile#?connected=facebook")).toBeNull();
    expect(readConnectResult("kolabo://profile?connected=facebook#x")).toEqual({
      kind: "connected",
      platform: "facebook"
    });
  });

  it("does not throw on a malformed percent escape", () => {
    /* decodeURIComponent raises URIError on "%zz", and this string comes from
       outside the app. A crash on the profile screen is not an acceptable
       answer to a nonsense url. */
    expect(() => readConnectResult("kolabo://profile?connected=%zz")).not.toThrow();
    expect(readConnectResult("kolabo://profile?connected=%zz")).toBeNull();
  });
});

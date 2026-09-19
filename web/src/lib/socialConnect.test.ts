import { describe, expect, it } from "vitest";

import { readConnectResult, stripConnectMarkers } from "./socialConnect";

/* The query string the OAuth callback sends a creator back on.

   TESTED HERE RATHER THAN THROUGH THE COMPONENT because it is a pure string
   decision. Asserting it through SocialSection would need a DOM, a router, a
   mocked fetch and an i18n instance to check that "connected=facebook" is a
   success, which is four pieces of scaffolding standing between the rule and
   the thing that proves it.

   The cases below are deliberately the same cases mobile/tests/
   socialConnect.test.ts asserts. The two clients parse the callback with
   different code — React Native has no URLSearchParams — so if an answer here
   stops matching the answer there, one of the two apps has started reading
   the same redirect differently. */

describe("readConnectResult reads what the callback said", () => {
  it("reads a success and names the platform", () => {
    expect(readConnectResult("?connected=facebook")).toEqual({
      kind: "connected",
      platform: "facebook"
    });
  });

  it("reads a failure and carries the code through untouched", () => {
    /* Untouched is the point: the code goes straight to errorText, which
       looks up the sentence errorMessages.ts already holds for it. */
    expect(readConnectResult("?social_error=oauth_exchange_failed")).toEqual({
      kind: "failed",
      code: "oauth_exchange_failed"
    });
    expect(readConnectResult("?social_error=oauth_state_expired")).toEqual({
      kind: "failed",
      code: "oauth_state_expired"
    });
    expect(readConnectResult("?social_error=oauth_state_invalid")).toEqual({
      kind: "failed",
      code: "oauth_state_invalid"
    });
  });

  it("works with or without the leading question mark", () => {
    expect(readConnectResult("connected=facebook")).toEqual({
      kind: "connected",
      platform: "facebook"
    });
  });

  it("finds the marker among other parameters, in any position", () => {
    expect(readConnectResult("?ref=email&connected=facebook&x=1")).toEqual({
      kind: "connected",
      platform: "facebook"
    });
  });

  it("answers null for an ordinary visit to the page", () => {
    expect(readConnectResult("")).toBeNull();
    expect(readConnectResult("?")).toBeNull();
    expect(readConnectResult("?tab=packages")).toBeNull();
  });

  it("answers null for a marker with no value", () => {
    expect(readConnectResult("?connected=")).toBeNull();
    expect(readConnectResult("?social_error=")).toBeNull();
    expect(readConnectResult("?connected")).toBeNull();
  });

  it("prefers success when somebody has pasted both markers together", () => {
    /* The callback appends exactly one, so both at once is not something the
       backend can produce. An account that really connected must not be
       reported as a failure. */
    expect(readConnectResult("?connected=facebook&social_error=oauth_state_invalid")).toEqual({
      kind: "connected",
      platform: "facebook"
    });
  });

  it("refuses a value outside the shape the backend can produce", () => {
    /* A platform id and an error code are lower-case letters, digits and
       underscores. Anything else was typed into the address bar by hand. */
    expect(readConnectResult("?connected=<script>")).toBeNull();
    expect(readConnectResult("?connected=Facebook")).toBeNull();
    expect(readConnectResult("?social_error=oauth exchange failed")).toBeNull();
    expect(readConnectResult("?social_error=../../etc/passwd")).toBeNull();
  });
});

describe("stripConnectMarkers leaves nothing to replay on a refresh", () => {
  it("removes the success marker", () => {
    expect(stripConnectMarkers("?connected=facebook")).toBe("");
  });

  it("removes the failure marker", () => {
    expect(stripConnectMarkers("?social_error=oauth_state_expired")).toBe("");
  });

  it("keeps every other parameter, because they are not ours", () => {
    expect(stripConnectMarkers("?ref=email&connected=facebook")).toBe("?ref=email");
    expect(stripConnectMarkers("?connected=facebook&tab=packages")).toBe("?tab=packages");
  });

  it("removes a malformed marker readConnectResult refused to read", () => {
    /* Otherwise a creator who reloaded would carry it forever, and the two
       functions would disagree about whether the page is still mid-flow. */
    expect(readConnectResult("?connected=Facebook")).toBeNull();
    expect(stripConnectMarkers("?connected=Facebook")).toBe("");
  });

  it("leaves a query string with no markers in it alone", () => {
    expect(stripConnectMarkers("?tab=packages")).toBe("?tab=packages");
    expect(stripConnectMarkers("")).toBe("");
  });
});

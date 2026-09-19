/* When a creator is asked which Page they sell on, and how the figure beside
   each Page is written.

   WHY THIS FILE EXISTS. Both failures this guards are silent. Ask too little
   and a creator who administers four Facebook Pages is left looking at the
   numeric app-scoped id the token exchange returned, with no follower count
   and nothing on screen to say why, which is the exact defect the picker was
   built for. Ask too much and a creator whose count was filled in at connect
   time is told for ever to choose a Page they have already got a verified
   number for. Neither throws, neither logs, and both reach us as "the app is
   a bit odd", so the rule is pinned here rather than checked by eye.

   IT HAS TO LIVE UNDER mobile/tests/. The include glob in vitest.config.ts
   collects test files under tests/ and nowhere else, so the same file under
   mobile/src/ would be collected by nothing and would pass by never running,
   which is the note punctuation.test.ts and socialConnect.test.ts both carry
   for the same reason. */
import { describe, expect, it } from "vitest";

import { followerText, needsPageChoice } from "../src/lib/socialPages";

/* The live case this feature came from: a creator on Facebook whose four
   Pages left read_audience with nothing it was willing to record. */
const AMBIGUOUS = { platform: "facebook", method: "oauth", follower_count: null };

describe("a connected account with no follower count", () => {
  it("is asked which Page it sells on", () => {
    expect(needsPageChoice(AMBIGUOUS)).toBe(true);
  });

  it("is asked when the field is missing altogether, not merely null", () => {
    /* profileTypes.SocialAccount types follower_count as nullable, but the
       value arrives off a JSON body and an older row can simply not carry
       it. Absent and null are the same fact about the account. */
    expect(needsPageChoice({ platform: "facebook", method: "oauth" })).toBe(true);
  });
});

describe("a connected account the platform already answered for", () => {
  it("is never asked, because exactly one Page means there was nothing to ask", () => {
    expect(needsPageChoice({ ...AMBIGUOUS, follower_count: 1688 })).toBe(false);
  });

  it("is never asked when the count is zero, which is a count and not an absence", () => {
    /* The line this pins: a falsy test here would ask the owner of a Page
       with no followers to choose it again on every visit, for ever. */
    expect(needsPageChoice({ ...AMBIGUOUS, follower_count: 0 })).toBe(false);
  });
});

describe("an account the question cannot be asked about", () => {
  it("is not asked when the handle was typed by hand", () => {
    /* A manual row has no token behind it, so there is no Page list to read
       and the endpoint would answer oauth_token_expired. */
    expect(needsPageChoice({ ...AMBIGUOUS, method: "manual" })).toBe(false);
  });

  it("is not asked on a platform with no OAuth provider behind it", () => {
    /* canConnect in lib/socialPlatforms mirrors
       oauth.build_default_providers, which today builds Meta and nothing
       else. Instagram would answer oauth_platform_unsupported. */
    expect(needsPageChoice({ ...AMBIGUOUS, platform: "instagram" })).toBe(false);
    expect(needsPageChoice({ ...AMBIGUOUS, platform: "tiktok" })).toBe(false);
  });

  it("is not asked on a platform nothing recognises", () => {
    expect(needsPageChoice({ ...AMBIGUOUS, platform: "myspace" })).toBe(false);
  });
});

describe("the figure beside a Page", () => {
  it("is null when the platform stated no number", () => {
    /* A Page with no follower count shows a sentence saying so, not a zero
       it never earned. Returning null rather than "" is what forces the
       caller to decide that. */
    expect(followerText(null, "fr")).toBeNull();
    expect(followerText(undefined, "fr")).toBeNull();
  });

  it("is written for a count of zero, which is a number the platform gave", () => {
    expect(followerText(0, "en")).toBe("0");
  });

  it("groups a real count rather than running the digits together", () => {
    const text = followerText(1688, "en");
    expect(text).not.toBeNull();
    expect(text).not.toBe("1688");
    /* Not an assertion on the separator itself: it is a comma in English, a
       space of some width in French, and which space depends on the ICU the
       runtime happens to ship. What matters is that the digits survive in
       order and something sits between them. */
    expect(text).toMatch(/^1\D?688$/);
  });

  it("uses the reader's language, so the two catalogues do not disagree", () => {
    expect(followerText(1688, "fr")).not.toBe(followerText(1688, "en"));
  });

  it("refuses a value that is not a usable number instead of printing NaN", () => {
    /* The value comes off a JSON body, so the type is a claim rather than a
       guarantee, and "NaN followers" reads as a broken platform rather than
       a broken client. */
    expect(followerText(Number.NaN, "en")).toBeNull();
    expect(followerText(Number.POSITIVE_INFINITY, "en")).toBeNull();
    expect(followerText("1688" as unknown as number, "en")).toBeNull();
  });
});

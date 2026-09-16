/* The two languages of the Google sign in copy say the same things.

   WHY THIS NEEDS A TEST AT ALL. A missing key does not fail anything on its
   own: i18next falls back to the other language, so a key written in English
   and forgotten in French renders English in the middle of a French screen,
   quietly, with a green build behind it. That failure mode is exactly the one
   errorMessages.test.ts and notificationBodies.test.ts already exist for, and
   the auth screens are the worst place to meet it, because they are the first
   thing a new user sees and the one screen they cannot skip.

   Key sets rather than sentences: nothing here can check that a translation is
   GOOD, and pretending otherwise would be a test that passes on "Google" typed
   into both columns. What it can check is that neither column is short. */
import { describe, expect, it } from "vitest";
import {
  google_account_en,
  google_account_fr,
  google_auth_en,
  google_auth_fr
} from "./googleStrings";

const GROUPS: [string, Record<string, string>, Record<string, string>][] = [
  ["auth", google_auth_fr, google_auth_en],
  ["account", google_account_fr, google_account_en]
];

describe("the two languages agree", () => {
  it.each(GROUPS)("has the same keys in %s", (_group, fr, en) => {
    expect(Object.keys(fr).sort()).toEqual(Object.keys(en).sort());
  });

  it.each(GROUPS)("has no empty sentence in %s", (_group, fr, en) => {
    for (const value of [...Object.values(fr), ...Object.values(en)]) {
      expect(value.trim()).not.toBe("");
    }
  });
});

describe("the keys are namespaced so a deep merge cannot collide", () => {
  /* Both bundles are merged INTO groups other files own, so a key here that
     happens to match one there would silently replace it. The auth group is
     i18n.ts's and the account group is accountStrings.ts's. Prefixing is what
     keeps the merge additive, and this is the check that somebody adding a key
     remembers to. */
  /* Three keys here are neither google* nor proof*, because they are Google
     aware rewrites of copy accountStrings.ts already owns under a name of its
     own (emailWhyPassword, phoneWhyPassword). They are listed by hand so that
     the rule stays a rule rather than becoming a shrug. */
  const KNOWN_UNPREFIXED = new Set(["emailWhyProof", "phoneWhyProof", "passwordMaybeFirst"]);

  it("prefixes every auth and account key", () => {
    const keys = [...Object.keys(google_auth_en), ...Object.keys(google_account_en)];
    for (const key of keys) {
      if (KNOWN_UNPREFIXED.has(key)) continue;
      expect(key.startsWith("google") || key.startsWith("proof")).toBe(true);
    }
  });
});

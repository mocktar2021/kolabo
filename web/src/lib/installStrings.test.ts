/* The install copy exists in both languages.

   The same check googleStrings.test.ts makes and for the same reason: a key
   written in one language and forgotten in the other fails nothing, because
   i18next falls back and renders English inside a French screen with a green
   build behind it.

   It matters a little more here than elsewhere. These six sentences are the
   only instructions an iPhone user ever gets, Safari offers no install API at
   all, and somebody who cannot follow them has no second route to an icon on
   their home screen. */
import { describe, expect, it } from "vitest";
import { install_en, install_fr } from "./installStrings";

describe("the install copy", () => {
  it("has the same keys in both languages", () => {
    expect(Object.keys(install_fr).sort()).toEqual(Object.keys(install_en).sort());
  });

  it("has no empty sentence", () => {
    for (const value of [...Object.values(install_fr), ...Object.values(install_en)]) {
      expect(value.trim()).not.toBe("");
    }
  });

  it("keeps all three iOS steps, because two of three is not a set of directions", () => {
    for (const group of [install_fr, install_en]) {
      expect(group.iosStep1).toBeTruthy();
      expect(group.iosStep2).toBeTruthy();
      expect(group.iosStep3).toBeTruthy();
    }
  });
});

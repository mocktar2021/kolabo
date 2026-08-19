import { describe, expect, it } from "vitest";
import { MIN_LIVE_PACKAGES, deactivationHidesProfile, minPrice } from "./pricing";

/* The rule behind the Active switch on a creator's packages.

   IT IS WORTH TESTING DESPITE BEING "JUST A WARNING", because the failure is
   silent and only one direction of it is loud. A creator who drops below
   MIN_LIVE_PACKAGES stops appearing in discovery — the API does not refuse,
   nothing turns red, and the first sign of trouble is a month with no orders.
   The sentence this predicate gates is the only place the platform says so,
   so a false here is a storefront that vanished without a word.

   The other direction matters too, in a smaller way: a warning that fires
   when nothing is at stake is a warning people learn to click through, and
   they click through the one that mattered with it. */

describe("MIN_LIVE_PACKAGES", () => {
  it("still mirrors backend/app/core/pricing.py", () => {
    /* Pinned rather than trusted. The number is duplicated on purpose (no
       endpoint reports it), and this is the line that fails when the backend
       moves it and the mirror does not follow — which would leave two
       sentences, in two languages, quoting a threshold nobody enforces. */
    expect(MIN_LIVE_PACKAGES).toBe(3);
  });
});

describe("deactivationHidesProfile", () => {
  it("warns on exactly the click that crosses the threshold", () => {
    // At the minimum: findable now, not findable once this one goes off.
    expect(deactivationHidesProfile(MIN_LIVE_PACKAGES)).toBe(true);
  });

  it("stays quiet while turning one off still leaves enough", () => {
    expect(deactivationHidesProfile(MIN_LIVE_PACKAGES + 1)).toBe(false);
    expect(deactivationHidesProfile(MIN_LIVE_PACKAGES + 7)).toBe(false);
  });

  it("stays quiet below the threshold, where the profile is already hidden", () => {
    /* Nothing is lost by this click that was not lost already, and telling
       somebody they are about to disappear when they disappeared last week
       is how the sentence stops being believed. */
    expect(deactivationHidesProfile(MIN_LIVE_PACKAGES - 1)).toBe(false);
    expect(deactivationHidesProfile(1)).toBe(false);
    expect(deactivationHidesProfile(0)).toBe(false);
  });
});

describe("minPrice", () => {
  it("returns the floor for a launch currency and zero for an unknown one", () => {
    /* The other half of this file, exercised because the packages form reads
       both: a currency with no floor must produce 0 and not undefined, or the
       form's belowFloor comparison silently turns every price into an error. */
    expect(minPrice("XOF")).toBe(5000);
    expect(minPrice("GHS")).toBe(100);
    expect(minPrice("EUR")).toBe(0);
  });
});

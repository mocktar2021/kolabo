import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  COMMISSION_BPS,
  MIN_LIVE_PACKAGES,
  commissionFor,
  deactivationHidesProfile,
  minPrice
} from "./pricing";

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

/* THE COMMISSION MIRROR, AND THE ONE THING THAT MAKES IT SAFE TO PUBLISH.

   pricing.ts carries COMMISSION_BPS as a hand maintained copy of
   settings.commission_bps, and the comment there is honest about why that was
   acceptable: the only screen reading it was an admin predicting the split of
   a disputed escrow, the server still computed the real figure at resolution,
   and a stale mirror therefore cost an admin a wrong estimate and nothing
   else.

   THE PRICING PAGE CHANGES THAT BARGAIN. /pricing, /for-brands and
   /for-creators now interpolate this constant into published copy in two
   languages. A stale mirror there is not a wrong estimate on an internal
   screen, it is a wrong price on a public page, which is the kind of mistake
   somebody quotes back at you after relying on it. The duplication keeps its
   justification only for as long as something notices when the two numbers
   disagree, and this is that something.

   READ AS TEXT, NOT IMPORTED, because the thing being checked is Python and
   this is a vitest suite in the web package. The repository already does this
   wherever running the real thing is out of reach, which is the argument
   siteRoutes.test.ts makes at length: it asserts on App.tsx as source,
   punctuation.test.ts walks web/src and reads files, and the backend's
   test_schema_owned_by_migrations parses migrations the same way.

   THE REAL FIX IS AN ENDPOINT, and it is small. GET /payments/config already
   exists and already reports the enabled countries to the payout form. The
   rate belongs in that payload; then the pages read it, the mirror goes away
   and so does this block. Until then the mirror is what exists.

   IT THROWS RATHER THAN SKIPS when the setting cannot be found. A guard that
   quietly does nothing is worse than no guard, because it reads as though it
   is covering something. One repository holds both halves, so the file is
   either there or the checkout is broken, and saying so is the right answer.

   The same technique would harden MIN_LIVE_PACKAGES above, which is still
   pinned to a literal 3. Left alone here deliberately: that number is not
   published to anybody, so it does not belong in a change about the pricing
   page. */
const HERE = dirname(fileURLToPath(import.meta.url));
/* web/src/lib up to the repository root, then into the settings module. */
const CONFIG = resolve(HERE, "..", "..", "..", "backend", "app", "core", "config.py");

function backendCommissionBps(): number {
  const source = readFileSync(CONFIG, "utf8");
  const match = /^\s*commission_bps:\s*int\s*=\s*(\d+)\s*$/m.exec(source);
  if (!match) {
    throw new Error(
      `Could not find "commission_bps: int = <n>" in ${CONFIG}. If that setting has ` +
        "been renamed or moved, this test has to follow it rather than be deleted: " +
        "the pricing page publishes COMMISSION_BPS to the world."
    );
  }
  return Number(match[1]);
}

describe("the published commission rate", () => {
  it("matches settings.commission_bps in the backend", () => {
    expect(COMMISSION_BPS).toBe(backendCommissionBps());
  });

  /* The rate is rendered as COMMISSION_BPS / 100 followed by a percent sign.
     A value that is not a whole number of percent would publish something
     like "15.5 %", which the copy around it is not written for. If the rate
     ever genuinely needs a fraction of a percent, the sentences and this
     expectation change together and deliberately. */
  it("is a whole number of percent, which is what the copy assumes", () => {
    expect(COMMISSION_BPS % 100).toBe(0);
  });

  /* The worked example on the pricing page is computed through this function
     rather than written into the copy, so these two lines are that example.
     25,000 XOF is the figure docs/PAYMENTS_FEDAPAY.md works through, kept the
     same so the document and the page describe one transaction. */
  it("computes the published worked example", () => {
    expect(commissionFor(25000)).toBe(3750);
    expect(25000 - commissionFor(25000)).toBe(21250);
  });

  /* Integer division with the remainder left on the creator's side, exactly
     like commission_for in payments/service.py. 15 percent of 10,001 is
     1,500.15, and that 0.15 has to stay with the creator rather than being
     rounded up into the platform's share. */
  it("leaves the rounding remainder with the creator", () => {
    expect(commissionFor(10001)).toBe(1500);
  });
});

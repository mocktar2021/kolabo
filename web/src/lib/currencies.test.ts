/* The currencies the campaign forms offer are the currencies the open markets
   use, and this is what keeps that true.

   THE FAILURE IT EXISTS FOR RUNS IN BOTH DIRECTIONS.

   Too many: a dropdown offering NGN is a promise that a campaign can be priced
   in naira and paid out in naira. It cannot. Nigeria, Ghana and Cameroon are
   closed, and their currencies sit outside the XOF area the payment provider's
   licence covers, so a brand pricing a brief in one of them produces a
   collaboration nobody can be paid for. That is the state this test was
   written to end: the list kept three currencies for a month after the three
   markets were closed.

   Too few: the day Ghana opens, country_config.py changes and this package
   does not, and the campaign form silently refuses to let a Ghanaian brand
   price anything in cedis. That direction is quieter and lasts longer, because
   nothing looks broken to anybody who is not Ghanaian.

   READ AS TEXT, NOT IMPORTED, because the authority is Python and this is a
   vitest suite in the web package. pricing.test.ts makes the same move against
   config.py and states the argument at length: the repository already reads
   across this seam wherever running the real thing is out of reach, and the
   backend's own test_schema_owned_by_migrations parses migrations the same way.

   IT THROWS RATHER THAN SKIPS when the table cannot be read. A guard that
   quietly does nothing is worse than no guard, because it reads as though it
   is covering something.

   THE REAL FIX IS AN ENDPOINT, as it is for the commission mirror.
   GET /payments/config already reports the enabled countries; the currency per
   country belongs in that payload, and then the forms read it and both this
   list and this file go away. Until then the list is a mirror and this is what
   notices when it drifts. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { CURRENCIES } from "./campaignOptions";

const HERE = dirname(fileURLToPath(import.meta.url));
/* web/src/lib up to the repository root, then into the country table. */
const CONFIG = resolve(HERE, "..", "..", "..", "backend", "app", "core", "country_config.py");

/* Every row of COUNTRY_CONFIG, in the file's own order:
     "BJ": {"name": "Benin", "currency": "XOF", "language": "fr", "enabled": True},
   The regex names the two fields this test cares about and ignores the rest,
   so adding a key to those dicts does not break it. */
const ROW = /"currency":\s*"([A-Z]{3})"[^}]*"enabled":\s*(True|False)/g;

function backendOpenCurrencies(): string[] {
  const source = readFileSync(CONFIG, "utf8");
  const open: string[] = [];
  let seen = 0;
  for (const match of source.matchAll(ROW)) {
    seen += 1;
    if (match[2] === "True" && !open.includes(match[1])) open.push(match[1]);
  }
  if (seen === 0) {
    throw new Error(
      `Could not read any country row out of ${CONFIG}. If COUNTRY_CONFIG has been ` +
        "reshaped or moved, this test has to follow it rather than be deleted: it is " +
        "the only thing holding the campaign form's currency list to the markets " +
        "where money can actually move."
    );
  }
  return open;
}

describe("the currencies the campaign forms offer", () => {
  it("are exactly the currencies of the open markets", () => {
    /* Sorted on both sides: this is about which currencies, not about the
       order they appear in a dropdown. */
    expect([...CURRENCIES].sort()).toEqual([...backendOpenCurrencies()].sort());
  });

  it("offers at least one, because every form defaults to CURRENCIES[0]", () => {
    /* Board, CampaignDetail and PublicProfile all seed their state with
       CURRENCIES[0]. An empty list would make that undefined and post a
       campaign with no currency at all. */
    expect(CURRENCIES.length).toBeGreaterThan(0);
  });
});

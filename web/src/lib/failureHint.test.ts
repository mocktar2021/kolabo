/* A gateway refusal either helps the brand or says nothing new.

   KOL-149. On 31 October two real payments failed on a number typed in local
   form. FeexPay answered PAYER_NOT_FOUND, the screen said "nothing was
   charged, you can try again", and the brand did exactly that, with the same
   number, and failed again. The generic line is true and, for this failure,
   worse than useless: it invites the action that cannot work.

   WHAT THIS GUARDS IS THE FALLBACK AS MUCH AS THE MAPPING. The tempting
   version of this feature prints `failure_reason` straight at the user, which
   is how a brand in Cotonou ends up reading PAYER_NOT_FOUND. The second and
   third cases below are the ones that fail if somebody does that. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
import { FAILURE_HINTS, failureHint } from "./checkout";

describe("the hint shown for a failed payment", () => {
  it("has its own sentence for the one code seen in production", () => {
    expect(failureHint("PAYER_NOT_FOUND")).toBe("pay.failedPayerNotFound");
  });

  it("falls back to the generic line for a code nobody has seen", () => {
    // Not a thrown error, not the raw code, not an empty string. The generic
    // sentence is always true, which is what makes it a safe default.
    expect(failureHint("SOME_FUTURE_CODE")).toBe("pay.failedHint");
  });

  it("falls back for no reason at all", () => {
    // A cancelled intent, or one that failed before the gateway said why.
    expect(failureHint(null)).toBe("pay.failedHint");
    expect(failureHint("")).toBe("pay.failedHint");
  });

  it("never returns a provider code as if it were a translation key", () => {
    // The failure mode this whole module exists to prevent, asserted
    // directly: every value in the map is a pay.* key, not a gateway string.
    for (const value of Object.values(FAILURE_HINTS)) {
      expect(value.startsWith("pay.")).toBe(true);
    }
  });

  it("maps every key to a sentence that exists in both languages", () => {
    // A key written in one language renders English inside a French screen
    // with a green build behind it, the failure installStrings.test.ts was
    // written for. Checked against the bundle source rather than i18next,
    // because this package's vitest runs in node with no app bootstrapped.
    const source = readFileSync(resolve(HERE, "./paymentStrings.ts"), "utf8");
    for (const key of Object.values(FAILURE_HINTS)) {
      const name = key.replace(/^pay\./, "");
      const occurrences = source.split(`${name}:`).length - 1;
      expect(occurrences).toBe(2);
    }
  });
});

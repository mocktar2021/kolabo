/* The brand's statement must not claim to show what left their wallet.

   WHY THIS IS A TEST AND NOT A COMMENT. On 31 October a brand funded a 500
   XOF escrow and 509 left their Mobile Money wallet: FeexPay adds its
   collection fee on top of the amount requested and charges it to the payer,
   so the boutique receives the full 500 and the payer is out 509. Nothing in
   the product said so, and the statement screen said the opposite, in two
   languages and in the user guide as well:

     "Ce que vous voyez ici est ce qui est parti de votre portefeuille."
     "What you see here is what left your wallet."

   Written to reassure, and in the presence of an operator surcharge it does
   the exact opposite: it is the sentence a brand quotes back when they
   notice. On a platform whose whole proposition in this market is that money
   is safe and nothing is taken quietly, that is the worst available sentence.

   The claim about commission is true and stays. The claim about the wallet
   cannot, and a comment would not have stopped it being written: it was
   written three times, in three files, by somebody who believed it. So this
   asserts on the source text, which is the pattern siteRoutes.test.ts and
   punctuation.test.ts already use for things a render cannot reach.

   See KOL-153. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const read = (p: string) => readFileSync(resolve(HERE, p), "utf8");

const SPEND = read("./spendStrings.ts");
const GUIDE = read("./guideStrings.ts");
const PAYMENTS = read("./paymentStrings.ts");
const CHECKOUT = read("../pages/Checkout.tsx");

/* The exact claims that were wrong, in both languages. Matched loosely on the
   operative phrase rather than the whole sentence, so a reworded version of
   the same promise is caught too. */
const WALLET_CLAIMS = [
  "parti de votre portefeuille",
  "left your wallet",
];

describe("the buyer statement's claims about money", () => {
  it("never tells a brand that the figures shown are what left their wallet", () => {
    for (const claim of WALLET_CLAIMS) {
      expect(SPEND).not.toContain(claim);
      expect(GUIDE).not.toContain(claim);
    }
  });

  it("says the operator adds a fee, in both languages", () => {
    // The French copy and the English copy each have to carry it. One of the
    // two is how a bilingual product tells half its users the truth.
    expect(SPEND).toContain("opérateur Mobile Money");
    expect(SPEND).toContain("Mobile Money operator");
  });

  it("says that fee is the operator's and not Kolabo's", () => {
    // Without this the warning creates the suspicion it exists to prevent.
    expect(SPEND).toContain("pas à Kolabo");
    expect(SPEND).toContain("not to Kolabo");
  });

  it("still says the Kolabo commission does not come out of what the brand pays", () => {
    // The part that was always true. A fix that quietly dropped it would
    // leave brands thinking we take a cut from both sides.
    expect(SPEND).toContain("jamais sur ce que vous payez");
    expect(SPEND).toContain("never out of what you pay");
  });
});

describe("the funding screen", () => {
  it("has the operator fee warning in both language bundles", () => {
    // Two occurrences: once in fr, once in en. A key written in one language
    // only renders English inside a French screen with a green build behind
    // it, which is the failure installStrings.test.ts was written for.
    const occurrences = PAYMENTS.split("fundOperatorFee:").length - 1;
    expect(occurrences).toBe(2);
  });

  it("actually renders it, rather than merely defining it", () => {
    // A string nobody reads is not a disclosure.
    expect(CHECKOUT).toContain('t("pay.fundOperatorFee")');
  });

  it("warns before the prompt is sent, not after", () => {
    // Above the submit button in the source is above it on the screen. A
    // warning under the button is a receipt.
    const warning = CHECKOUT.indexOf('t("pay.fundOperatorFee")');
    const submit = CHECKOUT.indexOf('t("pay.fundSubmit")');
    expect(warning).toBeGreaterThan(-1);
    expect(submit).toBeGreaterThan(-1);
    expect(warning).toBeLessThan(submit);
  });
});

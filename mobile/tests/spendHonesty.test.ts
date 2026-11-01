/* The brand's statement must not claim to show what left their wallet.

   THE MOBILE HALF OF web/src/lib/spendHonesty.test.ts, and a deliberate
   duplicate for the reason punctuation.test.ts gives about itself: the two
   packages share no module, and a guard that only one app runs is worse than
   no guard, because it reads as though both are covered.

   On 31 October a brand funded a 500 XOF escrow and 509 left their Mobile
   Money wallet. The operator adds its collection fee on top of the amount
   requested and charges it to the payer. Both apps carried a sentence
   promising the opposite:

     "Ce que vous voyez ici est ce qui est parti de votre portefeuille."
     "What you see here is what left your wallet."

   NARROWER THAN THE WEB TEST ON PURPOSE. The Mobile Money funding form with
   its network picker is web only today, so there is no mobile funding screen
   to warn on and nothing here asserts one. What both apps do have is the
   statement screen, and that is what this guards. When the picker is ported,
   the funding-screen half of the web test should be ported with it.

   See KOL-153. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const STRINGS = readFileSync(resolve(HERE, "../src/strings.ts"), "utf8");

const WALLET_CLAIMS = ["parti de votre portefeuille", "left your wallet"];

/* Collapsed before the search, so the guard does not depend on where a line
   happens to wrap. The web half explains the near miss that prompted it. */
const flat = (text: string) => text.replace(/\s+/g, " ");

describe("the buyer statement's claims about money, on mobile", () => {
  it("never tells a brand that the figures shown are what left their wallet", () => {
    for (const claim of WALLET_CLAIMS) {
      expect(flat(STRINGS)).not.toContain(claim);
    }
  });

  it("says the operator adds a fee, in both languages", () => {
    expect(STRINGS).toContain("opérateur Mobile Money");
    expect(STRINGS).toContain("Mobile Money operator");
  });

  it("says that fee is the operator's and not Kolabo's", () => {
    expect(STRINGS).toContain("pas à Kolabo");
    expect(STRINGS).toContain("not to Kolabo");
  });

  it("still says the Kolabo commission does not come out of what the brand pays", () => {
    expect(STRINGS).toContain("jamais sur ce que vous payez");
    expect(STRINGS).toContain("never out of what you pay");
  });
});

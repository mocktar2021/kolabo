/* Every way a brand can buy has to state the content licence, on BOTH
   clients.

   WHAT WENT WRONG (KOL-169). Article 10 of the collaboration contract makes
   the parties choose how the brand may use the content, and
   contracts/service.py::_licence_snapshot refuses to build a contract when
   neither the proposal nor the campaign carries that block
   (contract_licence_terms_missing). The web app asks for it on all three
   buying journeys. The app did not ask on any of them, so a direct order
   placed from a phone could be accepted by the creator and then had no
   contract at all — a refusal landing on the CREATOR, days later, for the one
   thing only the buyer could have fixed.

   WHY A SOURCE TEST RATHER THAN A RENDER TEST. There is no simulator in CI
   (see the mobile job in .github/workflows/ci.yml), and what broke was not a
   component's behaviour: it was a request body missing a key that the server
   silently accepts. pydantic ignores an undeclared key and OrderIn declares
   licence_terms as optional, so nothing anywhere fails loudly at the moment
   the licence goes missing. The only place the omission is visible is the
   source of the call itself.

   WHY IT READS BOTH CLIENTS. The gap existed for weeks because nothing
   compared them: a flow shipped on web, the mobile twin was written from the
   same endpoint docs, and the licence was simply not in the mobile copy.
   Pinning the six call sites together is what makes the next divergence a red
   CI run instead of a creator with an unsignable contract.

   WHAT IT DOES NOT CHECK. Whether the licence is CORRECT. That is
   licenceTerms.test.ts (shape, required fields per option) and the backend's
   own campaigns/licence.py (the 400 naming what is missing). This file only
   checks that a licence is asked for and sent. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..");

function read(relative: string): string {
  /* A missing file is a failure and never a skip. If web/ is not on disk the
     cross-client half of this file would quietly stop checking anything, which
     is the exact failure mode it exists to prevent. actions/checkout puts the
     whole repository on disk and the other tests in this folder already read
     backend/app/**.py from it. */
  try {
    return readFileSync(resolve(REPO, relative), "utf8");
  } catch {
    throw new Error(
      `${relative} could not be read. This test compares the mobile and web ` +
        `order paths, so it needs both trees. If the file moved, move this ` +
        `assertion with it rather than deleting it.`
    );
  }
}

/* One function's text, from its header to the next top-level function in the
   file. Sliced per function because both storefronts post to /campaigns/orders
   twice — once for a listed pack and once for the buyer's own terms — and a
   whole-file search would let either one carry the licence for both. */
function functionBody(source: string, header: string): string {
  const start = source.indexOf(header);
  expect(start, `${header} not found`).toBeGreaterThan(-1);
  const after = source.slice(start + header.length);
  const next = after.search(/\n {2}(?:async )?function /);
  return next === -1 ? after : after.slice(0, next);
}

/* The same text with every comment taken out. Used only by the negative
   assertions below: "this function must not mention a licence" should be a
   statement about the code, and a prose comment explaining WHY it does not is
   exactly the thing a reader would add next. */
function codeOnly(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

type Site = {
  what: string;
  file: string;
  fn: string;
  path: string;
  /* The helper that turns the form state into the request body. The two
     clients have their own copy of the licence module, so the name differs;
     what must not differ is that one is called. */
  builder: string;
};

const SITES: Site[] = [
  {
    what: "mobile, listed pack ordered straight from a profile",
    file: "mobile/src/screens/CreatorPublicScreen.tsx",
    fn: "async function sendOrder()",
    path: '"/campaigns/orders"',
    builder: "draftPayload(licence)",
  },
  {
    what: "mobile, buyer's own terms sent from a profile",
    file: "mobile/src/screens/CreatorPublicScreen.tsx",
    fn: "async function sendNegotiatedOrder()",
    path: '"/campaigns/orders"',
    builder: "draftPayload(licence)",
  },
  {
    what: "mobile, basket checked out",
    file: "mobile/src/screens/CartScreen.tsx",
    fn: "async function checkout()",
    path: '"/campaigns/orders/checkout"',
    builder: "draftPayload(licence)",
  },
  {
    what: "web, listed pack ordered straight from a profile",
    file: "web/src/pages/PublicProfile.tsx",
    fn: "async function placeOrder()",
    path: '"/campaigns/orders"',
    builder: "licenceBody(licence)",
  },
  {
    what: "web, buyer's own terms sent from a profile",
    file: "web/src/pages/PublicProfile.tsx",
    fn: "async function placeNegotiatedOrder()",
    path: '"/campaigns/orders"',
    builder: "licenceBody(licence)",
  },
  {
    what: "web, basket checked out",
    file: "web/src/pages/CartPage.tsx",
    fn: "async function checkout()",
    path: '"/campaigns/orders/checkout"',
    builder: "licenceBody(licence)",
  },
];

describe("every buying journey states the content licence", () => {
  for (const site of SITES) {
    describe(site.what, () => {
      const body = functionBody(read(site.file), site.fn);

      it("posts to the orders endpoint", () => {
        expect(body).toContain(site.path);
      });

      it("builds the licence block from the form", () => {
        expect(body).toContain(site.builder);
      });

      /* The guard, not only the call. Both clients disable the submit button
         until an option is chosen, so this line should be unreachable; it is
         what stops a body being posted with no licence if that gate is ever
         loosened, and it is the line that would be dropped first by somebody
         "simplifying" the function. */
      it("refuses to send when no option has been chosen", () => {
        expect(body).toContain("if (!terms) return;");
      });

      /* THE ASSERTION THIS FILE IS FOR. The block has to reach the request
         body. `const terms = ...` on its own is what the mobile screens were
         one edit away from having: a helper called and the result dropped. */
      it("spreads the block into the request body", () => {
        expect(body).toContain("...terms");
      });
    });
  }
});

/* The checkout has one more rule than the two profile paths, and it is not
   about a missing licence but about contradicting ones. The server fans a
   checkout out into one direct order per creator, and cart.py::_one_licence
   refuses with licence_terms_invalid when two lines of the same creator
   disagree. Both clients therefore hold ONE draft and put the same object on
   every line; a per-line draft would be the shape that trips that refusal. */
describe("a checkout sends one licence across every line", () => {
  const cases = [
    { client: "mobile", file: "mobile/src/screens/CartScreen.tsx" },
    { client: "web", file: "web/src/pages/CartPage.tsx" },
  ];

  for (const { client, file } of cases) {
    it(`${client} spreads the same block onto each item`, () => {
      const body = functionBody(read(file), "async function checkout()");
      /* One licence draft for the screen, mapped onto the lines. The shape
         that would fail is `items: posted.map(checkoutItem)` with the terms
         sent beside the list, where CartCheckoutIn does not declare them and
         pydantic drops them without a word. */
      expect(body).toMatch(/items: posted\.map\(\(line\) => \(\{ \.\.\.checkoutItem\(line\), \.\.\.terms \}\)\)/);
    });
  }
});

/* And the one place that deliberately asks for NO licence. Adding to a basket
   sends nothing to the server: the statement is made once at checkout, because
   one checkout becomes one order per creator and one answer has to cover all
   of them. Asking on both would let the two answers disagree, which is the
   refusal above. So this is pinned as a decision rather than left to be
   "fixed" by the next reader of this file. */
describe("adding to the basket asks for no licence", () => {
  const screen = read("mobile/src/screens/CreatorPublicScreen.tsx");

  for (const fn of ["function addPackageToCart()", "function addNegotiatedToCart()"]) {
    it(`${fn} sends no licence and is not gated on one`, () => {
      const body = codeOnly(functionBody(screen, fn));
      expect(body).not.toContain("licence");
      expect(body).not.toContain("terms");
    });
  }

  it("the two add buttons stay enabled without a licence", () => {
    /* Gated on the request in flight and on the terms of the offer, never on
       the licence. The negotiated one carries negComplete because a custom
       offer needs a platform, a deliverable, a price and a timeline before it
       can be a basket line at all. */
    expect(screen).toContain(`onPress={addNegotiatedToCart}
                    disabled={busy || !negComplete}`);
    expect(screen).toContain(`<GhostButton title={t("cart.add")} onPress={addPackageToCart} />`);
  });
});

/* The buttons that DO send. Each is disabled until the licence is complete,
   which is what keeps the guard inside the functions above unreachable in
   practice: a brand should be told what is missing by the control itself
   rather than by a refusal after a round trip. */
describe("the send buttons are gated on a complete licence", () => {
  it("mobile pack order", () => {
    const screen = read("mobile/src/screens/CreatorPublicScreen.tsx");
    expect(screen).toContain(`onPress={sendOrder}
                    loading={busy}
                    disabled={!draftIsComplete(licence)}`);
  });

  it("mobile negotiated order", () => {
    const screen = read("mobile/src/screens/CreatorPublicScreen.tsx");
    expect(screen).toContain(`onPress={sendNegotiatedOrder}
                    loading={busy}
                    disabled={!negComplete || !draftIsComplete(licence)}`);
  });

  it("mobile checkout", () => {
    const screen = read("mobile/src/screens/CartScreen.tsx");
    expect(screen).toContain(`disabled={selectedGroups.length === 0 || !draftIsComplete(licence)}`);
  });
});

/* The control itself, on every screen that sends. Without it the gates above
   can never open: a buyer would see a disabled button and no question to
   answer, which is worse than the bug this fixes. */
describe("each sending screen renders the licence form", () => {
  const screens = [
    "mobile/src/screens/CreatorPublicScreen.tsx",
    "mobile/src/screens/CartScreen.tsx",
  ];

  for (const file of screens) {
    it(`${file} renders LicenceFields`, () => {
      const source = read(file);
      expect(source).toContain('import { LicenceFields } from "../components/campaigns/LicenceFields";');
      expect(source).toContain("<LicenceFields value={licence} onChange={setLicence} />");
    });
  }

  /* Twice on the storefront, once per sheet, because the two sheets are
     mutually exclusive and each has to carry the question. One occurrence
     would mean a buyer who opened the other sheet sees a disabled button and
     nothing to fill in. */
  it("the storefront renders it in both order sheets", () => {
    const screen = read("mobile/src/screens/CreatorPublicScreen.tsx");
    const count = screen.split("<LicenceFields value={licence} onChange={setLicence} />").length - 1;
    expect(count).toBe(2);
  });
});

/* A brand has to be able to fund an escrow FROM THE APP.

   WHAT WENT WRONG. The checkout screen was written against FedaPay, a gateway
   with a hosted page: the app started a checkout the moment it mounted, opened
   the url that came back, and the payer picked their operator and typed their
   number on FedaPay's own page. FeexPay replaced it for the launch markets and
   works the other way round. It pushes a payment request to one handset on one
   named network and returns nothing to open, so the network and the phone have
   to travel in the request that starts the payment.

   Web was updated. The app was not. Its startCheckout posted neither field, so
   every attempt to fund from a phone died in feexpay.py::start_collection with
   "A mobile money network is required before a payment prompt can be sent",
   surfaced to the brand as payments_gateway_unavailable: "the payment service
   is temporarily unreachable". The service was reachable the whole time. Seen
   on production on 10 November on a real signed contract.

   WHY A SOURCE TEST RATHER THAN A RENDER TEST. There is no simulator in CI
   (see the mobile job in .github/workflows/ci.yml), and what broke was not a
   component's behaviour: it was a request body missing two keys that the
   server accepts as absent, because a redirect gateway legitimately sends
   neither. Nothing fails loudly at the moment they go missing. The only place
   the omission is visible is the source of the call itself.

   WHY IT READS BOTH CLIENTS. This is the same divergence as KOL-169 and it
   happened for the same reason: a flow changed on web and the mobile twin was
   left on the old shape. Pinning the two call sites together is what makes the
   next divergence a red CI run instead of a brand that cannot pay.

   WHAT IT DOES NOT CHECK. Whether a payment succeeds. That is the backend's
   test_device_prompt_checkout.py and test_feexpay.py, and ultimately a real
   prompt on a real handset. This file checks that the app asks for the two
   things FeexPay requires and sends them. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..");

function read(relative: string): string {
  /* A missing file is a failure and never a skip. If web/ or backend/ is not
     on disk the cross-tier halves of this file would quietly stop checking
     anything, which is the exact failure mode it exists to prevent. */
  try {
    return readFileSync(resolve(REPO, relative), "utf8");
  } catch {
    throw new Error(
      `${relative} could not be read. This test compares the mobile funding ` +
        `path against web and against the gateway's own network list, so it ` +
        `needs all three trees. If the file moved, move this assertion with ` +
        `it rather than deleting it.`
    );
  }
}

const MOBILE_LIB = read("mobile/src/lib/checkout.ts");
const WEB_LIB = read("web/src/lib/checkout.ts");
const SCREEN = read("mobile/src/screens/CheckoutScreen.tsx");
const STRINGS = read("mobile/src/lib/paymentStrings.ts");
const GATEWAY = read("backend/app/modules/payments/gateways/feexpay.py");

/* One function's text, from its header to the next top-level export. */
function functionBody(source: string, header: string): string {
  const start = source.indexOf(header);
  expect(start, `${header} not found`).toBeGreaterThan(-1);
  const after = source.slice(start + header.length);
  const next = after.search(/\nexport /);
  return next === -1 ? after : after.slice(0, next);
}

/* The same text with every comment taken out, for the assertions that must
   not be satisfied by a comment that merely mentions the field. */
function withoutComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

describe("the request that starts a payment", () => {
  for (const [label, source] of [
    ["mobile", MOBILE_LIB],
    ["web", WEB_LIB],
  ] as const) {
    it(`${label} sends the payer's network and phone`, () => {
      const body = withoutComments(functionBody(source, "export function startCheckout("));
      expect(body, "payer_network is not in the request body").toContain("payer_network:");
      expect(body, "payer_phone is not in the request body").toContain("payer_phone:");
    });

    it(`${label} reads them from the caller rather than inventing them`, () => {
      const body = withoutComments(functionBody(source, "export function startCheckout("));
      /* Not a literal, not a guess from the number. The screen asked the
         payer and the value travels through. */
      expect(body).toMatch(/payer_network:\s*opts\.network/);
      expect(body).toMatch(/payer_phone:\s*opts\.phone/);
    });

    it(`${label} can read the gateway's network list`, () => {
      expect(source, "collectionNetworks is missing").toContain(
        "export function collectionNetworks("
      );
      expect(source).toContain("/payments/collection-networks");
    });
  }
});

describe("the mobile checkout screen", () => {
  const code = withoutComments(SCREEN);

  it("asks which networks exist before it starts anything", () => {
    const asks = code.indexOf("collectionNetworks(");
    const starts = code.indexOf("startCheckout(");
    expect(asks, "the screen never asks for the networks").toBeGreaterThan(-1);
    expect(starts, "the screen never starts a checkout").toBeGreaterThan(-1);
    /* THE ORDER IS THE BUG. Starting first and asking afterwards is exactly
       what shipped, and the request that goes out first is the one that
       carries no network. */
    expect(asks, "the screen starts a checkout before it asks for networks").toBeLessThan(starts);
  });

  it("stops at the form when a network is required", () => {
    /* A non-empty list means there is a picker to render and nothing may be
       started until the payer has used it. Without this early return the
       screen would render the form AND fire the request behind it. */
    expect(code).toMatch(/available\.length\s*>\s*0/);
  });

  it("sends the network and the number the payer chose", () => {
    const send = code.slice(code.indexOf("async function sendPrompt("));
    expect(send).toMatch(/network,/);
    expect(send).toMatch(/phone:\s*phone\.trim\(\)/);
  });

  it("refuses to send without either of them", () => {
    const send = code.slice(
      code.indexOf("async function sendPrompt("),
      code.indexOf("async function retry(")
    );
    /* Caught here rather than at FeexPay, so the brand reads which field to
       fix instead of "the payment service is unreachable". */
    expect(send).toContain("pay.fundPickNetwork");
    expect(send).toContain("pay.fundNeedPhone");
  });

  it("decides the pending state from payer_action, not from checkout_url", () => {
    /* They are different questions. checkout_url also goes null once a
       redirect payment is terminal, so a screen that inferred the state from
       the url would tell somebody whose payment had already succeeded to go
       and check their phone.

       PINS THE DERIVATION, NOT THE MENTION. An earlier version of this
       assertion only looked for the string anywhere in the file, and passed
       with the render switched to `!intent?.checkout_url` because retry()
       below still mentioned payer_action. */
    expect(code).toMatch(/const prompt = intent\?\.payer_action === "device_prompt";/);
    expect(code, "the prompt state is being inferred from the url").not.toMatch(
      /const prompt = [^;]*checkout_url/
    );
  });

  it("offers a different wallet rather than resending to the same one", () => {
    /* A prompt that failed usually failed for a reason the payer can fix, and
       the most common one is the number. Resending to the same wallet without
       asking repeats the failure and spends another request. */
    const retry = code.slice(code.indexOf("async function retry("));
    expect(retry).toContain('payer_action === "device_prompt"');
    expect(retry).toMatch(/apply\(null\)/);
  });

  it("warns about the operator fee before the money moves", () => {
    /* KOL-153: a 500 XOF funding debited 509. The operator adds its fee on
       top and keeps it. Said afterwards this is a receipt, not a warning, so
       the string has to be on the form and not on the result card. */
    const form = code.slice(code.indexOf("pay.fundHow"), code.indexOf("pay.fundSubmit"));
    expect(form).toContain("pay.fundOperatorFee");
  });
});

/* Every network the gateway can return has to be nameable by both clients.

   The backend validates the payer's choice against this closed set and the
   clients render it. A value with no label falls back to the raw code, which
   is "CELTIIS BJ" in a chip, and that is the degraded case this test exists
   to keep rare rather than the one it accepts. */
describe("the network labels", () => {
  const block = GATEWAY.slice(
    GATEWAY.indexOf("_COLLECTION_NETWORKS: dict[str, tuple[str, ...]] = {"),
    GATEWAY.indexOf("_COLLECTION_STATUS")
  );
  /* Row by row, because the FIRST quoted token on each row is the country
     and not a network:

       "BJ": ("MTN", "MOOV", "CELTIIS BJ"),

     A whole-block match would read BJ, TG, CI and SN as operators and then
     demand a label for each of them. */
  const networks = block.split("\n").flatMap((line) => {
    const open = line.indexOf("(");
    if (open === -1 || !line.includes(":")) return [];
    return [...line.slice(open).matchAll(/"([^"]+)"/g)].map((m) => m[1]);
  });

  it("the gateway's list was actually found", () => {
    /* Guards the parse above: one that silently matches nothing would make
       every assertion below pass against an empty list. */
    expect(networks.length).toBeGreaterThanOrEqual(12);
    expect(networks).toContain("MTN");
    expect(networks).toContain("TOGOCOM TG");
  });

  for (const [label, source] of [
    ["mobile", MOBILE_LIB],
    ["web", WEB_LIB],
  ] as const) {
    const map = source.slice(
      source.indexOf("COLLECTION_NETWORK_LABELS: Record<string, string> = {"),
      source.indexOf("export function collectionNetworkLabel(")
    );
    const labelled = [...map.matchAll(/^\s*"?([A-Z][A-Z ]*?)"?:\s*"/gm)].map((m) => m[1]);

    it(`${label} names every network the gateway can return`, () => {
      for (const network of networks) {
        expect(labelled, `${network} has no label in ${label}`).toContain(network);
      }
    });

    it(`${label} has no label for a network that does not exist`, () => {
      for (const name of labelled) {
        expect(networks, `${name} is labelled in ${label} but the gateway never returns it`)
          .toContain(name);
      }
    });

    it(`${label} degrades an unknown code to the code itself`, () => {
      const fn = functionBody(source, "export function collectionNetworkLabel(");
      /* A chip with no label is unpickable. A new network at the provider
         should degrade to ugly, not to broken. */
      expect(withoutComments(fn)).toMatch(/\|\|\s*network/);
    });
  }
});

describe("the copy", () => {
  /* Both languages, because the pilot default is French and an untranslated
     key renders as "pay.fundPhone" on the one screen where a brand is about
     to part with money. */
  const keys = [
    "fundHow",
    "fundHowHint",
    "fundNetwork",
    "fundPhone",
    "fundPhoneHint",
    "fundOperatorFee",
    "fundSubmit",
    "fundPickNetwork",
    "fundNeedPhone",
    "promptSent",
    "promptSentHint",
    "promptSentTo",
    "promptChange",
    "failedPayerNotFound",
  ];
  const fr = STRINGS.slice(STRINGS.indexOf("const fr = {"), STRINGS.indexOf("const en = {"));
  const en = STRINGS.slice(STRINGS.indexOf("const en = {"));

  for (const key of keys) {
    it(`${key} exists in French`, () => {
      expect(fr).toContain(`${key}:`);
    });
    it(`${key} exists in English`, () => {
      expect(en).toContain(`${key}:`);
    });
  }
});

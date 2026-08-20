/* The basket's arithmetic, which is the part of the cart where a bug is
   silent: a total that is wrong still looks like a total, and the buyer only
   finds out at the escrow. Everything under test here is pure — items in,
   grouped per-currency totals out — which is why lib/cartTotals.ts holds no
   React and no React Native: this suite runs under node (vitest.config.ts).

   THE CASE THAT MATTERS MOST IS XOF + GHS. The platform sets no exchange rate
   and does not want one: an order carries one escrow and an escrow carries one
   currency, so adding 25 000 XOF to 400 GHS would invent a number nobody
   agreed to and that no order could ever be for. Web's test plan calls this
   O2 and calls it a release blocker.

   The grouping is the other half. It is not a display choice: cart.py's
   _group_by_creator keys on creator_user_id and keeps insertion order, and
   the checkout FANS OUT into one direct order per creator. A screen that
   grouped differently would promise a shape the receipt then contradicts. */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  MAX_CART_ITEMS,
  UNKNOWN_CREATOR,
  checkoutItem,
  groupByCreator,
  newLineId,
  normaliseLine,
  readLines,
  totalsByCurrency,
  type CartLine,
} from "../src/lib/cartTotals";

function line(over: Partial<CartLine> & { id: string; creator_user_id: string }): CartLine {
  return {
    creator: UNKNOWN_CREATOR,
    note: null,
    label: "Reel",
    package_id: "pkg-1",
    platform: "instagram",
    deliverable_type: "reel",
    quantity: 1,
    timeline_days: null,
    amount: 25000,
    currency: "XOF",
    ...over,
  };
}

describe("currencies are never summed together", () => {
  it("keeps XOF and GHS on separate rows", () => {
    const totals = totalsByCurrency([
      { amount: 25000, currency: "XOF" },
      { amount: 400, currency: "GHS" },
      { amount: 15000, currency: "XOF" },
    ]);
    expect(totals).toEqual([
      { currency: "GHS", amount: 400 },
      { currency: "XOF", amount: 40000 },
    ]);
  });

  it("never produces a single figure for a mixed basket", () => {
    /* The assertion is about the SHAPE, not the numbers: there is no row
       carrying 25 400, because there is no rate that would make one. */
    const totals = totalsByCurrency([
      { amount: 25000, currency: "XOF" },
      { amount: 400, currency: "GHS" },
    ]);
    expect(totals).toHaveLength(2);
    expect(totals.map((x) => x.amount)).not.toContain(25400);
  });

  it("sorts by currency code, so two identical baskets render alike", () => {
    const totals = totalsByCurrency([
      { amount: 1, currency: "XOF" },
      { amount: 1, currency: "NGN" },
      { amount: 1, currency: "GHS" },
      { amount: 1, currency: "XAF" },
    ]);
    expect(totals.map((x) => x.currency)).toEqual(["GHS", "NGN", "XAF", "XOF"]);
  });

  it("answers an empty basket with no rows rather than a zero", () => {
    expect(totalsByCurrency([])).toEqual([]);
  });
});

describe("the basket is grouped the way the endpoint groups it", () => {
  it("puts every line from one creator in one pile", () => {
    const groups = groupByCreator([
      line({ id: "a", creator_user_id: "kofi", amount: 25000 }),
      line({ id: "b", creator_user_id: "kofi", amount: 15000 }),
      line({ id: "c", creator_user_id: "kofi", amount: 10000 }),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].lines.map((l) => l.id)).toEqual(["a", "b", "c"]);
    /* One order, three deliverables, one summed budget — cart.py's _merge. */
    expect(groups[0].subtotals).toEqual([{ currency: "XOF", amount: 50000 }]);
  });

  it("keeps the piles in the order the basket was built", () => {
    const groups = groupByCreator([
      line({ id: "a", creator_user_id: "ama" }),
      line({ id: "b", creator_user_id: "kofi" }),
      line({ id: "c", creator_user_id: "ama" }),
      line({ id: "d", creator_user_id: "yaw" }),
    ]);
    expect(groups.map((g) => g.creator_user_id)).toEqual(["ama", "kofi", "yaw"]);
    expect(groups[0].lines.map((l) => l.id)).toEqual(["a", "c"]);
  });

  it("keeps two creators in two currencies apart, and never adds them", () => {
    /* Legitimate and untouched server-side: two creators are two orders and
       two escrows already. What must not happen is one figure. */
    const lines = [
      line({ id: "a", creator_user_id: "ama", amount: 25000, currency: "XOF" }),
      line({ id: "b", creator_user_id: "kofi", amount: 400, currency: "GHS" }),
    ];
    const groups = groupByCreator(lines);
    expect(groups[0].subtotals).toEqual([{ currency: "XOF", amount: 25000 }]);
    expect(groups[1].subtotals).toEqual([{ currency: "GHS", amount: 400 }]);
    expect(totalsByCurrency(lines)).toEqual([
      { currency: "GHS", amount: 400 },
      { currency: "XOF", amount: 25000 },
    ]);
  });

  it("shows one creator's mixed currencies as two subtotals, which is what the server refuses", () => {
    /* cart_mixed_currencies. The screen shows both rows and says why, rather
       than letting the buyer discover it as a 400 after the button. */
    const groups = groupByCreator([
      line({ id: "a", creator_user_id: "ama", amount: 25000, currency: "XOF" }),
      line({ id: "b", creator_user_id: "ama", amount: 400, currency: "GHS" }),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].subtotals).toEqual([
      { currency: "GHS", amount: 400 },
      { currency: "XOF", amount: 25000 },
    ]);
  });

  it("carries the identity snapshot of the first line of each pile", () => {
    const ama = {
      display_name: "Ama",
      avatar_url: null,
      top_platform: "tiktok",
      top_follower_count: 42000,
    };
    const groups = groupByCreator([
      line({ id: "a", creator_user_id: "ama", creator: ama }),
      line({ id: "b", creator_user_id: "ama" }),
    ]);
    expect(groups[0].creator).toEqual(ama);
  });
});

describe("a line becomes exactly one of the two bodies the endpoint takes", () => {
  it("sends a package id and nothing else", () => {
    expect(checkoutItem(line({ id: "a", creator_user_id: "ama", package_id: "pkg-9" }))).toEqual({
      package_id: "pkg-9",
    });
  });

  it("sends the whole custom offer when there is no package", () => {
    const body = checkoutItem(
      line({
        id: "a",
        creator_user_id: "ama",
        package_id: null,
        platform: "tiktok",
        deliverable_type: "video",
        quantity: 3,
        timeline_days: 7,
        amount: 40000,
        currency: "XOF",
      })
    );
    expect(body).toEqual({
      creator_user_id: "ama",
      platform: "tiktok",
      deliverable_type: "video",
      quantity: 3,
      rate_amount: 40000,
      currency: "XOF",
      timeline_days: 7,
    });
    /* Never both forms in one envelope: OrderIn answers 400 to that. */
    expect(body).not.toHaveProperty("package_id");
  });

  it("omits the note entirely when there is none", () => {
    expect(checkoutItem(line({ id: "a", creator_user_id: "ama", note: null }))).not.toHaveProperty(
      "note"
    );
    expect(checkoutItem(line({ id: "a", creator_user_id: "ama", note: "Avant le 12" }))).toMatchObject(
      { note: "Avant le 12" }
    );
  });
});

describe("a stored basket is made safe to render and safe to add up", () => {
  it("drops a row with no id or no creator", () => {
    expect(normaliseLine({ creator_user_id: "ama", amount: 1, currency: "XOF" })).toBeNull();
    expect(normaliseLine({ id: "a", amount: 1, currency: "XOF" })).toBeNull();
    expect(normaliseLine(null)).toBeNull();
    expect(normaliseLine("nope")).toBeNull();
  });

  it("drops a row whose amount is not a number", () => {
    /* THE REASON THIS CHECK EXISTS. A hand-edited or older row carrying
       "25000" as a string would make the totals concatenate instead of add —
       "025000" where a price belongs — and it would look like a total. */
    expect(
      normaliseLine({ id: "a", creator_user_id: "ama", amount: "25000", currency: "XOF" })
    ).toBeNull();
    expect(
      normaliseLine({ id: "a", creator_user_id: "ama", amount: Number.NaN, currency: "XOF" })
    ).toBeNull();
    expect(normaliseLine({ id: "a", creator_user_id: "ama", amount: 1, currency: "" })).toBeNull();
  });

  it("gives a row with no identity a neutral one rather than inventing a name", () => {
    const repaired = normaliseLine({ id: "a", creator_user_id: "ama", amount: 1, currency: "XOF" });
    expect(repaired?.creator).toEqual(UNKNOWN_CREATOR);
  });

  it("fills a half-written identity with nulls, never undefined", () => {
    const repaired = normaliseLine({
      id: "a",
      creator_user_id: "ama",
      amount: 1,
      currency: "XOF",
      creator: { display_name: "Ama" },
    });
    expect(repaired?.creator).toEqual({
      display_name: "Ama",
      avatar_url: null,
      top_platform: null,
      top_follower_count: null,
    });
  });

  it("never rewrites the terms it normalises", () => {
    const repaired = normaliseLine({
      id: "a",
      creator_user_id: "ama",
      amount: 25000,
      currency: "XOF",
      label: "Reel Instagram",
      package_id: "pkg-3",
      note: "Avant le 12",
    });
    expect(repaired?.amount).toBe(25000);
    expect(repaired?.package_id).toBe("pkg-3");
    expect(repaired?.note).toBe("Avant le 12");
  });

  it("survives a basket that will not parse rather than throwing on launch", () => {
    expect(readLines(null)).toEqual([]);
    expect(readLines("")).toEqual([]);
    expect(readLines("{not json")).toEqual([]);
    expect(readLines('{"items":[]}')).toEqual([]);
  });

  it("keeps the good rows out of a partly broken basket", () => {
    const stored = JSON.stringify([
      { id: "a", creator_user_id: "ama", amount: 25000, currency: "XOF" },
      { creator_user_id: "kofi", amount: 400, currency: "GHS" },
      { id: "c", creator_user_id: "yaw", amount: "400", currency: "GHS" },
    ]);
    expect(readLines(stored).map((l) => l.id)).toEqual(["a"]);
  });

  it("caps a stored basket at the ceiling the endpoint enforces", () => {
    const stored = JSON.stringify(
      Array.from({ length: MAX_CART_ITEMS + 5 }, (_, i) => ({
        id: `l${i}`,
        creator_user_id: "ama",
        amount: 5000,
        currency: "XOF",
      }))
    );
    expect(readLines(stored)).toHaveLength(MAX_CART_ITEMS);
  });

  it("mirrors the backend ceiling", () => {
    /* MAX_CART_ITEMS in backend/app/modules/campaigns/cart.py. Held here so a
       full basket says so at the button rather than after a round trip that
       refuses the whole checkout. */
    const cart = readFileSync(
      fileURLToPath(new URL("../../backend/app/modules/campaigns/cart.py", import.meta.url)),
      "utf8"
    );
    const declared = /^MAX_CART_ITEMS = (\d+)$/m.exec(cart);
    expect(declared).not.toBeNull();
    expect(Number(declared?.[1])).toBe(MAX_CART_ITEMS);
  });

  it("gives every line its own key", () => {
    const ids = new Set(Array.from({ length: 50 }, () => newLineId()));
    expect(ids.size).toBe(50);
  });
});

/* The copy, in both languages.

   errorMessages.test.ts guards the codes the BACKEND sends; nothing guards a
   runtime bundle, and a key present in one language and missing in the other
   falls back to the other language mid-screen — which in a francophone pilot
   means a French reader hitting an English sentence with nothing going red.
   Read as text rather than imported, because lib/cartStrings.ts imports the
   i18n instance, which pulls in expo-localization and cannot load here. */
describe("the cart copy exists in both languages", () => {
  const source = readFileSync(
    fileURLToPath(new URL("../src/lib/cartStrings.ts", import.meta.url)),
    "utf8"
  ).replace(/\/\*[\s\S]*?\*\//g, "");

  function bundle(name: "fr" | "en"): Record<string, string> {
    const start = source.indexOf(`const ${name} = {`);
    expect(start).toBeGreaterThan(-1);
    const end = source.indexOf("\n};", start);
    const body = source.slice(start, end);
    const out: Record<string, string> = {};
    let group = "";
    for (const raw of body.split("\n")) {
      const opened = /^ {2}([A-Za-z_]\w*): \{$/.exec(raw);
      if (opened) {
        group = opened[1];
        continue;
      }
      const entry = /^ {4}([A-Za-z_]\w*): "(.*)",$/.exec(raw);
      if (entry && group) out[`${group}.${entry[1]}`] = entry[2];
    }
    return out;
  }

  const fr = bundle("fr");
  const en = bundle("en");

  it("was read at all", () => {
    expect(Object.keys(fr).length).toBeGreaterThan(20);
  });

  it("has the same keys in French and English", () => {
    expect(Object.keys(fr).sort()).toEqual(Object.keys(en).sort());
  });

  it("has no empty sentence in either language", () => {
    const blank = [...Object.entries(fr), ...Object.entries(en)]
      .filter(([, text]) => text.trim() === "")
      .map(([key]) => key);
    expect(blank).toEqual([]);
  });

  it("asks for the same interpolation values in both", () => {
    const placeholders = (s: string) =>
      [...s.matchAll(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g)].map((m) => m[1]).sort().join(",");
    const mismatched = Object.keys(fr).filter((k) => placeholders(fr[k]) !== placeholders(en[k]));
    expect(mismatched).toEqual([]);
  });
});

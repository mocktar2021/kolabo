/* The basket's shape and its arithmetic, with no React and no React Native in
   it. That is not tidiness: mobile/tests runs under node (vitest.config.ts
   sets environment "node"), so anything importing react-native cannot be
   tested, and the grouping and the per-currency totals are exactly the part
   where a bug is silent — a basket that adds up to a number nobody agreed to
   looks like a working basket. The provider that holds this state lives in
   ./cart.tsx and imports everything below.

   THE BASKET LIVES ON THE CLIENT, AND THAT IS THE DESIGN. There is no cart on
   the server and backend/app/modules/campaigns/cart.py says why at length: a
   stored basket buys a table, an expiry policy (how long does an abandoned
   basket live, and who tells the creator their package is sitting in one?)
   and a stale-price problem (the package moved from 25k to 40k while the
   basket sat — which price is the order?), to solve a problem a client does
   not have. Holding a list of package ids is what a client is for. Mobile
   mirrors web/src/lib/cart.tsx exactly, down to the line shape; the only
   difference is where the copy that survives a restart is kept — the device
   keystore rather than localStorage, because that is where this app already
   keeps things (lib/auth.tsx, lib/language.ts).

   The amounts held on a line are FOR DISPLAY ONLY. They are what the profile
   showed when the line was added; the order is priced from the live package
   row at checkout, and if the two ever disagree the server is right. */

/* Mirrors MAX_CART_ITEMS in backend/app/modules/campaigns/cart.py. Enforced
   here as well as there so a full basket says so at the button rather than
   after a round trip that refuses the whole checkout. */
export const MAX_CART_ITEMS = 20;

/* The four identity fields a basket row carries about the creator it is
   addressed to — the same set the backend's CreatorIdentity has, so a name
   and a photo read the same here as on a proposal. */
export type CreatorSnapshot = {
  display_name: string | null;
  avatar_url: string | null;
  top_platform: string | null;
  top_follower_count: number | null;
};

/* An identity we never captured. Not "a creator with no name" — the
   difference matters on screen and CartScreen keeps it: this is a line
   written by a build that did not snapshot anybody, and the honest label for
   it is a neutral one rather than an assertion about a person nobody asked
   about. */
export const UNKNOWN_CREATOR: CreatorSnapshot = {
  display_name: null,
  avatar_url: null,
  top_platform: null,
  top_follower_count: null,
};

/* One line of the basket: something a brand could have ordered on its own, in
   either of the two forms POST /campaigns/orders takes.

   package_id set means the pack exactly as listed — title, price, deliverable
   and currency are all the creator's, which is the whole promise of a pack.
   package_id null means terms the buyer named, and then platform,
   deliverable_type, quantity, amount, currency and timeline_days are all
   required, because that is the complete offer.

   creator is A SNAPSHOT TAKEN WHEN THE LINE WAS ADDED rather than something
   the cart screen looks up, for the reason web states: no endpoint answers
   "who is this user id" and there should not be one, so the only place the
   identity is free is the profile screen the buyer was looking at when they
   tapped Add. Like the price on this row, it is for display only — the order
   is addressed by creator_user_id, which is the one field here the server
   reads. */
export type CartLine = {
  /* A row key for the list and for the remove button. Generated client-side
     and never sent: the server addresses items by their position in the
     array it is posted. */
  id: string;
  creator_user_id: string;
  creator: CreatorSnapshot;
  note: string | null;
  /* What the line is called on screen. A pack's title, or the deliverable for
     a custom line — which has no title, deliberately: the buyer said all of
     it by naming the terms, and a title box is one more thing to leave
     blank. */
  label: string;
  package_id: string | null;
  platform: string | null;
  deliverable_type: string | null;
  quantity: number | null;
  timeline_days: number | null;
  amount: number;
  currency: string;
};

/* What POST /campaigns/orders/checkout answers with (CartOrderOut in
   backend/app/modules/campaigns/schemas.py). creator_user_id is on each row
   because the buyer sent a flat list of items and got back a SHORTER list of
   orders, and without it the receipt cannot say which order is whose. */
export type CartCheckoutOrder = {
  creator_user_id: string;
  campaign_id: string;
  proposal_id: string;
  expires_at: string | null;
};

export type CartCheckoutResult = { orders: CartCheckoutOrder[] };

export type CurrencyTotal = { currency: string; amount: number };

export type CartGroup = {
  creator_user_id: string;
  creator: CreatorSnapshot;
  lines: CartLine[];
  subtotals: CurrencyTotal[];
};

/* MONEY, PER CURRENCY, NEVER ACROSS THEM.

   The platform sets no exchange rate and does not want to: an order carries
   one escrow and an escrow carries one currency, so adding 25 000 XOF to 400
   GHS would invent a number nobody agreed to and that no order could ever be
   for. Each currency gets its own row instead, in the per-creator subtotal
   and in the grand total alike. Sorted by currency code so two identical
   baskets never render their rows in a different order.

   This is the function mobile/tests/cartTotals.test.ts exists for. */
export function totalsByCurrency(entries: { amount: number; currency: string }[]): CurrencyTotal[] {
  const totals = new Map<string, number>();
  for (const e of entries) totals.set(e.currency, (totals.get(e.currency) ?? 0) + e.amount);
  return [...totals.entries()]
    .map(([currency, amount]) => ({ currency, amount }))
    .sort((a, b) => a.currency.localeCompare(b.currency));
}

/* One pile per creator, in the order the basket was built.

   This grouping is not decoration: it is exactly what the endpoint does with
   the items. cart.py's _group_by_creator keys on creator_user_id and keeps
   insertion order, and a checkout FANS OUT into one direct order per creator
   — each accepted or declined on its own, on its own clock, for its own money
   — so three packs from one person are one order with three deliverables,
   while two people are two independent orders. Showing the basket any other
   way would promise a shape the receipt then contradicts. */
export function groupByCreator(lines: CartLine[]): CartGroup[] {
  const groups: CartGroup[] = [];
  for (const line of lines) {
    const found = groups.find((g) => g.creator_user_id === line.creator_user_id);
    if (found) found.lines.push(line);
    else
      groups.push({
        creator_user_id: line.creator_user_id,
        creator: line.creator,
        lines: [line],
        subtotals: [],
      });
  }
  /* Filled after every line has landed rather than as each one arrives: a
     subtotal of a half-built pile is a number that was briefly wrong, and
     nothing here is hot enough to earn that. */
  for (const g of groups) g.subtotals = totalsByCurrency(g.lines);
  return groups;
}

/* One line as the endpoint takes it: a package_id, or the whole custom offer.
   Exactly one of the two forms — a body carrying both is not a preference to
   resolve, it is two different orders in one envelope, and OrderIn answers
   400 to it. The note rides on either form and is omitted when empty, like
   every other optional note in the app. */
export function checkoutItem(line: CartLine): Record<string, unknown> {
  const note = line.note ? { note: line.note } : {};
  if (line.package_id) return { package_id: line.package_id, ...note };
  return {
    creator_user_id: line.creator_user_id,
    platform: line.platform,
    deliverable_type: line.deliverable_type,
    quantity: line.quantity,
    rate_amount: line.amount,
    currency: line.currency,
    timeline_days: line.timeline_days,
    ...note,
  };
}

export function newLineId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

/* One stored row, made safe to render and safe to ADD UP.

   The keystore keeps a basket until somebody checks out or clears it; there
   is no migration to run and no server copy to fix, so a row written by an
   older build has to be survivable. A row missing either of the two fields
   that identify it — its own id, and the creator the order is addressed to —
   is dropped, because neither can be invented. A row missing only the
   identity gets a neutral one and renders under a neutral label.

   THE TYPES OF amount AND currency ARE CHECKED, which is the one place this
   is stricter than web's readStored. Everything else here is cosmetic; those
   two are arithmetic. A hand-edited or older row carrying "25000" as a STRING
   would make totalsByCurrency concatenate instead of add — "0250004000" where
   a total belongs — and it would look like a total. Dropping the row loses
   one line the buyer can re-add; keeping it shows them a price.

   Every other field is left exactly as stored. This normalises the shape and
   never the terms: a price rewritten on the way out of storage would be the
   cart quietly changing what somebody put in it. */
export function normaliseLine(raw: unknown): CartLine | null {
  if (!raw || typeof raw !== "object") return null;
  const line = raw as Partial<CartLine>;
  if (typeof line.id !== "string" || typeof line.creator_user_id !== "string") return null;
  if (typeof line.amount !== "number" || !Number.isFinite(line.amount)) return null;
  if (typeof line.currency !== "string" || line.currency === "") return null;
  const stored = (line.creator && typeof line.creator === "object" ? line.creator : null) as
    | Partial<CreatorSnapshot>
    | null;
  return {
    ...(line as CartLine),
    creator: stored
      ? {
          /* Field by field rather than a spread, so a half-written identity
             (an older shape, a hand-edited entry) cannot leave an undefined
             where every reader expects null. */
          display_name: stored.display_name ?? null,
          avatar_url: stored.avatar_url ?? null,
          top_platform: stored.top_platform ?? null,
          top_follower_count: stored.top_follower_count ?? null,
        }
      : UNKNOWN_CREATOR,
  };
}

/* The stored basket, as the provider reads it back at boot.

   A basket that will not parse was hand-edited or written by an older build.
   Dropped rather than allowed to throw on launch: the worst case is an empty
   cart, which costs a few taps to rebuild, and the alternative is a screen
   with no way out of it. Capped on the way in as well, because the ceiling is
   the endpoint's and a stored array longer than it could only ever be
   refused. */
export function readLines(raw: string | null): CartLine[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map(normaliseLine)
      .filter((line): line is CartLine => line !== null)
      .slice(0, MAX_CART_ITEMS);
  } catch {
    return [];
  }
}

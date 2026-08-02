import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { CreatorIdentity } from "./types";

/* THE BASKET LIVES ON THE CLIENT, AND THAT IS THE DESIGN.

   There is no cart on the server, and backend/app/modules/campaigns/cart.py
   says why: a stored basket buys a table, an expiry policy (how long does an
   abandoned basket live, and who tells the creator their package is sitting
   in one?) and a stale-price problem (the package moved from 25k to 40k while
   the basket sat — which price is the order?). It would buy all of that to
   solve a problem the client does not have. Holding a list of package ids is
   what a client is for, and reading prices off the live rows at checkout
   means there is never a stale one to reconcile.

   So the client owns the cart outright. React state is the truth while the
   tab is open; localStorage is the copy that survives a refresh, because a
   brand who built a six-line basket and reloaded should not have to build it
   again. Nothing here is ever sent anywhere except as one
   POST /campaigns/orders/checkout body.

   The amounts held on a line are FOR DISPLAY ONLY. They are what the profile
   showed when the line was added; the order is priced from the live package
   row at checkout, and if the two ever disagree the server is right. */

const KEY = "kolabo_cart";

/* Mirrors MAX_CART_ITEMS in backend/app/modules/campaigns/cart.py. Enforced
   here as well as there so a full basket says so at the button rather than
   after a round trip that refuses the whole checkout. */
export const MAX_CART_ITEMS = 20;

/* An identity we never captured. Not "a creator with no name" — the
   difference matters on screen and CartPage keeps it: this is a line written
   by a build that did not snapshot anybody, and the honest label for it is a
   neutral one rather than CreatorChip's "Créateur sans nom", which asserts a
   fact about a person we never asked about. */
export const UNKNOWN_CREATOR: CreatorIdentity = {
  display_name: null,
  avatar_url: null,
  top_platform: null,
  top_follower_count: null
};

/* One line of the basket: something a brand could have ordered on its own, in
   either of the two forms the orders endpoint takes.

   package_id set means the package exactly as listed — title, price,
   deliverable and currency are all the creator's, which is the whole promise
   of a package. package_id null means terms the buyer negotiated, and then
   platform, deliverable_type, quantity, amount, currency and timeline_days
   are all required, because that is the complete offer.

   creator carries the four identity fields CreatorChip renders, and it is A
   SNAPSHOT TAKEN WHEN THE LINE WAS ADDED rather than something the cart page
   looks up. Three reasons, in the order they matter:

     1. THERE IS NOTHING TO LOOK IT UP WITH. No endpoint answers "who is this
        user id", and there should not be one — that is an enumeration API
        over everybody on the platform, handed to whoever holds any token.
        What exists is the public profile page, keyed by user id, which is a
        whole marketplace aggregate (packages, portfolio, reviews, social
        accounts) to extract a name and a photo from.

     2. IT WOULD BE ONE REQUEST PER GROUP, ON A SCREEN THAT ALREADY HAS THE
        ANSWER. A four-creator basket is four aggregate fetches before the
        page can draw a heading, and every one of them can fail on its own,
        leaving the buyer looking at a basket that is half anonymous. The
        identity was on screen on the profile page at the exact moment the
        buyer clicked "ajouter" — capturing it there costs nothing.

     3. IT IS WHAT THE LINE ALREADY DOES WITH THE TERMS. The label, the
        amount, the currency and the timeline on this row are all snapshots of
        what the profile showed; the identity being live while the price is
        frozen would be the odd arrangement, not this one. And like those, the
        snapshot is FOR DISPLAY ONLY — the order is addressed by
        creator_user_id, which is the one field on this row the server reads. */
export type CartLine = {
  /* A row key for React and for the remove button. Generated client-side and
     never sent: the server addresses items by their position in the array. */
  id: string;
  creator_user_id: string;
  creator: CreatorIdentity;
  note: string | null;
  /* What the line is called on screen. A package's title, or the deliverable
     for a negotiated line — which has no title, deliberately: the buyer said
     all of it by choosing the terms, and a title box is one more thing to
     leave blank. */
  label: string;
  package_id: string | null;
  platform: string | null;
  deliverable_type: string | null;
  quantity: number | null;
  timeline_days: number | null;
  amount: number;
  currency: string;
};

/* What POST /campaigns/orders/checkout answers with. It lives here rather
   than in types.ts because the cart is its only reader: a flat list of items
   goes up and a shorter list of orders comes back, and creator_user_id on
   each row is what lets the basket say which order is whose. */
export type CartCheckoutOrder = {
  creator_user_id: string;
  campaign_id: string;
  proposal_id: string;
  expires_at: string | null;
};

export type CartCheckoutResult = { orders: CartCheckoutOrder[] };

/* One line as the endpoint takes it: a package_id, or the whole custom offer.
   Exactly one of the two forms — a body carrying both is not a preference to
   resolve, it is two different orders in one envelope, and the server answers
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
    ...note
  };
}

function newLineId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

/* One stored row, made safe to render.

   THE CASE THIS EXISTS FOR IS ALREADY IN PEOPLE'S BROWSERS. Baskets written
   before the identity snapshot have no `creator` key at all, and localStorage
   keeps them until somebody checks out or clears it — there is no migration
   to run and no server copy to fix. CreatorChip reads four fields off that
   object, so an untouched legacy line is a TypeError on the cart page and on
   the checkout receipt: a buyer's whole basket replaced by a white screen,
   with the remove button that would have fixed it on the other side of the
   crash.

   So the shape is repaired on read rather than trusted. A row missing the two
   fields that identify it (its own id, and the creator the order is addressed
   to) is dropped, because neither can be invented; a row missing only the
   identity gets an empty one and renders under a neutral label. Every other
   field is left exactly as stored — this normalises the shape and never the
   terms, and a price rewritten on the way out of storage would be the cart
   quietly changing what somebody put in it. */
function normaliseLine(raw: unknown): CartLine | null {
  if (!raw || typeof raw !== "object") return null;
  const line = raw as Partial<CartLine>;
  if (typeof line.id !== "string" || typeof line.creator_user_id !== "string") return null;
  const stored = (line.creator && typeof line.creator === "object" ? line.creator : null) as Partial<CreatorIdentity> | null;
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
          top_follower_count: stored.top_follower_count ?? null
        }
      : UNKNOWN_CREATOR
  };
}

function readStored(): CartLine[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map(normaliseLine)
      .filter((line): line is CartLine => line !== null);
  } catch {
    /* A basket that will not parse was hand-edited or written by an older
       build. Dropped rather than allowed to crash the app on load: the worst
       case is an empty cart, which costs a few clicks to rebuild, and the
       alternative is a white screen with no way out. */
    return [];
  }
}

type CartValue = {
  lines: CartLine[];
  count: number;
  /* False when the basket is already full. The caller has to say so — a line
     that silently fails to appear reads as a broken button. */
  add: (line: Omit<CartLine, "id">) => boolean;
  remove: (id: string) => void;
  clear: () => void;
};

const CartContext = createContext<CartValue | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  // Read once, synchronously, rather than in an effect: a cart that renders
  // empty for a frame and then fills in makes the nav badge flicker on every
  // page load.
  const [lines, setLines] = useState<CartLine[]>(readStored);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(lines));
    } catch {
      // Storage full or blocked (private browsing). The cart still works for
      // this tab; only surviving a refresh is lost, and losing the basket is
      // not worth breaking the page over.
    }
  }, [lines]);

  const value = useMemo<CartValue>(
    () => ({
      lines,
      count: lines.length,
      add: (line) => {
        if (lines.length >= MAX_CART_ITEMS) return false;
        setLines((prev) => (prev.length >= MAX_CART_ITEMS ? prev : [...prev, { ...line, id: newLineId() }]));
        return true;
      },
      remove: (id) => setLines((prev) => prev.filter((l) => l.id !== id)),
      clear: () => setLines([])
    }),
    [lines]
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within CartProvider");
  return ctx;
}

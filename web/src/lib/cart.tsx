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

/* One line of the basket: something a brand could have ordered on its own, in
   either of the two forms the orders endpoint takes.

   package_id set means the package exactly as listed — title, price,
   deliverable and currency are all the creator's, which is the whole promise
   of a package. package_id null means terms the buyer negotiated, and then
   platform, deliverable_type, quantity, amount, currency and timeline_days
   are all required, because that is the complete offer.

   creator carries the four identity fields CreatorChip renders. The cart page
   groups by creator and has no way to look anybody up — there is no endpoint
   for "who is this user id" and there should not be one — so the identity is
   captured on the profile page where it is already on screen. */
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

function readStored(): CartLine[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as CartLine[]) : [];
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

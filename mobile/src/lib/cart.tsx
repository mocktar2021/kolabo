import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import * as SecureStore from "expo-secure-store";
import { MAX_CART_ITEMS, newLineId, readLines, type CartLine } from "./cartTotals";

/* The basket, held in React state and copied into the device keystore so it
   survives the app being killed. The shape, the ceiling and the arithmetic
   all live in ./cartTotals — this module is only the holder.

   THE KEYSTORE, NOT A SECOND STORAGE MECHANISM. lib/auth.tsx keeps the token
   there and lib/language.ts keeps the language override there; adding
   AsyncStorage for this one list would mean two stores to reason about, two
   things to clear on logout, and a new dependency in a bundle that currently
   needs none. A basket is not a secret, so the keystore is not buying
   confidentiality here — it is buying the app having ONE answer to "where do
   we put small things that outlive a process".

   TWO CONSEQUENCES OF THAT CHOICE, both stated rather than discovered:

     1. THE READ IS ASYNCHRONOUS, where web's localStorage read is not. So
        this starts empty and fills in a moment later, and nothing may be
        WRITTEN before the read has answered — the first render would
        otherwise persist [] over the stored basket and lose it. `hydrated`
        is that gate, exactly the shape lib/auth.tsx uses for the token.

     2. expo-secure-store warns above 2048 bytes per value, and a full
        twenty-line basket with its identity snapshots can pass that. The
        write is best-effort and already inside a catch, so the failure mode
        is the basket not surviving a restart — the same thing web accepts
        when localStorage is full or blocked in private browsing. It is never
        worth breaking the screen over: nothing here has been sent anywhere,
        and re-adding a line is a tap. */
const KEY = "kolabo.cart";

type CartValue = {
  lines: CartLine[];
  count: number;
  /* True while the keystore read is still in flight. The badge and the cart
     screen use it to keep quiet rather than claim an empty basket for the
     fraction of a second before the real one lands — "your cart is empty" is
     a statement, and it should not be made before anybody has looked. */
  loading: boolean;
  /* False when the basket is already full. The caller has to say so — a line
     that silently fails to appear reads as a broken button. */
  add: (line: Omit<CartLine, "id">) => boolean;
  remove: (id: string) => void;
  clear: () => void;
};

const CartContext = createContext<CartValue | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    let active = true;
    void SecureStore.getItemAsync(KEY)
      .then((raw) => {
        if (active) setLines(readLines(raw));
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) setHydrated(true);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    /* Nothing is written until the stored basket has been read back, or the
       very first render would overwrite it with the empty array this state
       starts on. */
    if (!hydrated) return;
    void SecureStore.setItemAsync(KEY, JSON.stringify(lines)).catch(() => undefined);
  }, [lines, hydrated]);

  const value = useMemo<CartValue>(
    () => ({
      lines,
      count: lines.length,
      loading: !hydrated,
      add: (line) => {
        if (lines.length >= MAX_CART_ITEMS) return false;
        setLines((prev) =>
          prev.length >= MAX_CART_ITEMS ? prev : [...prev, { ...line, id: newLineId() }]
        );
        return true;
      },
      remove: (id) => setLines((prev) => prev.filter((l) => l.id !== id)),
      clear: () => setLines([]),
    }),
    [lines, hydrated]
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within CartProvider");
  return ctx;
}

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";
import { useAuth } from "./auth";

/* WHO IS SIGNED IN, fetched once and shared.

   Mirror of MeOut in backend/app/modules/auth/schemas.py. It lives here rather
   than in types.ts for the reason CartCheckoutOrder lives in cart.tsx: this
   module is its only reader, and everything else reads the context below.

   display_name and avatar_url are resolved server-side from the creator
   profile, else from the business profile's company name WITH A NULL AVATAR
   (a business has a company name and no avatar anywhere in this system), else
   both null. Null is a real answer for somebody who has not written a profile
   yet and it stays null — the users table's only human-readable column is the
   phone number, and a phone number is never put in a display slot.

   The phone IS on this payload and is deliberately not rendered in the nav.
   Here the reader is the subject, so /auth/me is the one place it is right to
   return it — the account settings screen needs to show you which number you
   log in with. A dropdown under an avatar does not. */
export type Me = {
  id: string;
  phone: string;
  role: string;
  country_code: string;
  is_verified: boolean;
  created_at: string;
  display_name: string | null;
  avatar_url: string | null;
};

type MeValue = {
  me: Me | null;
  /* True only while the first request for a given token is in flight. The nav
     uses it to avoid flashing a fallback name for a frame before the real one
     lands. */
  loading: boolean;
};

/* A default value rather than a null context, which is the one difference
   from useCart/useAuth and it is deliberate: those two throw outside their
   provider because a cart or a session is load-bearing, whereas a missing
   name decorates a button. A component rendered in a test or a story without
   the provider should draw the gradient, not crash the page. */
const MeContext = createContext<MeValue>({ me: null, loading: false });

/* ONE REQUEST PER SESSION, NOT ONE PER PAGE, and that is the whole point of
   this file existing instead of a useEffect in Layout.

   Layout mounts on every screen of the app and already spends two requests
   per navigation on the message and dispute badges (and a third on the
   notification count). Those three are refetched on purpose — they are
   counts, and a stale count is the failure. A name and an avatar are not:
   they change when somebody edits their profile, which is a thing they do on
   a screen that reloads the profile anyway.

   So the fetch is keyed on the token and nothing else. Signing out clears it,
   signing in as somebody else refetches it, and navigating does neither.

   Sits above the router in main.tsx so the value survives navigation; a
   provider inside a route element would remount with the route and turn one
   request per session back into one per page. */
export function MeProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) {
      // Signed out, or signed out from another tab. The previous person's
      // name and face must not survive into the next session.
      setMe(null);
      setLoading(false);
      return;
    }
    let live = true;
    setLoading(true);
    api<Me>("/auth/me", { token })
      .then((res) => { if (live) setMe(res); })
      /* Silent. This decorates a 28 px button: an expired token is already
         going to be reported by whatever the page itself was fetching, and a
         second error banner about an avatar would only bury it. */
      .catch(() => { if (live) setMe(null); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [token]);

  const value = useMemo<MeValue>(() => ({ me, loading }), [me, loading]);
  return <MeContext.Provider value={value}>{children}</MeContext.Provider>;
}

export function useMe(): MeValue {
  return useContext(MeContext);
}

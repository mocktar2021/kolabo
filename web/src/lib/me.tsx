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
   yet and it stays null — the users table's only human-readable columns are
   the email address and the optional phone number, and neither is ever put in
   a display slot.

   BOTH ARE ON THIS PAYLOAD and neither is rendered in the nav. Here the
   reader is the subject, so /auth/me is the one place it is right to return
   them — the account settings screen needs to show you which address you log
   in with, and which number your payouts go to. A dropdown under an avatar
   needs neither.

   `phone` IS NULLABLE and the type says so, because users.phone is nullable
   and nothing collects it at signup any more. An account that has never added
   one answers null, and a reader that assumes a string prints "null" at a
   user. */
export type Me = {
  id: string;
  email: string;
  phone: string | null;
  role: string;
  country_code: string;
  is_verified: boolean;
  /* Whether this account may reach the admin surface.

     NOT DERIVABLE FROM `role`, which is why it has to be transmitted: admin
     is a flag beside a role rather than a fourth role, so an admin is also an
     ordinary marketplace user and getStoredRole answers "influencer |
     business | agency" for them like anybody else. Until this field existed
     the frontend could not ask the question at all, which is why
     /admin/disputes was declared with no guard on it. App.tsx's AdminOnly is
     the reader. */
  is_admin: boolean;
  created_at: string;
  display_name: string | null;
  avatar_url: string | null;
};

type MeValue = {
  me: Me | null;
  /* True only while the first request for a given token is in flight. The nav
     uses it to avoid flashing a fallback name for a frame before the real one
     lands.

     NOT A SUFFICIENT "still loading" TEST ON ITS OWN — it starts false and
     only becomes true once the effect below runs, so the very first render of
     any consumer sees loading:false with me:null. A guard that keys on it
     alone will fall through on that frame; see AdminOnly in App.tsx, which
     waits on `me` instead. */
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

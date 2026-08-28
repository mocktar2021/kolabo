import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

/* Minimal auth state: the JWT is kept in localStorage so a refresh keeps the
   session. The user id is read from the token subject (the backend keys
   profiles by user id). */
const KEY = "kolabo_token";
/* The account role as the API last reported it. Registration writes a first
   guess; every login and verify-otp response overwrites it with the stored
   truth, so the role survives logout/login instead of falling back to a
   default. */
const ROLE_KEY = "kolabo_role";

export type Role = "influencer" | "business" | "agency";

/* Every read and write of localStorage in this file goes through these two.

   Not defensiveness for its own sake: the getter THROWS rather than returning
   null in Safari private mode and in any browser set to block site data, and
   an exception thrown while computing initial state takes the whole app down
   to a white page. A session that cannot be persisted is a session that ends
   when the tab does, which is a bad afternoon; a white page is a bug report. */
function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStored(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* Storage is full, or blocked. The in-memory session below still works
       for this tab; it just will not survive a reload. */
  }
}

/* Agencies buy creator services the same way businesses do, so they get the
   business UX (business profile form, business dashboard, business routing)
   until agency specific tooling exists. Every role branch in the app goes
   through this helper instead of comparing against "business" directly. */
export function isBusinessLike(role: string | null | undefined): boolean {
  return role === "business" || role === "agency";
}

export function getStoredRole(): Role | null {
  const r = readStored(ROLE_KEY);
  return r === "influencer" || r === "business" || r === "agency" ? r : null;
}

function decodeUserId(token: string | null): string | null {
  if (!token) return null;
  try {
    const part = token.split(".")[1];
    const json = JSON.parse(atob(part.replace(/-/g, "+").replace(/_/g, "/")));
    return typeof json.sub === "string" ? json.sub : null;
  } catch {
    return null;
  }
}

type AuthValue = {
  token: string | null;
  userId: string | null;
  isAuthenticated: boolean;
  login: (token: string, role?: string) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthValue | null>(null);

/* THE TOKEN IS READ ON THE FIRST RENDER, NOT IN AN EFFECT, and that sentence
   is the whole reason this comment exists.

   It used to be hydrated in a useEffect: state started null, so the first
   render of every screen said "signed out". Every guarded page answers that
   with `<Navigate to="/login" replace />` — and Navigate does its work in an
   effect of its own, deep in the tree. React runs a child's effects BEFORE
   its parents', so the redirect fired a tick before the hydration that would
   have prevented it, on a page that was by then already /login. `replace`
   meant there was not even a history entry to go back to.

   The symptom was not subtle and was not confined to one screen: refreshing
   ANY page logged you out, and so did coming back from the payment gateway,
   which is a full page load onto /checkout/return by construction. It also
   explains stray 401s in the backend log — a page's first fetch went out with
   no Authorization header while the effect was still pending.

   localStorage is synchronous and this is a Vite SPA with no server render,
   so the lazy initialiser is the entire fix: render one is already signed in
   and no guard ever sees a false negative. Anything that moves this read back
   into an effect brings the bug back with it, which is what auth.test.tsx is
   there to catch. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => readStored(KEY));

  const value = useMemo<AuthValue>(
    () => ({
      token,
      userId: decodeUserId(token),
      isAuthenticated: !!token,
      login: (t: string, role?: string) => {
        writeStored(KEY, t);
        // The role rides along with the token; persisting it here is what
        // keeps an agency an agency across sessions.
        if (role) writeStored(ROLE_KEY, role);
        setToken(t);
      },
      logout: () => {
        writeStored(KEY, null);
        setToken(null);
      }
    }),
    [token]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

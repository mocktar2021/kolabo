import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import * as SecureStore from "expo-secure-store";
import type { Role } from "./api";

/* Auth state, the mobile twin of web/src/lib/auth.tsx. The web app keeps the
   JWT in localStorage; here it lives in the device keystore via expo-secure-
   store, which is the right home for a bearer token on a phone. Because that
   store is async, the provider exposes `loading` while it restores on launch —
   the web version could read localStorage synchronously and had no such state.

   The role is persisted alongside the token for the same reason web does it:
   every login/verify response carries the backend's stored role, and keeping
   it is what lets an agency come back as an agency after a logout rather than
   defaulting to a creator. */
const TOKEN_KEY = "kolaboToken";
const ROLE_KEY = "kolaboRole";

/* THE CLOSED SET OF ROLES, in one place. RegisterScreen has always kept a
   local copy and the Google flow needs the identical set: a Google address
   with no account behind it is asked the same two questions the register form
   asks, and the answer goes to the same ROLES check in
   backend/app/modules/auth/schemas.py.

   Two copies of a closed set is how a fourth role reaches one screen and not
   the other, and the screen that missed it then refuses a value the server
   accepts. Kept here, beside the type, exactly as web/src/lib/auth.tsx keeps
   its own. */
export const ROLES: Role[] = ["influencer", "business", "agency"];

/* Agencies buy creator services the way businesses do, so they get the
   business experience until agency-specific tooling exists. Every role branch
   in the app goes through this helper rather than comparing to "business". */
export function isBusinessLike(role: string | null | undefined): boolean {
  return role === "business" || role === "agency";
}

/* A minimal, dependency-free base64url decoder for the JWT payload. Hermes has
   gained a global atob, but not on every runtime this bundle might touch, so
   the token subject is decoded here rather than trusting one to exist. The
   subject is a UUID (ASCII), so a Latin1 decode is exact for it. */
const B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
function base64UrlDecode(input: string): string {
  let str = input.replace(/-/g, "+").replace(/_/g, "/");
  while (str.length % 4) str += "=";
  let output = "";
  let bc = 0;
  let bs = 0;
  for (let i = 0; i < str.length; i++) {
    const ch = str.charAt(i);
    if (ch === "=") break;
    const idx = B64.indexOf(ch);
    if (idx === -1) continue;
    bs = bc % 4 ? bs * 64 + idx : idx;
    if (bc++ % 4) output += String.fromCharCode(255 & (bs >> ((-2 * bc) & 6)));
  }
  return output;
}

function decodeUserId(token: string | null): string | null {
  if (!token) return null;
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const obj = JSON.parse(base64UrlDecode(payload)) as { sub?: unknown };
    return typeof obj.sub === "string" ? obj.sub : null;
  } catch {
    return null;
  }
}

type AuthValue = {
  loading: boolean;
  token: string | null;
  role: Role | null;
  userId: string | null;
  isAuthenticated: boolean;
  login: (token: string, role?: Role) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<Role | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [storedToken, storedRole] = await Promise.all([
          SecureStore.getItemAsync(TOKEN_KEY),
          SecureStore.getItemAsync(ROLE_KEY),
        ]);
        if (!active) return;
        setToken(storedToken);
        if (storedRole === "influencer" || storedRole === "business" || storedRole === "agency") {
          setRole(storedRole);
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      loading,
      token,
      role,
      userId: decodeUserId(token),
      isAuthenticated: !!token,
      login: async (t: string, r?: Role) => {
        await SecureStore.setItemAsync(TOKEN_KEY, t);
        if (r) await SecureStore.setItemAsync(ROLE_KEY, r);
        setToken(t);
        if (r) setRole(r);
      },
      logout: async () => {
        await Promise.all([
          SecureStore.deleteItemAsync(TOKEN_KEY),
          SecureStore.deleteItemAsync(ROLE_KEY),
        ]);
        setToken(null);
        setRole(null);
      },
    }),
    [loading, token, role]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

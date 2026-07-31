import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

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

/* Agencies buy creator services the same way businesses do, so they get the
   business UX (business profile form, business dashboard, business routing)
   until agency specific tooling exists. Every role branch in the app goes
   through this helper instead of comparing against "business" directly. */
export function isBusinessLike(role: string | null | undefined): boolean {
  return role === "business" || role === "agency";
}

export function getStoredRole(): Role | null {
  const r = localStorage.getItem(ROLE_KEY);
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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    setToken(localStorage.getItem(KEY));
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      token,
      userId: decodeUserId(token),
      isAuthenticated: !!token,
      login: (t: string, role?: string) => {
        localStorage.setItem(KEY, t);
        // The role rides along with the token; persisting it here is what
        // keeps an agency an agency across sessions.
        if (role) localStorage.setItem(ROLE_KEY, role);
        setToken(t);
      },
      logout: () => {
        localStorage.removeItem(KEY);
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

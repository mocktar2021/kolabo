import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

/* Minimal auth state: the JWT is kept in localStorage so a refresh keeps the
   session. The user id is read from the token subject (the backend keys
   profiles by user id). */
const KEY = "kolabo_token";

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
  login: (token: string) => void;
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
      login: (t: string) => {
        localStorage.setItem(KEY, t);
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

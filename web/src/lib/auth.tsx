import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

/* Minimal auth state: the JWT is kept in localStorage so a refresh keeps the
   session. Real profile loading arrives with the profiles screen. */
const KEY = "kolabo_token";

type AuthValue = {
  token: string | null;
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

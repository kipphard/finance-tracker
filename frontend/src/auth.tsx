import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { apiGet, apiPost, getToken, setToken } from "./api/client";
import type { TokenResponse, UserOut } from "./api/types";

interface AuthContextValue {
  user: UserOut | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  startDemo: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>(null!);

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);

  const login = async (email: string, password: string) => {
    const resp = await apiPost<TokenResponse>("/auth/login", { email, password });
    setToken(resp.access_token);
    setUser(resp.user);
  };

  // Public live demo: spins up an isolated, seeded sandbox and signs in. No body needed.
  const startDemo = async () => {
    const resp = await apiPost<TokenResponse>("/auth/demo");
    setToken(resp.access_token);
    setUser(resp.user);
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    // drop ?demo=1 so a logout doesn't immediately re-enter the demo
    if (window.location.search.includes("demo=1")) {
      window.history.replaceState({}, "", window.location.pathname);
    }
  };

  useEffect(() => {
    const onUnauthorized = () => setUser(null);
    window.addEventListener("ft-unauthorized", onUnauthorized);

    const autoDemo = new URLSearchParams(window.location.search).get("demo") === "1";
    if (getToken()) {
      apiGet<UserOut>("/auth/me")
        .then(setUser)
        .catch(() => setToken(null))
        .finally(() => setLoading(false));
    } else if (autoDemo) {
      startDemo().catch(() => undefined).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
    return () => window.removeEventListener("ft-unauthorized", onUnauthorized);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, startDemo, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

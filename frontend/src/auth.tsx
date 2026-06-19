import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { apiGet, apiPost, getToken, setToken } from "./api/client";
import type { TokenResponse, UserOut } from "./api/types";

interface AuthContextValue {
  user: UserOut | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>(null!);

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const onUnauthorized = () => setUser(null);
    window.addEventListener("ft-unauthorized", onUnauthorized);

    if (getToken()) {
      apiGet<UserOut>("/auth/me")
        .then(setUser)
        .catch(() => setToken(null))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
    return () => window.removeEventListener("ft-unauthorized", onUnauthorized);
  }, []);

  const authenticate = async (path: string, email: string, password: string) => {
    const resp = await apiPost<TokenResponse>(path, { email, password });
    setToken(resp.access_token);
    setUser(resp.user);
  };

  const login = (email: string, password: string) =>
    authenticate("/auth/login", email, password);
  const register = (email: string, password: string) =>
    authenticate("/auth/register", email, password);
  const logout = () => {
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

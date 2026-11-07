import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { api, hasSession, post, setTokens } from "./api";
import { User } from "./types";

interface AuthState {
  user: User | null;
  ready: boolean;
  login: (login: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  const reload = useCallback(async () => {
    if (!hasSession()) {
      setUser(null);
      return;
    }
    try {
      setUser(await api<User>("/api/auth/me/"));
    } catch {
      setTokens(null, null);
      setUser(null);
    }
  }, []);

  useEffect(() => {
    reload().finally(() => setReady(true));
  }, [reload]);

  const login = async (loginName: string, password: string) => {
    const tokens = await post<{ access: string; refresh: string }>("/api/auth/login/", {
      login: loginName,
      password,
    });
    setTokens(tokens.access, tokens.refresh);
    await reload();
  };

  const logout = async () => {
    let refresh: string | null = null;
    try {
      refresh = sessionStorage.getItem("chama.refresh");
    } catch {
      refresh = null;
    }
    if (refresh) await post("/api/auth/logout/", { refresh }).catch(() => undefined);
    setTokens(null, null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, ready, login, logout, reload }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (!state) throw new Error("useAuth must be used inside AuthProvider");
  return state;
}

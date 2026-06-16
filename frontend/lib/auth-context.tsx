"use client";

import { createContext, use, useState, useEffect, useMemo, ReactNode, useCallback } from "react";
import { setAuthTokens, clearAuthTokens, getStoredToken } from "@/lib/auth-tokens";
import { ApiRequestError, getCurrentUser, type CurrentUser } from "@/lib/api";

interface AuthContextType {
  token: string | null;
  user: CurrentUser | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (token: string, expiresAt: string) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  // Start with no token and loading=true ("still checking"). localStorage can't be
  // read during the server render, so we defer the auth decision to the effect below.
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    clearAuthTokens();
    setToken(null);
    setUser(null);
  }, []);

  const fetchUser = useCallback(
    async (authToken: string) => {
      try {
        const userData = await getCurrentUser(authToken);
        setUser(userData);
      } catch (error) {
        if (error instanceof ApiRequestError && error.status === 401) {
          logout();
        } else {
          console.error("Failed to fetch user:", error);
        }
      } finally {
        setLoading(false);
      }
    },
    [logout],
  );

  const login = useCallback(
    (newToken: string, expiresAt: string) => {
      setAuthTokens(newToken, expiresAt);
      setToken(newToken);
      setLoading(true);
      // Fetch directly from the handler that starts the flow rather than via a
      // token-watching effect, so we don't chain effects (extra renders).
      fetchUser(newToken);
    },
    [fetchUser],
  );

  // Runs once, in the browser only (effects never run on the server), where
  // localStorage exists. Read the stored token and, if present, load the user.
  useEffect(() => {
    const stored = getStoredToken();
    if (stored) {
      setToken(stored);
      fetchUser(stored);
    } else {
      setLoading(false);
    }
  }, [fetchUser]);

  const refreshUser = useCallback(async () => {
    if (token) {
      await fetchUser(token);
    }
  }, [token, fetchUser]);

  // Memoize so consumers don't re-render on every provider render (new value identity).
  const value = useMemo(
    () => ({
      token,
      user,
      isAuthenticated: !!token,
      loading,
      login,
      logout,
      refreshUser,
    }),
    [token, user, loading, login, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = use(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

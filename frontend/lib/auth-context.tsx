"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
  useCallback,
} from "react";

const TOKEN_KEY = "access_token";
const EXPIRES_KEY = "expires_at";

export function setAuthTokens(token: string, expiresAt: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(EXPIRES_KEY, expiresAt);
}

export function clearAuthTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EXPIRES_KEY);
}

interface User {
  id?: string;
  username?: string;
  name?: string;
  email?: string;
  avatar?: string;
  plan?: string;
}

interface AuthContextType {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (token: string, expiresAt: string) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function getInitialToken(): string | null {
  if (typeof window === "undefined") return null;

  const storedToken = localStorage.getItem(TOKEN_KEY);
  const expiresAt = localStorage.getItem(EXPIRES_KEY);

  if (storedToken && expiresAt) {
    const isExpired = new Date(expiresAt) < new Date();
    if (!isExpired) {
      return storedToken;
    }
    clearAuthTokens();
  }
  return null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(getInitialToken);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const login = (newToken: string, expiresAt: string) => {
    setAuthTokens(newToken, expiresAt);
    setToken(newToken);
  };

  const logout = useCallback(() => {
    clearAuthTokens();
    setToken(null);
    setUser(null);
  }, []);

  const fetchUser = useCallback(
    async (authToken: string) => {
      try {
        const response = await fetch("/api/v1/user/me", {
          headers: {
            Authorization: `Bearer ${authToken}`,
            Accept: "application/json",
          },
        });

        if (response.ok) {
          const userData = await response.json();
          setUser(userData);
        } else if (response.status === 401) {
          logout();
        }
      } catch (error) {
        console.error("Failed to fetch user:", error);
      } finally {
        setLoading(false);
      }
    },
    [logout],
  );

  useEffect(() => {
    if (token) {
      fetchUser(token);
    } else {
      setLoading(false);
      setUser(null);
    }
  }, [token, fetchUser]);

  const refreshUser = async () => {
    if (token) {
      await fetchUser(token);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        isAuthenticated: !!token,
        loading,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

'use client';

import { createContext, useContext, useState, ReactNode } from 'react';

interface AuthContextType {
  token: string | null;
  isAuthenticated: boolean;
  login: (token: string, expiresAt: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function getInitialToken(): string | null {
  if (typeof window === 'undefined') return null;

  const storedToken = localStorage.getItem('access_token');
  const expiresAt = localStorage.getItem('expires_at');

  if (storedToken && expiresAt) {
    const isExpired = new Date(expiresAt) < new Date();
    if (!isExpired) {
      return storedToken;
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('expires_at');
  }
  return null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(getInitialToken);

  const login = (newToken: string, expiresAt: string) => {
    localStorage.setItem('access_token', newToken);
    localStorage.setItem('expires_at', expiresAt);
    setToken(newToken);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('expires_at');
    setToken(null);
  };

  return (
    <AuthContext.Provider value={{ token, isAuthenticated: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface AuthContextType {
  token: string | null;
  isAuthenticated: boolean;
  login: (token: string, expiresAt: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const storedToken = localStorage.getItem('access_token');
    const expiresAt = localStorage.getItem('expires_at');

    if (storedToken && expiresAt) {
      const isExpired = new Date(expiresAt) < new Date();
      if (!isExpired) {
        setToken(storedToken);
      } else {
        localStorage.removeItem('access_token');
        localStorage.removeItem('expires_at');
      }
    }
  }, []);

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

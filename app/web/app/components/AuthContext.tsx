"use client";

import { createContext, useContext, useState, useEffect, useCallback } from "react";

interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: string;
}

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginQuick: () => Promise<void>;
  logout: () => void;
  getAuthHeaders: () => Record<string, string>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem("agentos_token");
    if (stored) {
      setToken(stored);
      fetchUser(stored);
    } else {
      setIsLoading(false);
    }
  }, []);

  const fetchUser = async (accessToken: string) => {
    try {
      const res = await fetch("/api/v1/auth/me", {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
      } else {
        localStorage.removeItem("agentos_token");
        setToken(null);
      }
    } catch {
      // Token might still be valid, keep it
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    const res = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json();
    localStorage.setItem("agentos_token", data.access_token);
    setToken(data.access_token);
    setUser(data.user);
  };

  const loginQuick = async () => {
    const res = await fetch("/api/v1/auth/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sub: "admin", workspace: "default" }),
    });
    if (!res.ok) throw new Error("Quick token failed");
    const data = await res.json();
    localStorage.setItem("agentos_token", data.access_token);
    setToken(data.access_token);
    // Fetch user info
    await fetchUser(data.access_token);
  };

  const logout = () => {
    localStorage.removeItem("agentos_token");
    setToken(null);
    setUser(null);
  };

  const getAuthHeaders = useCallback((): Record<string, string> => {
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, [token]);

  return (
    <AuthContext.Provider
      value={{ user, token, isLoading, login, loginQuick, logout, getAuthHeaders }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

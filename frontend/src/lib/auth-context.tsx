"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { apiFetch, getStoredRefreshToken, onAuthFailure, setTokens } from "@/lib/api-client";
import type { TokenPair } from "@/lib/types";

interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  login(email: string, password: string): Promise<void>;
  register(email: string, password: string): Promise<void>;
  logout(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function requestTokenPair(path: string, email: string, password: string): Promise<TokenPair> {
  const response = await apiFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    throw new Error(`request to ${path} failed with status ${response.status}`);
  }
  return (await response.json()) as TokenPair;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    onAuthFailure(() => setIsAuthenticated(false));
  }, []);

  useEffect(() => {
    const existingRefreshToken = getStoredRefreshToken();
    if (!existingRefreshToken) {
      setIsLoading(false);
      return;
    }
    apiFetch("/v1/attempts?limit=1")
      .then((response) => setIsAuthenticated(response.ok))
      .catch(() => setIsAuthenticated(false))
      .finally(() => setIsLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const tokens = await requestTokenPair("/v1/auth/login", email, password);
    setTokens(tokens);
    setIsAuthenticated(true);
  }

  async function register(email: string, password: string) {
    const tokens = await requestTokenPair("/v1/auth/register", email, password);
    setTokens(tokens);
    setIsAuthenticated(true);
  }

  async function logout() {
    const refreshToken = getStoredRefreshToken();
    if (refreshToken) {
      await apiFetch("/v1/auth/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      }).catch(() => undefined); // logout is best-effort client-side regardless
    }
    setTokens(null);
    setIsAuthenticated(false);
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside an AuthProvider");
  return context;
}

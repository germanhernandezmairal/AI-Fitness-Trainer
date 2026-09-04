"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { apiFetch, getStoredRefreshToken, onAuthFailure, setTokens, AuthError } from "@/lib/api-client";
import type { TokenPair } from "@/lib/types";

interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  login(email: string, password: string): Promise<void>;
  register(email: string, password: string, consent: boolean): Promise<void>;
  logout(): Promise<void>;
  deleteAccount(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function requestTokenPair(
  path: string,
  body: Record<string, unknown>,
): Promise<TokenPair> {
  let response: Response;
  try {
    response = await apiFetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (error) {
    if (error instanceof AuthError) {
      // On login/register endpoints, a 401 means bad credentials, not session expiration.
      // Don't let the global auth-failure signal treat it as session invalidation.
      throw new Error("Invalid email or password");
    }
    throw error; // Network errors, etc. propagate as-is
  }
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
      // Clearing derived loading state synchronously when there's no stored session
      // to check, before any fetch starts — not fighting with any subscription.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsLoading(false);
      return;
    }
    apiFetch("/v1/attempts?limit=1")
      .then((response) => setIsAuthenticated(response.ok))
      .catch(() => setIsAuthenticated(false))
      .finally(() => setIsLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const tokens = await requestTokenPair("/v1/auth/login", { email, password });
    setTokens(tokens);
    setIsAuthenticated(true);
  }

  async function register(email: string, password: string, consent: boolean) {
    const tokens = await requestTokenPair("/v1/auth/register", { email, password, consent });
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

  async function deleteAccount() {
    await apiFetch("/v1/users/me", { method: "DELETE" });
    await logout(); // best-effort refresh-token revoke (harmless — it's already gone via
                     // cascade) + the same local token-clearing logout() always does
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, login, register, logout, deleteAccount }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside an AuthProvider");
  return context;
}

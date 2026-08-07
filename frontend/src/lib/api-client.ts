import type { TokenPair } from "@/lib/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const REFRESH_TOKEN_STORAGE_KEY = "refresh_token";

export class AuthError extends Error {
  constructor(message = "authentication required") {
    super(message);
    this.name = "AuthError";
  }
}

let accessToken: string | null = null;
let authFailureCallback: (() => void) | null = null;
let refreshPromise: Promise<boolean> | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function getStoredRefreshToken(): string | null {
  if (typeof localStorage === "undefined") return null;
  return localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
}

export function setTokens(tokens: TokenPair | null): void {
  if (tokens === null) {
    accessToken = null;
    if (typeof localStorage !== "undefined") {
      localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
    }
    return;
  }
  accessToken = tokens.access_token;
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, tokens.refresh_token);
  }
}

export function onAuthFailure(callback: () => void): void {
  authFailureCallback = callback;
}

function buildHeaders(init?: RequestInit): Record<string, string> {
  const headers: Record<string, string> = {};

  // Copy existing headers
  if (init?.headers) {
    if (init.headers instanceof Headers) {
      init.headers.forEach((value, key) => {
        headers[key] = value;
      });
    } else if (Array.isArray(init.headers)) {
      init.headers.forEach(([key, value]) => {
        headers[key] = value;
      });
    } else {
      Object.assign(headers, init.headers);
    }
  }

  // Add authorization header
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  return headers;
}

async function refreshAccessToken(): Promise<boolean> {
  // If a refresh is already in flight, wait for it instead of starting a new one.
  // This prevents concurrent callers from each using the same refresh token,
  // which could look like token theft to a server with token-reuse detection.
  if (refreshPromise) {
    return refreshPromise;
  }

  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) return false;

  refreshPromise = (async () => {
    const response = await fetch(`${BASE_URL}/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) return false;

    const tokens = (await response.json()) as TokenPair;
    setTokens(tokens);
    return true;
  })().finally(() => {
    refreshPromise = null;
  });

  return refreshPromise;
}

/**
 * The only function the app uses to call the backend. Returns the raw Response
 * for any status other than a 401 that survives one refresh-and-retry attempt —
 * callers decide what a given status code means for them (see the frontend
 * design spec's error-handling table).
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers: buildHeaders(init) });
  if (response.status !== 401) return response;

  const refreshed = await refreshAccessToken();
  if (!refreshed) {
    setTokens(null);
    authFailureCallback?.();
    throw new AuthError();
  }

  const retried = await fetch(`${BASE_URL}${path}`, { ...init, headers: buildHeaders(init) });
  if (retried.status === 401) {
    setTokens(null);
    authFailureCallback?.();
    throw new AuthError();
  }
  return retried;
}

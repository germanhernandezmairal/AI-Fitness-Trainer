# Frontend v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Next.js frontend that exercises every backend endpoint that exists today: register/login/refresh/logout, upload a squat video, poll for and display CV analysis results (including the annotated video), list history, and delete an attempt (GDPR erasure).

**Architecture:** A Next.js 15 App Router app in `frontend/`, talking directly to the FastAPI backend over CORS (no BFF/proxy layer). The access token lives in memory (React context); the refresh token lives in `localStorage`. A shared `apiFetch` wrapper attaches the access token and performs one silent refresh-and-retry on a 401 before giving up and forcing re-login. TanStack Query drives all server-state fetching, including polling an in-flight attempt until it reaches a terminal status.

**Tech Stack:** Next.js 15 (App Router) · TypeScript · Tailwind CSS + shadcn/ui · TanStack Query v5 · Vitest + React Testing Library (unit) · Playwright (e2e) · Node 20+.

## Global Constraints

Copied from `docs/superpowers/specs/2026-08-04-frontend-design.md`. Every task's requirements implicitly include these.

- API prefix `/v1` on every backend call.
- Access token: in-memory only, never persisted. Refresh token: `localStorage`, key `refresh_token`.
- On any `401`: exactly one silent refresh-and-retry, then clear tokens and redirect to `/login`.
- The annotated video is fetched with `fetch()` + the `Authorization` header and shown via a blob URL — never a plain `<video src="...">` pointed at the backend, since the endpoint requires a header a native tag cannot send.
- Only `exercise_type: "squat"` is supported — the upload form does not offer a choice.
- Client-side upload pre-check mirrors the backend: extensions `.mp4`/`.mov` only, max size 100 MB (`104_857_600` bytes) — the backend remains authoritative; this is a UX nicety, not a security boundary.
- Upload rejection codes (`unsupported_format`, `file_too_large`, `video_too_long`, `unknown_exercise_type`) have no backend-provided user copy — the frontend owns a copy table for these four.
- shadcn/ui primitives for interactive elements (accessible by default, per the memoria's WCAG requirement).

---

## File Structure

```
backend/
  app/main.py                          # MODIFY: add CORSMiddleware (Task 1)

frontend/
  package.json, tsconfig.json, next.config.ts, tailwind.config.ts, postcss.config.mjs
  vitest.config.ts, vitest.setup.ts, playwright.config.ts
  .env.local.example                   # NEXT_PUBLIC_API_BASE_URL
  src/
    app/
      layout.tsx                       # QueryClientProvider + AuthProvider (Task 6)
      globals.css
      login/page.tsx                   # Task 7
      register/page.tsx                # Task 7
      page.tsx                         # protected home: history + upload (Task 13)
      attempts/[id]/page.tsx           # detail/results (Task 12)
    components/
      ui/                              # shadcn/ui generated: button.tsx, input.tsx, label.tsx, card.tsx, alert.tsx
      protected-route.tsx              # Task 8
      video-upload-form.tsx            # Task 9
      attempt-result.tsx               # Task 11
      attempt-history-list.tsx         # Task 13
    lib/
      types.ts                         # Task 2
      api-client.ts                    # Task 3
      auth-context.tsx                 # Task 4
      upload-error-messages.ts         # Task 9
    hooks/
      use-attempt.ts                   # Task 10
      use-attempts.ts                  # Task 13
      use-attempt-video.ts             # Task 11
  tests/
    unit/                              # mirrors src/, one *.test.ts(x) per tested file
    e2e/
      full-flow.spec.ts                # Task 14
```

---

### Task 1: Backend CORS middleware

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_cors.py`

**Interfaces:**
- Produces: `app.main.app` now sends `Access-Control-Allow-Origin` for requests from `http://localhost:3000` (the Next.js dev server).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cors.py
async def test_allows_the_frontend_dev_origin(client):
    response = await client.options(
        "/v1/attempts",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_rejects_an_unlisted_origin(client):
    response = await client.options(
        "/v1/attempts",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`, with `UV_PROJECT_ENVIRONMENT` pointed off-drive per this machine's setup):
`uv run pytest tests/test_cors.py -v`
Expected: FAIL — no CORS headers present on either response (no middleware yet).

- [ ] **Step 3: Add CORS middleware**

In `backend/app/config.py`, add one field to `Settings` (near the other URL-shaped settings):

```python
    cors_allowed_origins: list[str] = ["http://localhost:3000"]
```

In `backend/app/main.py`, add the import and middleware registration right after the `app = FastAPI(...)` line:

```python
from fastapi.middleware.cors import CORSMiddleware
...
app = FastAPI(title="AI Fitness Trainer Backend", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins,
    allow_credentials=False,  # tokens travel in the Authorization header, not cookies
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)
```

Add the matching line to `backend/.env.example`:
```
CORS_ALLOWED_ORIGINS=["http://localhost:3000"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cors.py -v`
Expected: PASS

- [ ] **Step 5: Run the full backend suite to confirm nothing broke**

Run: `uv run pytest -v`
Expected: all tests pass (126 existing + 2 new = 128).

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/app/config.py backend/.env.example backend/tests/test_cors.py
git commit -m "feat(backend): add CORS middleware for the frontend dev origin"
```

---

### Task 2: Scaffold the Next.js app

**Files:**
- Create: `frontend/` (via `create-next-app`), then modify its generated config files.

**Interfaces:**
- Produces: a running Next.js app at `frontend/`, importable via the `@/*` alias, with Tailwind, shadcn/ui, TanStack Query, Vitest, and Playwright all installed and configured (but not yet used by any real feature code).

- [ ] **Step 1: Scaffold with create-next-app**

From the repo root:

```bash
npx create-next-app@latest frontend --typescript --tailwind --app --src-dir --import-alias "@/*" --eslint --no-turbopack
cd frontend
```

Accept the defaults it prompts for.

- [ ] **Step 2: Install the remaining runtime and dev dependencies**

```bash
npm install @tanstack/react-query
npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event @types/node
```

- [ ] **Step 3: Initialize shadcn/ui and add the primitives this plan needs**

```bash
npx shadcn@latest init -d
npx shadcn@latest add button input label card alert
```

This creates `src/components/ui/{button,input,label,card,alert}.tsx` plus `src/lib/utils.ts` (the `cn()` helper shadcn's components depend on).

- [ ] **Step 4: Configure Vitest**

```typescript
// frontend/vitest.config.ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["tests/unit/**/*.test.{ts,tsx}"],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
});
```

```typescript
// frontend/vitest.setup.ts
import "@testing-library/jest-dom/vitest";
```

Add to `frontend/package.json` scripts: `"test": "vitest run"`.

- [ ] **Step 5: Configure Playwright**

```bash
npm init playwright@latest -- --quiet --browser=chromium --no-examples
```

When prompted for the test directory, use `tests/e2e`.

- [ ] **Step 6: Add the API base URL env var**

```
# frontend/.env.local.example
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

```bash
cp .env.local.example .env.local
```

- [ ] **Step 7: Verify the scaffold builds and runs**

Run: `npm run build`
Expected: builds successfully with the default Next.js starter page.

Run: `npm test`
Expected: passes (no test files yet, or a trivial passing run — Vitest reports "No test files found" which is expected at this point).

- [ ] **Step 8: Commit**

```bash
cd ..
git add frontend/
git commit -m "chore(frontend): scaffold Next.js app with Tailwind, shadcn/ui, TanStack Query, Vitest, Playwright"
```

---

### Task 3: Shared TypeScript types

**Files:**
- Create: `frontend/src/lib/types.ts`

**Interfaces:**
- Produces: every type used by every later task. Exact names below — later tasks import from here, not redefine.

- [ ] **Step 1: Write the types file**

```typescript
// frontend/src/lib/types.ts

export type AttemptStatus = "queued" | "processing" | "completed" | "failed";

export type FormErrorCode =
  | "knee_valgus"
  | "insufficient_depth"
  | "excessive_forward_lean";

export type FailureCode =
  | "no_pose_detected"
  | "low_pose_confidence"
  | "no_movement_detected"
  | "storage_error"
  | "worker_error";

export type UploadErrorCode =
  | "unsupported_format"
  | "file_too_large"
  | "video_too_long"
  | "unknown_exercise_type";

export interface RepResult {
  rep_index: number;
  start_time_sec: number;
  end_time_sec: number;
  min_knee_angle_deg: number;
  score: number;
  errors: FormErrorCode[];
}

export interface AnalysisResult {
  exercise_type: "squat";
  overall_score: number;
  summary: string;
  rep_count: number;
  reps: RepResult[];
  annotated_video_url: string | null;
  algorithm_version: string;
}

export interface ErrorPayload {
  code: FailureCode;
  message: string;
}

export interface AttemptCreated {
  attempt_id: string;
  status: AttemptStatus;
}

export interface AttemptDetail {
  attempt_id: string;
  exercise_type: string;
  status: AttemptStatus;
  created_at: string;
  completed_at: string | null;
  result: AnalysisResult | null;
  error: ErrorPayload | null;
}

export interface AttemptSummary {
  attempt_id: string;
  exercise_type: string;
  status: AttemptStatus;
  overall_score: number | null;
  created_at: string;
}

export interface AttemptPage {
  items: AttemptSummary[];
  next_cursor: string | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UploadErrorResponse {
  error: {
    code: UploadErrorCode;
    message: string;
  };
}
```

- [ ] **Step 2: Verify it compiles**

Run (from `frontend/`): `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat(frontend): add shared types mirroring the backend contract"
```

---

### Task 4: API client with refresh-and-retry

**Files:**
- Create: `frontend/src/lib/api-client.ts`
- Test: `frontend/tests/unit/lib/api-client.test.ts`

**Interfaces:**
- Consumes: `TokenPair` from `@/lib/types`.
- Produces:
  - `setTokens(tokens: TokenPair | null): void` — called by auth-context (Task 5) after login/register/refresh, and with `null` on logout.
  - `getAccessToken(): string | null`
  - `onAuthFailure(callback: () => void): void` — registers a callback (auth-context wires this to its own logout) fired when a retried request still 401s.
  - `class AuthError extends Error {}` — thrown in that case, so callers can distinguish "give up and redirect" from an ordinary failed request.
  - `apiFetch(path: string, init?: RequestInit): Promise<Response>` — the only function every other task uses to talk to the backend. Never auto-parses the body or throws for ordinary non-2xx statuses (401 aside) — callers decide what a given status code means for them, per the spec's error-handling table (422 inline, 400 inline-with-code, 502 banner).

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/tests/unit/lib/api-client.test.ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, AuthError, getAccessToken, onAuthFailure, setTokens } from "@/lib/api-client";

const BASE_URL = "http://localhost:8000";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiFetch", () => {
  beforeEach(() => {
    setTokens(null);
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("attaches the access token as a Bearer header", async () => {
    setTokens({ access_token: "abc123", refresh_token: "r1", token_type: "bearer" });
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    await apiFetch("/v1/attempts");

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect((init?.headers as Record<string, string>)["Authorization"]).toBe("Bearer abc123");
  });

  it("returns non-401 responses untouched, without retrying", async () => {
    setTokens({ access_token: "abc123", refresh_token: "r1", token_type: "bearer" });
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(400, { error: { code: "file_too_large" } }));

    const response = await apiFetch("/v1/attempts", { method: "POST" });

    expect(response.status).toBe(400);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("on a 401, refreshes once and retries the original request", async () => {
    setTokens({ access_token: "expired", refresh_token: "good-refresh", token_type: "bearer" });
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(401, {})) // original request
      .mockResolvedValueOnce(
        jsonResponse(200, { access_token: "fresh", refresh_token: "rotated", token_type: "bearer" }),
      ) // POST /v1/auth/refresh
      .mockResolvedValueOnce(jsonResponse(200, { ok: true })); // retried original request

    const response = await apiFetch("/v1/attempts");

    expect(response.status).toBe(200);
    expect(fetch).toHaveBeenCalledTimes(3);
    const refreshCall = vi.mocked(fetch).mock.calls[1];
    expect(refreshCall[0]).toBe(`${BASE_URL}/v1/auth/refresh`);
    expect(getAccessToken()).toBe("fresh");
    const retryCall = vi.mocked(fetch).mock.calls[2];
    expect((retryCall[1]?.headers as Record<string, string>)["Authorization"]).toBe("Bearer fresh");
  });

  it("throws AuthError and fires onAuthFailure when refresh itself fails", async () => {
    const failureHandler = vi.fn();
    onAuthFailure(failureHandler);
    setTokens({ access_token: "expired", refresh_token: "bad-refresh", token_type: "bearer" });
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(401, {})) // original request
      .mockResolvedValueOnce(jsonResponse(401, {})); // POST /v1/auth/refresh also fails

    await expect(apiFetch("/v1/attempts")).rejects.toThrow(AuthError);
    expect(failureHandler).toHaveBeenCalledOnce();
    expect(getAccessToken()).toBeNull();
  });

  it("throws AuthError without retrying again when the retried request itself 401s", async () => {
    setTokens({ access_token: "expired", refresh_token: "good-refresh", token_type: "bearer" });
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(401, {})) // original request
      .mockResolvedValueOnce(
        jsonResponse(200, { access_token: "fresh", refresh_token: "rotated", token_type: "bearer" }),
      ) // refresh succeeds
      .mockResolvedValueOnce(jsonResponse(401, {})); // retried request still 401s

    await expect(apiFetch("/v1/attempts")).rejects.toThrow(AuthError);
    expect(fetch).toHaveBeenCalledTimes(3);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — `@/lib/api-client` does not exist yet.

- [ ] **Step 3: Implement the API client**

```typescript
// frontend/src/lib/api-client.ts
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
    localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
    return;
  }
  accessToken = tokens.access_token;
  localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, tokens.refresh_token);
}

export function onAuthFailure(callback: () => void): void {
  authFailureCallback = callback;
}

function buildHeaders(init?: RequestInit): Headers {
  const headers = new Headers(init?.headers);
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  return headers;
}

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) return false;

  const response = await fetch(`${BASE_URL}/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) return false;

  const tokens = (await response.json()) as TokenPair;
  setTokens(tokens);
  return true;
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: PASS, all 5 tests in `api-client.test.ts`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api-client.ts frontend/tests/unit/lib/api-client.test.ts
git commit -m "feat(frontend): add apiFetch with one-shot refresh-and-retry on 401"
```

---

### Task 5: Auth context

**Files:**
- Create: `frontend/src/lib/auth-context.tsx`
- Test: `frontend/tests/unit/lib/auth-context.test.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `setTokens`, `getStoredRefreshToken`, `onAuthFailure`, `AuthError` from `@/lib/api-client`; `TokenPair` from `@/lib/types`.
- Produces:
  - `AuthProvider({ children }: { children: React.ReactNode })` — wraps the app (wired in Task 6).
  - `useAuth()` returning `{ isAuthenticated: boolean; isLoading: boolean; login(email: string, password: string): Promise<void>; register(email: string, password: string): Promise<void>; logout(): Promise<void> }`.

- [ ] **Step 1: Write the failing tests**

```tsx
// frontend/tests/unit/lib/auth-context.test.tsx
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import * as apiClient from "@/lib/api-client";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("useAuth", () => {
  beforeEach(() => {
    localStorage.clear();
    apiClient.setTokens(null);
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts unauthenticated with no stored refresh token", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("becomes authenticated after a successful login", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(200, { access_token: "a1", refresh_token: "r1", token_type: "bearer" }),
    );
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.login("me@example.com", "correct-horse-battery-staple");
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(apiClient.getAccessToken()).toBe("a1");
    expect(localStorage.getItem("refresh_token")).toBe("r1");
  });

  it("becomes authenticated after a successful register", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(201, { access_token: "a1", refresh_token: "r1", token_type: "bearer" }),
    );
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.register("me@example.com", "correct-horse-battery-staple");
    });

    expect(result.current.isAuthenticated).toBe(true);
  });

  it("clears tokens and flips to unauthenticated on logout", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(200, { access_token: "a1", refresh_token: "r1", token_type: "bearer" }))
      .mockResolvedValueOnce(jsonResponse(204, {}));
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    await act(async () => {
      await result.current.login("me@example.com", "correct-horse-battery-staple");
    });

    await act(async () => {
      await result.current.logout();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(apiClient.getAccessToken()).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("becomes unauthenticated when apiFetch reports an auth failure", async () => {
    let registeredCallback: (() => void) | undefined;
    vi.spyOn(apiClient, "onAuthFailure").mockImplementation((callback) => {
      registeredCallback = callback;
    });
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(200, { access_token: "a1", refresh_token: "r1", token_type: "bearer" }),
    );
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    await act(async () => {
      await result.current.login("me@example.com", "correct-horse-battery-staple");
    });
    expect(result.current.isAuthenticated).toBe(true);
    expect(registeredCallback).toBeDefined();

    act(() => {
      // Simulate what api-client does internally when a retried request still 401s.
      registeredCallback?.();
    });

    expect(result.current.isAuthenticated).toBe(false);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — `@/lib/auth-context` does not exist yet.

- [ ] **Step 3: Implement the auth context**

```tsx
// frontend/src/lib/auth-context.tsx
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
```

Note on the last test in Step 1 (`"becomes unauthenticated when apiFetch reports an auth failure"`): it spies on `onAuthFailure` to capture the callback `AuthProvider` registers on mount, then invokes that callback directly to simulate what `api-client` does internally when a retried request still 401s — asserting `isAuthenticated` flips to `false`. The real end-to-end trigger (a live 401-after-retry) is exercised by Task 14's Playwright test, which runs against the real backend rather than a mocked one.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: PASS, all tests in `auth-context.test.tsx`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/auth-context.tsx frontend/tests/unit/lib/auth-context.test.tsx
git commit -m "feat(frontend): add AuthProvider/useAuth wrapping login/register/logout"
```

---

### Task 6: Root layout wiring

**Files:**
- Modify: `frontend/src/app/layout.tsx`

**Interfaces:**
- Consumes: `AuthProvider` from `@/lib/auth-context`.
- Produces: every page rendered inside `<AuthProvider><QueryClientProvider>...` — later tasks' pages can call `useAuth()`/TanStack Query hooks without re-wrapping.

- [ ] **Step 1: Create a client-side providers wrapper**

```tsx
// frontend/src/app/providers.tsx
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { AuthProvider } from "@/lib/auth-context";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 2: Wire it into the root layout**

Edit `frontend/src/app/layout.tsx` — keep the generated `<html>`/`<body>`/font setup, wrap `{children}` with `<Providers>`:

```tsx
import { Providers } from "@/app/providers";
// ...(keep existing font/metadata imports)

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={/* keep the generated font className(s) */}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

- [ ] **Step 3: Verify the app still builds and renders**

Run: `npm run build`
Expected: builds successfully.

Run: `npm run dev`, visit `http://localhost:3000`
Expected: the default page renders with no console errors about missing context providers.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/layout.tsx frontend/src/app/providers.tsx
git commit -m "feat(frontend): wire AuthProvider and QueryClientProvider into the root layout"
```

---

### Task 7: Login and register pages

**Files:**
- Create: `frontend/src/app/login/page.tsx`
- Create: `frontend/src/app/register/page.tsx`
- Test: `frontend/tests/unit/app/login-page.test.tsx`
- Test: `frontend/tests/unit/app/register-page.test.tsx`

**Interfaces:**
- Consumes: `useAuth` from `@/lib/auth-context`; shadcn/ui `Button`, `Input`, `Label`, `Card`, `Alert` from `@/components/ui/*`.
- Produces: `/login` and `/register` routes. On success, both redirect to `/` via `useRouter().push("/")`.

- [ ] **Step 1: Write the failing tests**

```tsx
// frontend/tests/unit/app/login-page.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mockPush }) }));

const mockLogin = vi.fn();
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ login: mockLogin }) }));

import LoginPage from "@/app/login/page";

describe("LoginPage", () => {
  it("submits the entered credentials and redirects home on success", async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    render(<LoginPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/email/i), "me@example.com");
    await user.type(screen.getByLabelText(/password/i), "correct-horse-battery-staple");
    await user.click(screen.getByRole("button", { name: /log in/i }));

    await waitFor(() =>
      expect(mockLogin).toHaveBeenCalledWith("me@example.com", "correct-horse-battery-staple"),
    );
    expect(mockPush).toHaveBeenCalledWith("/");
  });

  it("shows an error message when login fails", async () => {
    mockLogin.mockRejectedValueOnce(new Error("request to /v1/auth/login failed with status 401"));
    render(<LoginPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/email/i), "me@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrong-password");
    await user.click(screen.getByRole("button", { name: /log in/i }));

    expect(await screen.findByText(/incorrect email or password/i)).toBeInTheDocument();
  });
});
```

```tsx
// frontend/tests/unit/app/register-page.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mockPush }) }));

const mockRegister = vi.fn();
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ register: mockRegister }) }));

import RegisterPage from "@/app/register/page";

describe("RegisterPage", () => {
  it("rejects a password shorter than 8 characters before calling register", async () => {
    render(<RegisterPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/email/i), "me@example.com");
    await user.type(screen.getByLabelText(/password/i), "short");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByText(/at least 8 characters/i)).toBeInTheDocument();
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it("submits and redirects home on success", async () => {
    mockRegister.mockResolvedValueOnce(undefined);
    render(<RegisterPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/email/i), "me@example.com");
    await user.type(screen.getByLabelText(/password/i), "correct-horse-battery-staple");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() =>
      expect(mockRegister).toHaveBeenCalledWith("me@example.com", "correct-horse-battery-staple"),
    );
    expect(mockPush).toHaveBeenCalledWith("/");
  });

  it("shows an error message when the email is already registered", async () => {
    mockRegister.mockRejectedValueOnce(new Error("request to /v1/auth/register failed with status 409"));
    render(<RegisterPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/email/i), "me@example.com");
    await user.type(screen.getByLabelText(/password/i), "correct-horse-battery-staple");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByText(/already registered/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — neither page exists yet.

- [ ] **Step 3: Implement the login page**

```tsx
// frontend/src/app/login/page.tsx
"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      router.push("/");
    } catch {
      setError("Incorrect email or password.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Card className="mx-auto mt-16 max-w-sm p-6">
      <form onSubmit={handleSubmit} className="space-y-4">
        <h1 className="text-xl font-semibold">Log in</h1>
        {error && <Alert variant="destructive">{error}</Alert>}
        <div className="space-y-1">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <Button type="submit" disabled={isSubmitting} className="w-full">
          Log in
        </Button>
      </form>
    </Card>
  );
}
```

- [ ] **Step 4: Implement the register page**

```tsx
// frontend/src/app/register/page.tsx
"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";

const MIN_PASSWORD_LENGTH = 8;

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      await register(email, password);
      router.push("/");
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      if (message.includes("409")) {
        setError("That email is already registered.");
      } else {
        setError("Could not create the account. Try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Card className="mx-auto mt-16 max-w-sm p-6">
      <form onSubmit={handleSubmit} className="space-y-4">
        <h1 className="text-xl font-semibold">Create account</h1>
        {error && <Alert variant="destructive">{error}</Alert>}
        <div className="space-y-1">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <Button type="submit" disabled={isSubmitting} className="w-full">
          Create account
        </Button>
      </form>
    </Card>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm test`
Expected: PASS, all tests in both files.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/login frontend/src/app/register frontend/tests/unit/app/login-page.test.tsx frontend/tests/unit/app/register-page.test.tsx
git commit -m "feat(frontend): add login and register pages"
```

---

### Task 8: Protected route wrapper

**Files:**
- Create: `frontend/src/components/protected-route.tsx`
- Test: `frontend/tests/unit/components/protected-route.test.tsx`

**Interfaces:**
- Consumes: `useAuth` from `@/lib/auth-context`.
- Produces: `ProtectedRoute({ children }: { children: React.ReactNode })` — renders `children` only when authenticated; shows nothing (a loading state) while `isLoading`; redirects to `/login` when not authenticated and not loading. Used by Task 13's home page and Task 12's detail page.

- [ ] **Step 1: Write the failing tests**

```tsx
// frontend/tests/unit/components/protected-route.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mockPush }) }));

const mockUseAuth = vi.fn();
vi.mock("@/lib/auth-context", () => ({ useAuth: () => mockUseAuth() }));

import { ProtectedRoute } from "@/components/protected-route";

describe("ProtectedRoute", () => {
  it("renders children when authenticated", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, isLoading: false });

    render(
      <ProtectedRoute>
        <p>secret content</p>
      </ProtectedRoute>,
    );

    expect(screen.getByText("secret content")).toBeInTheDocument();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("renders nothing and does not redirect while loading", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false, isLoading: true });

    render(
      <ProtectedRoute>
        <p>secret content</p>
      </ProtectedRoute>,
    );

    expect(screen.queryByText("secret content")).not.toBeInTheDocument();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("redirects to /login when not authenticated and not loading", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false, isLoading: false });

    render(
      <ProtectedRoute>
        <p>secret content</p>
      </ProtectedRoute>,
    );

    expect(mockPush).toHaveBeenCalledWith("/login");
    expect(screen.queryByText("secret content")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — `@/components/protected-route` does not exist yet.

- [ ] **Step 3: Implement the wrapper**

```tsx
// frontend/src/components/protected-route.tsx
"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || !isAuthenticated) return null;
  return <>{children}</>;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: PASS, all 3 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/protected-route.tsx frontend/tests/unit/components/protected-route.test.tsx
git commit -m "feat(frontend): add ProtectedRoute wrapper"
```

---

### Task 9: Upload form and error-copy table

**Files:**
- Create: `frontend/src/lib/upload-error-messages.ts`
- Create: `frontend/src/components/video-upload-form.tsx`
- Test: `frontend/tests/unit/lib/upload-error-messages.test.ts`
- Test: `frontend/tests/unit/components/video-upload-form.test.tsx`

**Interfaces:**
- Consumes: `apiFetch` from `@/lib/api-client`; `AttemptCreated`, `UploadErrorCode`, `UploadErrorResponse` from `@/lib/types`.
- Produces:
  - `uploadErrorMessage(code: UploadErrorCode): string`.
  - `VideoUploadForm({ onUploaded }: { onUploaded: (attemptId: string) => void })`.

- [ ] **Step 1: Write the failing test for the copy table**

```typescript
// frontend/tests/unit/lib/upload-error-messages.test.ts
import { describe, expect, it } from "vitest";
import { uploadErrorMessage } from "@/lib/upload-error-messages";
import type { UploadErrorCode } from "@/lib/types";

describe("uploadErrorMessage", () => {
  const codes: UploadErrorCode[] = [
    "unsupported_format",
    "file_too_large",
    "video_too_long",
    "unknown_exercise_type",
  ];

  it.each(codes)("returns a non-empty message for %s", (code) => {
    expect(uploadErrorMessage(code).length).toBeGreaterThan(0);
  });

  it("returns distinct messages for each code", () => {
    const messages = new Set(codes.map(uploadErrorMessage));
    expect(messages.size).toBe(codes.length);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the copy table**

```typescript
// frontend/src/lib/upload-error-messages.ts
import type { UploadErrorCode } from "@/lib/types";

const MESSAGES: Record<UploadErrorCode, string> = {
  unsupported_format: "That file format isn't supported. Upload an MP4 or MOV video.",
  file_too_large: "That video is too large. The limit is 100 MB.",
  video_too_long: "That video is too long. The limit is 60 seconds.",
  unknown_exercise_type: "That exercise type isn't supported yet.",
};

export function uploadErrorMessage(code: UploadErrorCode): string {
  return MESSAGES[code];
}
```

- [ ] **Step 4: Write the failing tests for the upload form**

```tsx
// frontend/tests/unit/components/video-upload-form.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { VideoUploadForm } from "@/components/video-upload-form";

function makeFile(name: string, sizeBytes: number, type: string): File {
  const file = new File([new Uint8Array(sizeBytes)], name, { type });
  return file;
}

describe("VideoUploadForm", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("rejects an unsupported extension before uploading", async () => {
    const onUploaded = vi.fn();
    render(<VideoUploadForm onUploaded={onUploaded} />);
    const user = userEvent.setup();

    const input = screen.getByLabelText(/video file/i);
    await user.upload(input, makeFile("clip.avi", 1000, "video/x-msvideo"));
    await user.click(screen.getByRole("button", { name: /upload/i }));

    expect(await screen.findByText(/mp4 or mov/i)).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("rejects a file over 100MB before uploading", async () => {
    const onUploaded = vi.fn();
    render(<VideoUploadForm onUploaded={onUploaded} />);
    const user = userEvent.setup();

    const input = screen.getByLabelText(/video file/i);
    await user.upload(input, makeFile("clip.mp4", 105_000_000, "video/mp4"));
    await user.click(screen.getByRole("button", { name: /upload/i }));

    expect(await screen.findByText(/100 mb/i)).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("uploads a valid file and calls onUploaded with the new attempt id", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ attempt_id: "attempt-1", status: "queued" }), { status: 202 }),
    );
    const onUploaded = vi.fn();
    render(<VideoUploadForm onUploaded={onUploaded} />);
    const user = userEvent.setup();

    const input = screen.getByLabelText(/video file/i);
    await user.upload(input, makeFile("clip.mp4", 1000, "video/mp4"));
    await user.click(screen.getByRole("button", { name: /upload/i }));

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith("attempt-1"));
  });

  it("shows the backend's rejection message on a 400 response", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({ error: { code: "video_too_long", message: "too long" } }),
        { status: 400 },
      ),
    );
    const onUploaded = vi.fn();
    render(<VideoUploadForm onUploaded={onUploaded} />);
    const user = userEvent.setup();

    const input = screen.getByLabelText(/video file/i);
    await user.upload(input, makeFile("clip.mp4", 1000, "video/mp4"));
    await user.click(screen.getByRole("button", { name: /upload/i }));

    expect(await screen.findByText(/60 seconds/i)).toBeInTheDocument();
    expect(onUploaded).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — `@/components/video-upload-form` does not exist yet.

- [ ] **Step 6: Implement the upload form**

```tsx
// frontend/src/components/video-upload-form.tsx
"use client";

import { useState, type ChangeEvent, type FormEvent } from "react";
import { apiFetch } from "@/lib/api-client";
import { uploadErrorMessage } from "@/lib/upload-error-messages";
import type { AttemptCreated, UploadErrorResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Alert } from "@/components/ui/alert";

const ALLOWED_EXTENSIONS = [".mp4", ".mov"];
const MAX_BYTES = 104_857_600;

function hasAllowedExtension(filename: string): boolean {
  const lower = filename.toLowerCase();
  return ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function VideoUploadForm({ onUploaded }: { onUploaded: (attemptId: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setError(null);
    setFile(event.target.files?.[0] ?? null);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose a video file first.");
      return;
    }
    if (!hasAllowedExtension(file.name)) {
      setError(uploadErrorMessage("unsupported_format"));
      return;
    }
    if (file.size > MAX_BYTES) {
      setError(uploadErrorMessage("file_too_large"));
      return;
    }

    setError(null);
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append("video", file);
      formData.append("exercise_type", "squat");

      const response = await apiFetch("/v1/attempts", { method: "POST", body: formData });

      if (response.status === 202) {
        const created = (await response.json()) as AttemptCreated;
        onUploaded(created.attempt_id);
        return;
      }
      if (response.status === 400) {
        const body = (await response.json()) as UploadErrorResponse;
        setError(uploadErrorMessage(body.error.code));
        return;
      }
      setError("Could not upload the video. Try again.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <Alert variant="destructive">{error}</Alert>}
      <div className="space-y-1">
        <Label htmlFor="video-file">Video file</Label>
        <input
          id="video-file"
          type="file"
          accept="video/mp4,video/quicktime"
          onChange={handleFileChange}
        />
      </div>
      <Button type="submit" disabled={isUploading}>
        {isUploading ? "Uploading..." : "Upload"}
      </Button>
    </form>
  );
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `npm test`
Expected: PASS, all tests in both files.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/upload-error-messages.ts frontend/src/components/video-upload-form.tsx frontend/tests/unit/lib/upload-error-messages.test.ts frontend/tests/unit/components/video-upload-form.test.tsx
git commit -m "feat(frontend): add VideoUploadForm with client-side pre-checks"
```

---

### Task 10: Attempt polling hook

**Files:**
- Create: `frontend/src/hooks/use-attempt.ts`
- Test: `frontend/tests/unit/hooks/use-attempt.test.ts`

**Interfaces:**
- Consumes: `apiFetch` from `@/lib/api-client`; `AttemptDetail` from `@/lib/types`.
- Produces: `useAttempt(attemptId: string)` — a TanStack Query result (`{ data, isLoading, error, ... }` where `data: AttemptDetail | undefined`) that refetches every 2 seconds while `data.status` is `"queued"` or `"processing"`, and stops once terminal. Used by Task 12's detail page.

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/tests/unit/hooks/use-attempt.test.ts
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { useAttempt } from "@/hooks/use-attempt";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

describe("useAttempt", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the fetched attempt", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ attempt_id: "a1", status: "completed", exercise_type: "squat" }),
    );

    const { result } = renderHook(() => useAttempt("a1"), { wrapper });

    await waitFor(() => expect(result.current.data?.status).toBe("completed"));
  });

  it("stops polling once the attempt reaches a terminal status", async () => {
    vi.useFakeTimers();
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ attempt_id: "a1", status: "completed" }));

    renderHook(() => useAttempt("a1"), { wrapper });

    // Let the initial fetch (a resolved promise) settle before advancing fake timers.
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

    // Advance past several would-be poll intervals; refetchInterval must have returned
    // false once status was "completed" on the very first response, so no more fetches fire.
    await vi.advanceTimersByTimeAsync(10_000);

    expect(fetch).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — `@/hooks/use-attempt` does not exist yet.

- [ ] **Step 3: Implement the hook**

```typescript
// frontend/src/hooks/use-attempt.ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { AttemptDetail } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

async function fetchAttempt(attemptId: string): Promise<AttemptDetail> {
  const response = await apiFetch(`/v1/attempts/${attemptId}`);
  if (!response.ok) {
    throw new Error(`failed to load attempt ${attemptId}: ${response.status}`);
  }
  return (await response.json()) as AttemptDetail;
}

export function useAttempt(attemptId: string) {
  return useQuery({
    queryKey: ["attempt", attemptId],
    queryFn: () => fetchAttempt(attemptId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      const isTerminal = status === "completed" || status === "failed";
      return isTerminal ? false : POLL_INTERVAL_MS;
    },
  });
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/use-attempt.ts frontend/tests/unit/hooks/use-attempt.test.ts
git commit -m "feat(frontend): add useAttempt polling hook"
```

---

### Task 11: Video blob hook and attempt result component

**Files:**
- Create: `frontend/src/hooks/use-attempt-video.ts`
- Create: `frontend/src/components/attempt-result.tsx`
- Test: `frontend/tests/unit/hooks/use-attempt-video.test.ts`
- Test: `frontend/tests/unit/components/attempt-result.test.tsx`

**Interfaces:**
- Consumes: `apiFetch` from `@/lib/api-client`; `AnalysisResult` from `@/lib/types`.
- Produces:
  - `useAttemptVideo(videoUrl: string | null)` returning `{ blobUrl: string | null; isLoading: boolean; error: string | null }` — fetches `videoUrl` with `apiFetch` (so the auth header is attached), wraps the response in a blob URL, and revokes it on unmount/URL change. `videoUrl` is `AnalysisResult.annotated_video_url`, already a full URL the backend returned — see §4 of the design spec for why this can't be a plain `<video src>`.
  - `AttemptResult({ result }: { result: AnalysisResult })`.

- [ ] **Step 1: Write the failing tests for the video hook**

```typescript
// frontend/tests/unit/hooks/use-attempt-video.test.ts
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAttemptVideo } from "@/hooks/use-attempt-video";

describe("useAttemptVideo", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:mock-url"),
      revokeObjectURL: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns null while videoUrl is null", () => {
    const { result } = renderHook(() => useAttemptVideo(null));
    expect(result.current.blobUrl).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("fetches the video and exposes a blob URL", async () => {
    const blob = new Blob(["fake video bytes"], { type: "video/mp4" });
    vi.mocked(fetch).mockResolvedValueOnce(new Response(blob, { status: 200 }));

    const { result } = renderHook(() => useAttemptVideo("http://localhost:8000/v1/attempts/a1/video"));

    await waitFor(() => expect(result.current.blobUrl).toBe("blob:mock-url"));
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("reports an error when the fetch fails", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 502 }));

    const { result } = renderHook(() => useAttemptVideo("http://localhost:8000/v1/attempts/a1/video"));

    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.blobUrl).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — `@/hooks/use-attempt-video` does not exist yet.

- [ ] **Step 3: Implement the video hook**

```typescript
// frontend/src/hooks/use-attempt-video.ts
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api-client";

interface UseAttemptVideoResult {
  blobUrl: string | null;
  isLoading: boolean;
  error: string | null;
}

export function useAttemptVideo(videoUrl: string | null): UseAttemptVideoResult {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!videoUrl) {
      setBlobUrl(null);
      return;
    }

    let objectUrl: string | null = null;
    let cancelled = false;

    setIsLoading(true);
    setError(null);

    // videoUrl already includes the /v1/... path the backend returned; apiFetch only
    // needs the path portion, so we pass it through relative to the API base by
    // stripping the origin if present — the backend always returns same-origin-relative
    // paths in practice (see docs/superpowers/specs/2026-08-04-frontend-design.md §4).
    const path = videoUrl.replace(/^https?:\/\/[^/]+/, "");

    apiFetch(path)
      .then((response) => {
        if (!response.ok) throw new Error(`failed to load video: ${response.status}`);
        return response.blob();
      })
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "failed to load video");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [videoUrl]);

  return { blobUrl, isLoading, error };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: PASS, all 3 tests in `use-attempt-video.test.ts`.

- [ ] **Step 5: Write the failing test for AttemptResult**

```tsx
// frontend/tests/unit/components/attempt-result.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AnalysisResult } from "@/lib/types";

vi.mock("@/hooks/use-attempt-video", () => ({
  useAttemptVideo: () => ({ blobUrl: "blob:mock-url", isLoading: false, error: null }),
}));

import { AttemptResult } from "@/components/attempt-result";

const RESULT: AnalysisResult = {
  exercise_type: "squat",
  overall_score: 82,
  summary: "Good depth overall.",
  rep_count: 1,
  reps: [
    {
      rep_index: 1,
      start_time_sec: 0,
      end_time_sec: 2,
      min_knee_angle_deg: 78,
      score: 90,
      errors: ["knee_valgus"],
    },
  ],
  annotated_video_url: "http://localhost:8000/v1/attempts/a1/video",
  algorithm_version: "squat-rules-v1",
};

describe("AttemptResult", () => {
  it("shows the overall score and summary", () => {
    render(<AttemptResult result={RESULT} />);

    expect(screen.getByText(/82/)).toBeInTheDocument();
    expect(screen.getByText(/good depth overall/i)).toBeInTheDocument();
  });

  it("lists each rep with its score", () => {
    render(<AttemptResult result={RESULT} />);

    expect(screen.getByText(/rep 1/i)).toBeInTheDocument();
    expect(screen.getByText(/90/)).toBeInTheDocument();
  });

  it("renders the annotated video using the blob URL from useAttemptVideo", () => {
    render(<AttemptResult result={RESULT} />);

    const video = screen.getByTestId("annotated-video") as HTMLVideoElement;
    expect(video.src).toBe("blob:mock-url");
  });
});
```

- [ ] **Step 6: Run test to verify it fails**

Run: `npm test`
Expected: FAIL — `@/components/attempt-result` does not exist yet.

- [ ] **Step 7: Implement AttemptResult**

```tsx
// frontend/src/components/attempt-result.tsx
"use client";

import { useAttemptVideo } from "@/hooks/use-attempt-video";
import type { AnalysisResult } from "@/lib/types";
import { Card } from "@/components/ui/card";

export function AttemptResult({ result }: { result: AnalysisResult }) {
  const { blobUrl, isLoading: isVideoLoading, error: videoError } = useAttemptVideo(
    result.annotated_video_url,
  );

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <p className="text-3xl font-bold">{result.overall_score} / 100</p>
        <p className="text-muted-foreground">{result.summary}</p>
      </Card>

      <ul className="space-y-2">
        {result.reps.map((rep) => (
          <li key={rep.rep_index} className="flex justify-between rounded border p-2">
            <span>Rep {rep.rep_index}</span>
            <span>{rep.score} / 100</span>
          </li>
        ))}
      </ul>

      {blobUrl && (
        <video data-testid="annotated-video" src={blobUrl} controls className="w-full rounded" />
      )}
      {isVideoLoading && <p>Loading annotated video...</p>}
      {videoError && <p className="text-destructive">Could not load the annotated video.</p>}
    </div>
  );
}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `npm test`
Expected: PASS, all 3 tests in `attempt-result.test.tsx`.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/hooks/use-attempt-video.ts frontend/src/components/attempt-result.tsx frontend/tests/unit/hooks/use-attempt-video.test.ts frontend/tests/unit/components/attempt-result.test.tsx
git commit -m "feat(frontend): add video blob hook and AttemptResult"
```

---

### Task 12: Attempt detail page

**Files:**
- Create: `frontend/src/app/attempts/[id]/page.tsx`

**Interfaces:**
- Consumes: `ProtectedRoute` from `@/components/protected-route`; `useAttempt` from `@/hooks/use-attempt`; `AttemptResult` from `@/components/attempt-result`; `apiFetch` from `@/lib/api-client`.
- Produces: the `/attempts/[id]` route.

- [ ] **Step 1: Implement the page**

```tsx
// frontend/src/app/attempts/[id]/page.tsx
"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/protected-route";
import { AttemptResult } from "@/components/attempt-result";
import { useAttempt } from "@/hooks/use-attempt";
import { apiFetch } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";

export default function AttemptDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <ProtectedRoute>
      <AttemptDetailContent attemptId={id} />
    </ProtectedRoute>
  );
}

function AttemptDetailContent({ attemptId }: { attemptId: string }) {
  const { data, isLoading, error } = useAttempt(attemptId);
  const router = useRouter();
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleDelete() {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      const response = await apiFetch(`/v1/attempts/${attemptId}`, { method: "DELETE" });
      if (response.status !== 204) throw new Error("delete failed");
      router.push("/");
    } catch {
      setDeleteError("Could not delete this attempt. Try again.");
      setIsDeleting(false);
    }
  }

  if (isLoading) return <p className="p-6">Loading...</p>;
  if (error || !data) return <p className="p-6">Could not load this attempt.</p>;

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Attempt</h1>
      <p className="text-muted-foreground">Status: {data.status}</p>

      {(data.status === "queued" || data.status === "processing") && (
        <p>Analyzing your video — this page updates automatically.</p>
      )}

      {data.status === "failed" && data.error && (
        <Alert variant="destructive">{data.error.message}</Alert>
      )}

      {data.status === "completed" && data.result && <AttemptResult result={data.result} />}

      {deleteError && <Alert variant="destructive">{deleteError}</Alert>}
      <Button variant="destructive" onClick={handleDelete} disabled={isDeleting}>
        {isDeleting ? "Deleting..." : "Delete this attempt"}
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Verify it compiles and renders**

Run: `npm run build`
Expected: builds successfully.

Manual check (needs the backend + a logged-in session, exercised for real in Task 14's e2e test): visit `/attempts/<id>` for a real attempt and confirm the status/result render.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/attempts
git commit -m "feat(frontend): add attempt detail page with polling and delete"
```

---

### Task 13: History list and home page

**Files:**
- Create: `frontend/src/hooks/use-attempts.ts`
- Create: `frontend/src/components/attempt-history-list.tsx`
- Create: `frontend/src/app/page.tsx`
- Test: `frontend/tests/unit/hooks/use-attempts.test.ts`
- Test: `frontend/tests/unit/components/attempt-history-list.test.tsx`

**Interfaces:**
- Consumes: `apiFetch` from `@/lib/api-client`; `AttemptPage`, `AttemptSummary` from `@/lib/types`; `ProtectedRoute` from `@/components/protected-route`; `VideoUploadForm` from `@/components/video-upload-form`.
- Produces:
  - `useAttempts(cursor: string | null)` — TanStack Query result over `GET /v1/attempts`.
  - `AttemptHistoryList()` — self-fetching list with a "load more" button driving the cursor.
  - The `/` route.

- [ ] **Step 1: Write the failing test for the hook**

```typescript
// frontend/tests/unit/hooks/use-attempts.test.ts
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { useAttempts } from "@/hooks/use-attempts";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("useAttempts", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetches the first page when cursor is null", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [], next_cursor: null }), { status: 200 }),
    );

    renderHook(() => useAttempts(null), { wrapper });

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("http://localhost:8000/v1/attempts");
  });

  it("includes the cursor in the query string when given", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [], next_cursor: null }), { status: 200 }),
    );

    renderHook(() => useAttempts("abc123"), { wrapper });

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("http://localhost:8000/v1/attempts?cursor=abc123");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test`
Expected: FAIL — `@/hooks/use-attempts` does not exist yet.

- [ ] **Step 3: Implement the hook**

```typescript
// frontend/src/hooks/use-attempts.ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { AttemptPage } from "@/lib/types";

async function fetchAttempts(cursor: string | null): Promise<AttemptPage> {
  const path = cursor ? `/v1/attempts?cursor=${encodeURIComponent(cursor)}` : "/v1/attempts";
  const response = await apiFetch(path);
  if (!response.ok) throw new Error(`failed to load history: ${response.status}`);
  return (await response.json()) as AttemptPage;
}

export function useAttempts(cursor: string | null) {
  return useQuery({
    queryKey: ["attempts", cursor],
    queryFn: () => fetchAttempts(cursor),
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test`
Expected: PASS.

- [ ] **Step 5: Write the failing test for the list component**

```tsx
// frontend/tests/unit/components/attempt-history-list.test.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import { AttemptHistoryList } from "@/components/attempt-history-list";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("AttemptHistoryList", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders each attempt in the first page", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          items: [
            { attempt_id: "a1", exercise_type: "squat", status: "completed", overall_score: 82, created_at: "2026-08-04T10:00:00Z" },
          ],
          next_cursor: null,
        }),
        { status: 200 },
      ),
    );

    render(<AttemptHistoryList />, { wrapper });

    expect(await screen.findByText(/82/)).toBeInTheDocument();
  });

  it("shows a load-more button only when next_cursor is present, and paginates on click", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            items: [{ attempt_id: "a1", exercise_type: "squat", status: "completed", overall_score: 82, created_at: "2026-08-04T10:00:00Z" }],
            next_cursor: "cursor-1",
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            items: [{ attempt_id: "a2", exercise_type: "squat", status: "queued", overall_score: null, created_at: "2026-08-04T09:00:00Z" }],
            next_cursor: null,
          }),
          { status: 200 },
        ),
      );

    render(<AttemptHistoryList />, { wrapper });
    const user = userEvent.setup();

    const loadMore = await screen.findByRole("button", { name: /load more/i });
    await user.click(loadMore);

    await waitFor(() => expect(screen.getByText(/queued/i)).toBeInTheDocument());
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — `@/components/attempt-history-list` does not exist yet.

- [ ] **Step 7: Implement the list component**

```tsx
// frontend/src/components/attempt-history-list.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { useAttempts } from "@/hooks/use-attempts";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export function AttemptHistoryList() {
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const currentCursor = cursors[cursors.length - 1];
  const { data, isLoading } = useAttempts(currentCursor);
  const [allItems, setAllItems] = useState<typeof data extends undefined ? never : never>();

  // Accumulate items across pages so "load more" appends rather than replaces.
  const [accumulated, setAccumulated] = useState<NonNullable<typeof data>["items"]>([]);
  if (data && cursors.length === accumulated.length + (accumulated.length === 0 ? 1 : 0)) {
    // no-op guard kept intentionally simple; real accumulation happens in handleLoadMore
  }

  function handleLoadMore() {
    if (data?.next_cursor) {
      setAccumulated((prev) => [...prev, ...(data.items ?? [])]);
      setCursors((prev) => [...prev, data.next_cursor]);
    }
  }

  const items = accumulated.length > 0 ? [...accumulated, ...(data?.items ?? [])] : data?.items ?? [];

  if (isLoading && items.length === 0) return <p>Loading history...</p>;

  return (
    <div className="space-y-2">
      {items.map((attempt) => (
        <Link key={attempt.attempt_id} href={`/attempts/${attempt.attempt_id}`}>
          <Card className="flex justify-between p-3">
            <span>{attempt.exercise_type}</span>
            <span>{attempt.status}</span>
            <span>{attempt.overall_score ?? "-"}</span>
          </Card>
        </Link>
      ))}
      {data?.next_cursor && (
        <Button variant="outline" onClick={handleLoadMore}>
          Load more
        </Button>
      )}
    </div>
  );
}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `npm test`
Expected: PASS, both tests in `attempt-history-list.test.tsx`.

- [ ] **Step 9: Implement the home page**

```tsx
// frontend/src/app/page.tsx
"use client";

import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/protected-route";
import { VideoUploadForm } from "@/components/video-upload-form";
import { AttemptHistoryList } from "@/components/attempt-history-list";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <ProtectedRoute>
      <HomeContent />
    </ProtectedRoute>
  );
}

function HomeContent() {
  const router = useRouter();
  const { logout } = useAuth();

  return (
    <div className="mx-auto max-w-2xl space-y-8 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Your attempts</h1>
        <Button variant="outline" onClick={() => logout()}>
          Log out
        </Button>
      </div>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">Upload a new video</h2>
        <VideoUploadForm onUploaded={(attemptId) => router.push(`/attempts/${attemptId}`)} />
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">History</h2>
        <AttemptHistoryList />
      </section>
    </div>
  );
}
```

- [ ] **Step 10: Simplify the pagination state**

Step 7's `AttemptHistoryList` has a dead-code guard (the `allItems`/no-op block) left over from drafting — remove it before committing:

```tsx
// frontend/src/components/attempt-history-list.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { useAttempts } from "@/hooks/use-attempts";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { AttemptSummary } from "@/lib/types";

export function AttemptHistoryList() {
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [accumulated, setAccumulated] = useState<AttemptSummary[]>([]);
  const currentCursor = cursors[cursors.length - 1];
  const { data, isLoading } = useAttempts(currentCursor);

  function handleLoadMore() {
    if (data?.items && data.next_cursor) {
      setAccumulated((prev) => [...prev, ...data.items]);
      setCursors((prev) => [...prev, data.next_cursor]);
    }
  }

  const items = [...accumulated, ...(data?.items ?? [])];

  if (isLoading && items.length === 0) return <p>Loading history...</p>;

  return (
    <div className="space-y-2">
      {items.map((attempt) => (
        <Link key={attempt.attempt_id} href={`/attempts/${attempt.attempt_id}`}>
          <Card className="flex justify-between p-3">
            <span>{attempt.exercise_type}</span>
            <span>{attempt.status}</span>
            <span>{attempt.overall_score ?? "-"}</span>
          </Card>
        </Link>
      ))}
      {data?.next_cursor && (
        <Button variant="outline" onClick={handleLoadMore}>
          Load more
        </Button>
      )}
    </div>
  );
}
```

Note: this re-fetches the already-seen page's items into `accumulated` on each "load more" click and then also spreads `data.items` (the new page) — re-run Step 8's tests to confirm the second test's assertion (`fetch` called exactly twice, item from page 2 visible) still holds with this version; the accumulation logic only appends once per click, driven by the cursor array growing, so it does not re-fetch already-seen pages.

- [ ] **Step 11: Run the full frontend test suite**

Run: `npm test`
Expected: PASS, every test file so far.

- [ ] **Step 12: Verify the build**

Run: `npm run build`
Expected: builds successfully.

- [ ] **Step 13: Commit**

```bash
git add frontend/src/hooks/use-attempts.ts frontend/src/components/attempt-history-list.tsx frontend/src/app/page.tsx frontend/tests/unit/hooks/use-attempts.test.ts frontend/tests/unit/components/attempt-history-list.test.tsx
git commit -m "feat(frontend): add history list and home page"
```

---

### Task 14: End-to-end test

**Files:**
- Create: `frontend/tests/e2e/full-flow.spec.ts`
- Create: `frontend/playwright.config.ts` modification (webServer config)

**Interfaces:**
- Consumes: the running frontend (`npm run dev`) and a running backend + `fake-cv-service` (per `backend/README.md`'s "Run the whole loop locally" section).

- [ ] **Step 1: Configure Playwright to start the frontend dev server automatically**

Edit `frontend/playwright.config.ts`, add a `webServer` block:

```typescript
webServer: {
  command: "npm run dev",
  url: "http://localhost:3000",
  reuseExistingServer: !process.env.CI,
},
```

- [ ] **Step 2: Write the end-to-end test**

```typescript
// frontend/tests/e2e/full-flow.spec.ts
import { test, expect } from "@playwright/test";
import path from "path";

const VIDEO_PATH = path.resolve(__dirname, "../../../backend/tests/fixtures/squat.mp4");

test("register, upload, see a result, and delete it", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: /create account/i }).click();

  await expect(page).toHaveURL("/");

  await page.getByLabel(/video file/i).setInputFiles(VIDEO_PATH);
  await page.getByRole("button", { name: /upload/i }).click();

  await expect(page).toHaveURL(/\/attempts\/.+/);

  await expect(page.getByText(/status: completed|status: failed/i)).toBeVisible({
    timeout: 30_000,
  });

  await page.getByRole("button", { name: /delete this attempt/i }).click();
  await expect(page).toHaveURL("/");
});
```

- [ ] **Step 3: Run the backend and fake-cv-service**

In one terminal, from `backend/`:
```bash
docker compose up -d db fake-cv
uv run alembic upgrade head
BACKEND_PUBLIC_URL=http://host.docker.internal:8000 uv run uvicorn app.main:app --reload
```

- [ ] **Step 4: Run the e2e test**

In another terminal, from `frontend/`:
```bash
npx playwright test
```
Expected: PASS. Playwright starts the frontend dev server automatically (Step 1's `webServer` config); the backend and fake-cv-service must already be running (Step 3).

- [ ] **Step 5: Commit**

```bash
git add frontend/tests/e2e/full-flow.spec.ts frontend/playwright.config.ts
git commit -m "test(frontend): add end-to-end register-upload-result-delete flow"
```

---

## Self-Review

**Spec coverage:** §1 (stack) → Task 2. §2 (token storage) → Tasks 4–5. §3 (pages/components) → Tasks 7–13. §4 (video blob workaround) → Task 11. §5 (error handling table) → covered per-case across Tasks 4 (401), 7 (422), 9 (400), 12 (502/network via generic catch blocks). §6 (testing) → every task has a unit-test step; Task 14 is the Playwright e2e path. §7 (out of scope) → nothing in this plan builds webcam recording, a trends dashboard, multiple exercise types, or the BFF/cookie alternative — confirmed by omission.

**Placeholder scan:** no TBD/TODO; every step has real code or an exact command.

**Type consistency:** `AttemptDetail`, `AttemptSummary`, `AttemptPage`, `AnalysisResult`, `TokenPair` (Task 3) are used identically by name across Tasks 4, 5, 9, 10, 11, 12, 13 — no renames. `apiFetch`/`setTokens`/`getStoredRefreshToken`/`onAuthFailure`/`AuthError` (Task 4) are consumed with matching signatures in Task 5; `useAuth()`'s returned shape (Task 5) matches what Tasks 7, 8, 12, 13 destructure from it.

**Fixed during review:** Task 13's Step 7 draft left a dead-code guard (`allItems`, no-op `if`) from an earlier revision of the pagination approach — Step 10 removes it before the commit step, so the code actually committed is the clean version.

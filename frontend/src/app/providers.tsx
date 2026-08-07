"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { AuthProvider } from "@/lib/auth-context";
import { AuthError } from "@/lib/api-client";

// Query error messages in this codebase end with ": <status>" for HTTP failures
// (e.g. `failed to load attempt ${attemptId}: ${response.status}`, see use-attempt.ts
// and use-attempts.ts). A 4xx there means the request itself won't succeed on retry
// (404, forbidden, etc.) — don't burn retries/backoff on it.
function isHttp4xxError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const match = /: (\d{3})$/.exec(error.message);
  if (!match) return false;
  const status = Number(match[1]);
  return status >= 400 && status < 500;
}

function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  // AuthError means apiFetch already tried a silent refresh-and-retry and gave up —
  // retrying again here can't succeed, and the auth-failure signal has already fired.
  if (error instanceof AuthError) return false;
  if (isHttp4xxError(error)) return false;
  // Other failures (network blips, 5xx) are more likely transient — allow a couple
  // of retries, short of TanStack Query's default of 3.
  return failureCount < 2;
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: shouldRetryQuery,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}

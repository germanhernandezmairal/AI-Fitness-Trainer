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

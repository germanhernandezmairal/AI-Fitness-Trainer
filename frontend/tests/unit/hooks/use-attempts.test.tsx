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

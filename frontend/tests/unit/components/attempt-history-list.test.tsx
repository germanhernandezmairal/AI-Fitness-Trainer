import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
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
    cleanup();
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

  it("shows an error message when the history fails to load", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response("Internal Server Error", { status: 500 }));

    render(<AttemptHistoryList />, { wrapper });

    expect(await screen.findByText(/could not load your attempt history/i)).toBeInTheDocument();
  });

  it("gives each status a distinct pill style", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          items: [
            { attempt_id: "a1", exercise_type: "squat", status: "completed", overall_score: 82, created_at: "2026-08-04T10:00:00Z" },
            { attempt_id: "a2", exercise_type: "squat", status: "failed", overall_score: null, created_at: "2026-08-04T09:00:00Z" },
          ],
          next_cursor: null,
        }),
        { status: 200 },
      ),
    );

    render(<AttemptHistoryList />, { wrapper });

    const completedPill = await screen.findByText("completed");
    const failedPill = screen.getByText("failed");

    expect(completedPill.className).toContain("text-primary");
    expect(failedPill.className).toContain("text-destructive");
  });
});

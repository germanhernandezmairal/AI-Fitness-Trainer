import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@tanstack/react-query", () => ({ useQueryClient: () => ({ invalidateQueries: vi.fn() }) }));
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ isAuthenticated: true, isLoading: false, logout: vi.fn() }),
}));
vi.mock("@/hooks/use-attempt", () => ({
  useAttempt: () => ({ data: undefined, isLoading: true, error: null }),
}));

import { AttemptDetailContent } from "@/app/attempts/[id]/page";

describe("AttemptDetailPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the AppShell wordmark even while the attempt is loading", () => {
    render(<AttemptDetailContent attemptId="a1" />);

    expect(screen.getByText("AI Fitness Trainer")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
  });
});

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

const mockLogout = vi.fn();
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ logout: mockLogout }) }));

import { AppShell } from "@/components/app-shell";

describe("AppShell", () => {
  afterEach(() => {
    cleanup();
    mockLogout.mockReset();
  });

  it("renders the wordmark and its children", () => {
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );

    expect(screen.getByText("AI Fitness Trainer")).toBeInTheDocument();
    expect(screen.getByText("page content")).toBeInTheDocument();
  });

  it("calls logout when the Log out button is clicked", async () => {
    mockLogout.mockResolvedValueOnce(undefined);
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /log out/i }));

    expect(mockLogout).toHaveBeenCalled();
  });
});

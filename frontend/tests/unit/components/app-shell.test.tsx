import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

const mockLogout = vi.fn();
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ logout: mockLogout }) }));

const mockSetTheme = vi.fn();
let mockResolvedTheme = "light";
vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: mockResolvedTheme, setTheme: mockSetTheme }),
}));

import { AppShell } from "@/components/app-shell";

describe("AppShell", () => {
  afterEach(() => {
    cleanup();
    mockLogout.mockReset();
    mockSetTheme.mockReset();
    mockResolvedTheme = "light";
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

  it("links the wordmark back to /", () => {
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );

    expect(screen.getByRole("link", { name: "AI Fitness Trainer" })).toHaveAttribute(
      "href",
      "/",
    );
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

  it("renders a theme toggle button", () => {
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );

    expect(screen.getByRole("button", { name: /toggle theme/i })).toBeInTheDocument();
  });

  it("switches to dark when toggled while the resolved theme is light", async () => {
    mockResolvedTheme = "light";
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /toggle theme/i }));

    expect(mockSetTheme).toHaveBeenCalledWith("dark");
  });

  it("switches to light when toggled while the resolved theme is dark", async () => {
    mockResolvedTheme = "dark";
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /toggle theme/i }));

    expect(mockSetTheme).toHaveBeenCalledWith("light");
  });
});

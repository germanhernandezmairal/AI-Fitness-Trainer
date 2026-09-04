import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

const mockLogout = vi.fn();
const mockDeleteAccount = vi.fn();
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ logout: mockLogout, deleteAccount: mockDeleteAccount }),
}));

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mockPush }) }));

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
    mockDeleteAccount.mockReset();
    mockPush.mockReset();
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

  it("does not call deleteAccount until DELETE is typed to confirm", async () => {
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /delete account/i }));
    await user.click(screen.getByRole("button", { name: /confirm/i }));

    expect(mockDeleteAccount).not.toHaveBeenCalled();
  });

  it("deletes the account and redirects to /login once DELETE is typed", async () => {
    mockDeleteAccount.mockResolvedValueOnce(undefined);
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /delete account/i }));
    await user.type(screen.getByLabelText(/type delete to confirm/i), "DELETE");
    await user.click(screen.getByRole("button", { name: /confirm/i }));

    expect(mockDeleteAccount).toHaveBeenCalled();
    await vi.waitFor(() => expect(mockPush).toHaveBeenCalledWith("/login"));
  });

  it("cancels the confirmation without deleting", async () => {
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /delete account/i }));
    await user.click(screen.getByRole("button", { name: /cancel/i }));

    expect(screen.queryByLabelText(/type delete to confirm/i)).not.toBeInTheDocument();
    expect(mockDeleteAccount).not.toHaveBeenCalled();
  });
});

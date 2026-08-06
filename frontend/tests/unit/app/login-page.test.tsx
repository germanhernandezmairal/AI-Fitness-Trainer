import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mockPush }) }));

const mockLogin = vi.fn();
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ login: mockLogin }) }));

import LoginPage from "@/app/login/page";

describe("LoginPage", () => {
  beforeEach(() => {
    mockLogin.mockReset();
    mockPush.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

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

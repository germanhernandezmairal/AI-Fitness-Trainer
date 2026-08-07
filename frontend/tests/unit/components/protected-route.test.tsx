import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mockPush }) }));

const mockUseAuth = vi.fn();
vi.mock("@/lib/auth-context", () => ({ useAuth: () => mockUseAuth() }));

import { ProtectedRoute } from "@/components/protected-route";

describe("ProtectedRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

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

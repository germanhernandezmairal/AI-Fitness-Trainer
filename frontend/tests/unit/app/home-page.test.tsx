import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ isAuthenticated: true, isLoading: false, logout: vi.fn() }),
}));
vi.mock("@/components/video-upload-form", () => ({
  VideoUploadForm: () => <div>upload form</div>,
}));
vi.mock("@/components/attempt-history-list", () => ({
  AttemptHistoryList: () => <div>history list</div>,
}));

import HomePage from "@/app/page";

describe("HomePage", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the AppShell wordmark, page title, and both sections", () => {
    render(<HomePage />);

    expect(screen.getByText("AI Fitness Trainer")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /your attempts/i })).toBeInTheDocument();
    expect(screen.getByText("upload form")).toBeInTheDocument();
    expect(screen.getByText("history list")).toBeInTheDocument();
  });

  it("renders a working log out control", () => {
    render(<HomePage />);

    expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
  });
});

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import PrivacyPage from "@/app/privacy/page";

describe("PrivacyPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the policy heading", () => {
    render(<PrivacyPage />);

    expect(screen.getByRole("heading", { name: /privacy policy/i })).toBeInTheDocument();
  });

  it("states the 30-day retention period", () => {
    render(<PrivacyPage />);

    expect(screen.getByText(/30 days/i)).toBeInTheDocument();
  });

  it("names both erasure options", () => {
    render(<PrivacyPage />);

    expect(screen.getByText(/delete a single analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/delete your entire account/i)).toBeInTheDocument();
  });
});

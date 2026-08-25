import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AnalysisResult } from "@/lib/types";

vi.mock("@/hooks/use-attempt-video", () => ({
  useAttemptVideo: () => ({ blobUrl: "blob:mock-url", isLoading: false, error: null }),
}));

import { AttemptResult } from "@/components/attempt-result";

const RESULT: AnalysisResult = {
  exercise_type: "squat",
  overall_score: 82,
  summary: "Good depth overall.",
  rep_count: 1,
  reps: [
    {
      rep_index: 1,
      start_time_sec: 0,
      end_time_sec: 2,
      min_knee_angle_deg: 78,
      score: 90,
      errors: ["knee_valgus"],
    },
  ],
  annotated_video_url: "http://localhost:8000/v1/attempts/a1/video",
  algorithm_version: "squat-rules-v1",
};

describe("AttemptResult", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows the overall score and summary", () => {
    render(<AttemptResult result={RESULT} />);

    expect(screen.getByText(/82/)).toBeInTheDocument();
    expect(screen.getByText(/good depth overall/i)).toBeInTheDocument();
  });

  it("lists each rep with its score", () => {
    render(<AttemptResult result={RESULT} />);

    expect(screen.getByText(/rep 1/i)).toBeInTheDocument();
    expect(screen.getByText(/90/)).toBeInTheDocument();
  });

  it("renders the annotated video using the blob URL from useAttemptVideo", () => {
    render(<AttemptResult result={RESULT} />);

    const video = screen.getByTestId("annotated-video") as HTMLVideoElement;
    expect(video.src).toBe("blob:mock-url");
  });

  it("shows human-readable copy for a rep's form errors", () => {
    render(<AttemptResult result={RESULT} />);

    expect(screen.getByText(/knees caving in/i)).toBeInTheDocument();
  });

  it("does not render an errors section for a rep with no errors", () => {
    const clean: AnalysisResult = {
      ...RESULT,
      reps: [{ ...RESULT.reps[0], errors: [] }],
    };
    render(<AttemptResult result={clean} />);

    expect(screen.queryByText(/knees caving in/i)).not.toBeInTheDocument();
  });

  it("shows an eyebrow label above the overall score", () => {
    render(<AttemptResult result={RESULT} />);

    expect(screen.getByText(/overall score/i)).toBeInTheDocument();
  });

  it("gives per-rep scores the same eyebrow/display type-scale as the overall score", () => {
    render(<AttemptResult result={RESULT} />);

    const repLabel = screen.getByText(/rep 1/i);
    expect(repLabel.className).toContain("text-[11px]");
    expect(repLabel.className).toContain("uppercase");
    expect(repLabel.className).toContain("tracking-wide");

    const repScore = screen.getByText(/90/);
    expect(repScore.className).toContain("font-bold");
    expect(repScore.className.split(" ")).toContain("text-primary-text");
    expect(repScore.className.split(" ")).not.toContain("text-primary");
  });
});

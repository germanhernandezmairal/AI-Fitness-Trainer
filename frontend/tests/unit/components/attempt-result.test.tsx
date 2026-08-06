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
});

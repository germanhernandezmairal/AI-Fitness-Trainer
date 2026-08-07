import { describe, expect, it } from "vitest";
import { failureMessage } from "@/lib/failure-messages";
import type { FailureCode } from "@/lib/types";

describe("failureMessage", () => {
  const codes: FailureCode[] = [
    "no_pose_detected",
    "low_pose_confidence",
    "no_movement_detected",
    "storage_error",
    "worker_error",
  ];

  it.each(codes)("returns a non-empty message for %s", (code) => {
    expect(failureMessage(code).length).toBeGreaterThan(0);
  });

  it("returns distinct messages for each code", () => {
    const messages = new Set(codes.map(failureMessage));
    expect(messages.size).toBe(codes.length);
  });
});

import type { FailureCode } from "@/lib/types";

const MESSAGES: Record<FailureCode, string> = {
  no_pose_detected: "We couldn't detect a person in the video.",
  low_pose_confidence: "The video quality made it hard to analyze your form clearly.",
  no_movement_detected: "No squat movement was detected in the video.",
  storage_error: "Something went wrong storing your video. Try again.",
  worker_error: "Something went wrong analyzing your video. Try again.",
};

export function failureMessage(code: FailureCode): string {
  return MESSAGES[code];
}

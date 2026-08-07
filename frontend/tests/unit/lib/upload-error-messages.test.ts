import { describe, expect, it } from "vitest";
import { uploadErrorMessage } from "@/lib/upload-error-messages";
import type { UploadErrorCode } from "@/lib/types";

describe("uploadErrorMessage", () => {
  const codes: UploadErrorCode[] = [
    "unsupported_format",
    "file_too_large",
    "video_too_long",
    "unknown_exercise_type",
  ];

  it.each(codes)("returns a non-empty message for %s", (code) => {
    expect(uploadErrorMessage(code).length).toBeGreaterThan(0);
  });

  it("returns distinct messages for each code", () => {
    const messages = new Set(codes.map(uploadErrorMessage));
    expect(messages.size).toBe(codes.length);
  });
});

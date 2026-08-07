import { describe, expect, it } from "vitest";
import { formErrorMessage } from "@/lib/form-error-messages";
import type { FormErrorCode } from "@/lib/types";

describe("formErrorMessage", () => {
  const codes: FormErrorCode[] = [
    "knee_valgus",
    "insufficient_depth",
    "excessive_forward_lean",
  ];

  it.each(codes)("returns a non-empty message for %s", (code) => {
    expect(formErrorMessage(code).length).toBeGreaterThan(0);
  });

  it("returns distinct messages for each code", () => {
    const messages = new Set(codes.map(formErrorMessage));
    expect(messages.size).toBe(codes.length);
  });
});

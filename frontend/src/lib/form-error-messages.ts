import type { FormErrorCode } from "@/lib/types";

const MESSAGES: Record<FormErrorCode, string> = {
  knee_valgus: "Knees caving in",
  insufficient_depth: "Didn't squat deep enough",
  excessive_forward_lean: "Leaning too far forward",
};

export function formErrorMessage(code: FormErrorCode): string {
  return MESSAGES[code];
}

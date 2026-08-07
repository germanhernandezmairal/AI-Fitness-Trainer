import type { UploadErrorCode } from "@/lib/types";

const MESSAGES: Record<UploadErrorCode, string> = {
  unsupported_format: "That file format isn't supported. Upload an MP4 or MOV video.",
  file_too_large: "That video is too large. The limit is 100 MB.",
  video_too_long: "That video is too long. The limit is 60 seconds.",
  unknown_exercise_type: "That exercise type isn't supported yet.",
};

export function uploadErrorMessage(code: UploadErrorCode): string {
  return MESSAGES[code];
}

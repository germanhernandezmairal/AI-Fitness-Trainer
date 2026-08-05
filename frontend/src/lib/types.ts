export type AttemptStatus = "queued" | "processing" | "completed" | "failed";

export type FormErrorCode =
  | "knee_valgus"
  | "insufficient_depth"
  | "excessive_forward_lean";

export type FailureCode =
  | "no_pose_detected"
  | "low_pose_confidence"
  | "no_movement_detected"
  | "storage_error"
  | "worker_error";

export type UploadErrorCode =
  | "unsupported_format"
  | "file_too_large"
  | "video_too_long"
  | "unknown_exercise_type";

export interface RepResult {
  rep_index: number;
  start_time_sec: number;
  end_time_sec: number;
  min_knee_angle_deg: number;
  score: number;
  errors: FormErrorCode[];
}

export interface AnalysisResult {
  exercise_type: "squat";
  overall_score: number;
  summary: string;
  rep_count: number;
  reps: RepResult[];
  annotated_video_url: string | null;
  algorithm_version: string;
}

export interface ErrorPayload {
  code: FailureCode;
  message: string;
}

export interface AttemptCreated {
  attempt_id: string;
  status: AttemptStatus;
}

export interface AttemptDetail {
  attempt_id: string;
  exercise_type: string;
  status: AttemptStatus;
  created_at: string;
  completed_at: string | null;
  result: AnalysisResult | null;
  error: ErrorPayload | null;
}

export interface AttemptSummary {
  attempt_id: string;
  exercise_type: string;
  status: AttemptStatus;
  overall_score: number | null;
  created_at: string;
}

export interface AttemptPage {
  items: AttemptSummary[];
  next_cursor: string | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UploadErrorResponse {
  error: {
    code: UploadErrorCode;
    message: string;
  };
}

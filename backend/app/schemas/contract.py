"""The shared backend <-> CV service contract (spec §5, §6).

Both sides of the internal boundary validate against this module. Changing anything
here is a contract change and must be agreed with the CV service author.
"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AttemptStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in (AttemptStatus.COMPLETED, AttemptStatus.FAILED)


class ExerciseType(StrEnum):
    SQUAT = "squat"


class FormErrorCode(StrEnum):
    """Per-rep technique errors (spec §6a). Extensible per exercise."""

    KNEE_VALGUS = "knee_valgus"
    INSUFFICIENT_DEPTH = "insufficient_depth"
    EXCESSIVE_FORWARD_LEAN = "excessive_forward_lean"


class FailureCode(StrEnum):
    """Job failure codes (spec §6b)."""

    NO_POSE_DETECTED = "no_pose_detected"
    LOW_POSE_CONFIDENCE = "low_pose_confidence"
    NO_MOVEMENT_DETECTED = "no_movement_detected"
    STORAGE_ERROR = "storage_error"
    WORKER_ERROR = "worker_error"

    @property
    def is_retryable(self) -> bool:
        """Content errors mean the user re-records; system errors are retried."""
        return self in (FailureCode.STORAGE_ERROR, FailureCode.WORKER_ERROR)


class UploadErrorCode(StrEnum):
    """Backend-side upload rejections, HTTP 400 (spec §6c)."""

    UNSUPPORTED_FORMAT = "unsupported_format"
    FILE_TOO_LARGE = "file_too_large"
    VIDEO_TOO_LONG = "video_too_long"
    UNKNOWN_EXERCISE_TYPE = "unknown_exercise_type"


class RepResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rep_index: int
    start_time_sec: float
    end_time_sec: float
    min_knee_angle_deg: float
    score: int = Field(ge=0, le=100)
    errors: list[FormErrorCode] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_type: ExerciseType
    overall_score: int = Field(ge=0, le=100)
    summary: str
    rep_count: int = Field(ge=0)
    reps: list[RepResult] = Field(default_factory=list)
    annotated_video_url: str | None = None
    algorithm_version: str


class ErrorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: FailureCode
    message: str


class JobAccepted(BaseModel):
    """202 response from POST /v1/jobs."""

    model_config = ConfigDict(extra="ignore")

    job_id: str
    status: AttemptStatus


class JobStatus(BaseModel):
    """GET /v1/jobs/{id} response and the webhook callback body."""

    model_config = ConfigDict(extra="ignore")

    status: AttemptStatus
    result: AnalysisResult | None = None
    error: ErrorPayload | None = None

    @model_validator(mode="after")
    def check_payload_matches_status(self) -> Self:
        if self.status is AttemptStatus.COMPLETED and self.result is None:
            raise ValueError("a completed job must carry a result")
        if self.status is AttemptStatus.FAILED and self.error is None:
            raise ValueError("a failed job must carry an error")
        return self

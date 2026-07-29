from dataclasses import dataclass
from pathlib import Path

import av

from app.config import Settings
from app.schemas.contract import ExerciseType, UploadErrorCode

ALLOWED_EXTENSIONS = {".mp4", ".mov"}


class UploadValidationError(Exception):
    """Rejected before a CV job is created. Maps to HTTP 400 (spec §6c)."""

    def __init__(self, code: UploadErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class VideoInfo:
    duration_sec: float
    container: str
    video_codec: str


def probe_video(path: Path) -> VideoInfo:
    try:
        with av.open(str(path)) as container:
            streams = container.streams.video
            if not streams:
                raise UploadValidationError(
                    UploadErrorCode.UNSUPPORTED_FORMAT, "file contains no video stream"
                )
            duration = float(container.duration) / 1_000_000 if container.duration else 0.0
            return VideoInfo(
                duration_sec=duration,
                container=container.format.name,
                video_codec=streams[0].codec_context.name,
            )
    except UploadValidationError:
        raise
    except Exception as exc:
        raise UploadValidationError(
            UploadErrorCode.UNSUPPORTED_FORMAT, f"could not decode the video: {exc}"
        ) from exc


def validate_upload(
    path: Path,
    filename: str,
    exercise_type: str,
    size_bytes: int,
    settings: Settings,
) -> ExerciseType:
    """Checks run cheapest-first so the reported code is the most useful one."""
    try:
        exercise = ExerciseType(exercise_type)
    except ValueError:
        raise UploadValidationError(
            UploadErrorCode.UNKNOWN_EXERCISE_TYPE, f"unknown exercise type {exercise_type!r}"
        ) from None

    if size_bytes > settings.max_upload_bytes:
        raise UploadValidationError(
            UploadErrorCode.FILE_TOO_LARGE,
            f"{size_bytes} bytes exceeds the {settings.max_upload_bytes} byte limit",
        )

    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            UploadErrorCode.UNSUPPORTED_FORMAT, "only MP4 and MOV uploads are accepted"
        )

    info = probe_video(path)
    if info.duration_sec > settings.max_duration_sec:
        raise UploadValidationError(
            UploadErrorCode.VIDEO_TOO_LONG,
            f"{info.duration_sec:.1f}s exceeds the {settings.max_duration_sec}s limit",
        )

    return exercise

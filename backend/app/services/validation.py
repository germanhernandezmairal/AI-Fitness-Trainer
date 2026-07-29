from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import av

from app.config import Settings
from app.schemas.contract import ExerciseType, UploadErrorCode

ALLOWED_EXTENSIONS = {".mp4", ".mov"}
ALLOWED_VIDEO_CODECS = {"h264"}


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


def _resolve_duration_sec(
    container_duration_us: int | None,
    stream_duration: int | None,
    stream_time_base: Fraction | None,
) -> float | None:
    """Container duration (microseconds) first; falls back to the video stream's own
    duration (in its time_base), which fragmented files often still report even when
    the container omits an overall duration. Returns None if neither is known --
    callers must not score that as 0 seconds, since that would silently pass any
    duration cap.
    """
    if container_duration_us:
        return float(container_duration_us) / 1_000_000
    if stream_duration is not None and stream_time_base is not None:
        return float(stream_duration * stream_time_base)
    return None


def probe_video(path: Path) -> VideoInfo:
    try:
        with av.open(str(path)) as container:
            streams = container.streams.video
            if not streams:
                raise UploadValidationError(
                    UploadErrorCode.UNSUPPORTED_FORMAT, "file contains no video stream"
                )
            stream = streams[0]
            duration = _resolve_duration_sec(
                container.duration, stream.duration, stream.time_base
            )
            if duration is None:
                raise UploadValidationError(
                    UploadErrorCode.UNSUPPORTED_FORMAT,
                    "could not determine the video duration",
                )
            return VideoInfo(
                duration_sec=duration,
                container=container.format.name,
                video_codec=stream.codec_context.name,
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

    if info.video_codec not in ALLOWED_VIDEO_CODECS:
        raise UploadValidationError(
            UploadErrorCode.UNSUPPORTED_FORMAT,
            f"unsupported video codec {info.video_codec!r}",
        )

    if info.duration_sec > settings.max_duration_sec:
        raise UploadValidationError(
            UploadErrorCode.VIDEO_TOO_LONG,
            f"{info.duration_sec:.1f}s exceeds the {settings.max_duration_sec}s limit",
        )

    return exercise

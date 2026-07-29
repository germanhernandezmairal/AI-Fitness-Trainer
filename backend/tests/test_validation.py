from pathlib import Path

import pytest

from app.config import Settings
from app.schemas.contract import ExerciseType, UploadErrorCode
from app.services.validation import UploadValidationError, probe_video, validate_upload

FIXTURES = Path(__file__).parent / "fixtures"
SQUAT = FIXTURES / "squat.mp4"


@pytest.fixture
def limits() -> Settings:
    return Settings(max_upload_bytes=104_857_600, max_duration_sec=60)


def test_probes_a_real_mp4():
    info = probe_video(SQUAT)

    assert "mp4" in info.container
    assert info.duration_sec > 0


def test_accepts_a_valid_squat_upload(limits):
    exercise = validate_upload(
        SQUAT, "squat.mp4", "squat", size_bytes=SQUAT.stat().st_size, settings=limits
    )

    assert exercise is ExerciseType.SQUAT


def test_rejects_an_unknown_exercise_type(limits):
    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(
            SQUAT, "squat.mp4", "backflip", size_bytes=SQUAT.stat().st_size, settings=limits
        )

    assert excinfo.value.code is UploadErrorCode.UNKNOWN_EXERCISE_TYPE


def test_rejects_an_unsupported_extension(limits):
    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(SQUAT, "clip.avi", "squat", size_bytes=1000, settings=limits)

    assert excinfo.value.code is UploadErrorCode.UNSUPPORTED_FORMAT


def test_rejects_a_file_that_is_not_a_video(tmp_path, limits):
    fake = tmp_path / "fake.mp4"
    fake.write_bytes(b"this is definitely not a video")

    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(fake, "fake.mp4", "squat", size_bytes=fake.stat().st_size, settings=limits)

    assert excinfo.value.code is UploadErrorCode.UNSUPPORTED_FORMAT


def test_rejects_an_oversized_file(limits):
    small_limit = limits.model_copy(update={"max_upload_bytes": 100})

    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(SQUAT, "squat.mp4", "squat", size_bytes=5000, settings=small_limit)

    assert excinfo.value.code is UploadErrorCode.FILE_TOO_LARGE


def test_rejects_a_too_long_video(limits):
    short_limit = limits.model_copy(update={"max_duration_sec": 1})

    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(
            SQUAT, "squat.mp4", "squat", size_bytes=SQUAT.stat().st_size, settings=short_limit
        )

    assert excinfo.value.code is UploadErrorCode.VIDEO_TOO_LONG


def test_size_is_checked_before_the_expensive_probe(limits, tmp_path):
    """An oversized file must be rejected without decoding it."""
    junk = tmp_path / "huge.mp4"
    junk.write_bytes(b"not a video at all")
    small_limit = limits.model_copy(update={"max_upload_bytes": 5})

    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(junk, "huge.mp4", "squat", size_bytes=1000, settings=small_limit)

    assert excinfo.value.code is UploadErrorCode.FILE_TOO_LARGE

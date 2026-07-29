from fractions import Fraction
from pathlib import Path

import av
import pytest

from app.config import Settings
from app.schemas.contract import ExerciseType, UploadErrorCode
from app.services.validation import (
    UploadValidationError,
    _resolve_duration_sec,
    probe_video,
    validate_upload,
)

FIXTURES = Path(__file__).parent / "fixtures"
SQUAT = FIXTURES / "squat.mp4"


def _make_mpeg4_clip(path: Path) -> None:
    """A tiny, real, decodable video encoded with mpeg4 (not h264) so the codec
    rejection can be exercised without a second binary fixture."""
    container = av.open(str(path), mode="w")
    stream = container.add_stream("mpeg4", rate=24)
    stream.width = 32
    stream.height = 32
    stream.pix_fmt = "yuv420p"
    for _ in range(5):
        frame = av.VideoFrame(32, 32, "yuv420p")
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


@pytest.fixture
def limits() -> Settings:
    return Settings(max_upload_bytes=104_857_600, max_duration_sec=60)


def test_probes_a_real_mp4():
    info = probe_video(SQUAT)

    assert "mp4" in info.container
    assert info.duration_sec > 0
    assert info.video_codec == "h264"


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


def test_rejects_a_non_h264_video_codec(limits, tmp_path):
    """MP4 container, but the wrong video codec inside it -- must still be rejected."""
    clip = tmp_path / "mpeg4_clip.mp4"
    _make_mpeg4_clip(clip)

    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(
            clip, "mpeg4_clip.mp4", "squat", size_bytes=clip.stat().st_size, settings=limits
        )

    assert excinfo.value.code is UploadErrorCode.UNSUPPORTED_FORMAT


def test_resolve_duration_prefers_the_container_duration():
    assert _resolve_duration_sec(2_000_000, 999, Fraction(1, 90_000)) == 2.0


def test_resolve_duration_falls_back_to_the_stream_duration():
    result = _resolve_duration_sec(None, 2560, Fraction(1, 12_288))

    assert result == pytest.approx(2560 / 12_288)


def test_resolve_duration_returns_none_when_both_are_missing():
    assert _resolve_duration_sec(None, None, None) is None

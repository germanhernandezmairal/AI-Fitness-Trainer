import pytest
from pydantic import ValidationError

from app.schemas.contract import (
    AnalysisResult,
    AttemptStatus,
    FailureCode,
    FormErrorCode,
    JobStatus,
)

SPEC_RESULT = {
    "exercise_type": "squat",
    "overall_score": 82,
    "summary": "Good depth overall, but knees collapse inward on 2 of 5 reps.",
    "rep_count": 5,
    "reps": [
        {
            "rep_index": 1,
            "start_time_sec": 2.1,
            "end_time_sec": 5.4,
            "min_knee_angle_deg": 78,
            "score": 90,
            "errors": [],
        },
        {
            "rep_index": 2,
            "start_time_sec": 6.0,
            "end_time_sec": 9.1,
            "min_knee_angle_deg": 65,
            "score": 60,
            "errors": ["knee_valgus", "insufficient_depth"],
        },
    ],
    "annotated_video_url": "https://cv-storage/x/annotated.mp4",
    "algorithm_version": "squat-rules-v1",
}


def test_parses_the_spec_example_verbatim():
    result = AnalysisResult.model_validate(SPEC_RESULT)

    assert result.overall_score == 82
    assert result.rep_count == 5
    assert result.reps[1].errors == [
        FormErrorCode.KNEE_VALGUS,
        FormErrorCode.INSUFFICIENT_DEPTH,
    ]
    assert result.algorithm_version == "squat-rules-v1"


def test_rejects_a_form_error_outside_the_closed_catalog():
    payload = {**SPEC_RESULT, "reps": [{**SPEC_RESULT["reps"][0], "errors": ["made_up_error"]}]}

    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(payload)


def test_parses_the_completed_job_status():
    status = JobStatus.model_validate({"status": "completed", "result": SPEC_RESULT})

    assert status.status is AttemptStatus.COMPLETED
    assert status.result is not None
    assert status.error is None


def test_parses_the_spec_failure_shape():
    status = JobStatus.model_validate(
        {"status": "failed", "error": {"code": "no_pose_detected", "message": "no human in frame"}}
    )

    assert status.status is AttemptStatus.FAILED
    assert status.error is not None
    assert status.error.code is FailureCode.NO_POSE_DETECTED
    assert status.result is None


def test_rejects_a_failure_code_outside_the_closed_catalog():
    with pytest.raises(ValidationError):
        JobStatus.model_validate(
            {"status": "failed", "error": {"code": "kaboom", "message": "x"}}
        )


def test_completed_status_requires_a_result():
    with pytest.raises(ValidationError):
        JobStatus.model_validate({"status": "completed", "result": None})


def test_failed_status_requires_an_error():
    with pytest.raises(ValidationError):
        JobStatus.model_validate({"status": "failed", "error": None})


def test_failure_codes_declare_whether_they_are_retryable():
    assert FailureCode.WORKER_ERROR.is_retryable is True
    assert FailureCode.STORAGE_ERROR.is_retryable is True
    assert FailureCode.NO_POSE_DETECTED.is_retryable is False
    assert FailureCode.LOW_POSE_CONFIDENCE.is_retryable is False
    assert FailureCode.NO_MOVEMENT_DETECTED.is_retryable is False

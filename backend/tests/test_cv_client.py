import io

import httpx
import pytest
import respx

from app.schemas.contract import AttemptStatus, FailureCode
from app.services.cv_client import CVClient, CVServiceError

BASE = "http://cv.test"
API_KEY = "secret-api-key"

RESULT = {
    "exercise_type": "squat",
    "overall_score": 82,
    "summary": "Good depth.",
    "rep_count": 1,
    "reps": [
        {
            "rep_index": 1,
            "start_time_sec": 0.0,
            "end_time_sec": 2.0,
            "min_knee_angle_deg": 78,
            "score": 90,
            "errors": [],
        }
    ],
    "annotated_video_url": "https://cv-storage/x/annotated.mp4",
    "algorithm_version": "squat-rules-v1",
}


@pytest.fixture
async def cv_client():
    async with httpx.AsyncClient() as http:
        yield CVClient(base_url=BASE, api_key=API_KEY, http=http)


@respx.mock
async def test_submit_job_posts_multipart_with_the_api_key(cv_client):
    route = respx.post(f"{BASE}/v1/jobs").mock(
        return_value=httpx.Response(202, json={"job_id": "job-1", "status": "queued"})
    )

    accepted = await cv_client.submit_job(
        video=io.BytesIO(b"bytes"),
        filename="squat.mp4",
        exercise_type="squat",
        callback_url="http://backend/v1/cv-callback/xyz",
    )

    assert accepted.job_id == "job-1"
    assert accepted.status is AttemptStatus.QUEUED
    request = route.calls.last.request
    assert request.headers["X-API-Key"] == API_KEY
    body = request.content
    assert b"squat.mp4" in body
    assert b"http://backend/v1/cv-callback/xyz" in body


@respx.mock
async def test_submit_job_raises_on_a_server_error(cv_client):
    respx.post(f"{BASE}/v1/jobs").mock(return_value=httpx.Response(503, text="down"))

    with pytest.raises(CVServiceError) as excinfo:
        await cv_client.submit_job(
            video=io.BytesIO(b"bytes"),
            filename="squat.mp4",
            exercise_type="squat",
            callback_url="http://backend/cb",
        )

    assert excinfo.value.status_code == 503


@respx.mock
async def test_submit_job_raises_when_the_service_is_unreachable(cv_client):
    respx.post(f"{BASE}/v1/jobs").mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(CVServiceError):
        await cv_client.submit_job(
            video=io.BytesIO(b"bytes"),
            filename="squat.mp4",
            exercise_type="squat",
            callback_url="http://backend/cb",
        )


@respx.mock
async def test_submit_job_raises_on_a_malformed_200_response(cv_client):
    respx.post(f"{BASE}/v1/jobs").mock(
        return_value=httpx.Response(200, json={"unexpected": "shape"})
    )

    with pytest.raises(CVServiceError):
        await cv_client.submit_job(
            video=io.BytesIO(b"bytes"),
            filename="squat.mp4",
            exercise_type="squat",
            callback_url="http://backend/cb",
        )


@respx.mock
async def test_submit_job_sends_the_content_type_for_a_mov_upload(cv_client):
    route = respx.post(f"{BASE}/v1/jobs").mock(
        return_value=httpx.Response(202, json={"job_id": "job-1", "status": "queued"})
    )

    await cv_client.submit_job(
        video=io.BytesIO(b"bytes"),
        filename="squat.mov",
        exercise_type="squat",
        callback_url="http://backend/cb",
    )

    body = route.calls.last.request.content
    assert b"video/quicktime" in body


@respx.mock
async def test_submit_job_sends_the_content_type_for_an_mp4_upload(cv_client):
    route = respx.post(f"{BASE}/v1/jobs").mock(
        return_value=httpx.Response(202, json={"job_id": "job-1", "status": "queued"})
    )

    await cv_client.submit_job(
        video=io.BytesIO(b"bytes"),
        filename="squat.mp4",
        exercise_type="squat",
        callback_url="http://backend/cb",
    )

    body = route.calls.last.request.content
    assert b"video/mp4" in body


@respx.mock
async def test_get_job_parses_a_completed_result(cv_client):
    respx.get(f"{BASE}/v1/jobs/job-1").mock(
        return_value=httpx.Response(200, json={"status": "completed", "result": RESULT})
    )

    status = await cv_client.get_job("job-1")

    assert status.status is AttemptStatus.COMPLETED
    assert status.result is not None
    assert status.result.overall_score == 82


@respx.mock
async def test_get_job_parses_a_failure(cv_client):
    respx.get(f"{BASE}/v1/jobs/job-2").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "failed",
                "error": {"code": "no_pose_detected", "message": "empty frame"},
            },
        )
    )

    status = await cv_client.get_job("job-2")

    assert status.status is AttemptStatus.FAILED
    assert status.error is not None
    assert status.error.code is FailureCode.NO_POSE_DETECTED


@respx.mock
async def test_get_job_raises_on_a_malformed_200_response(cv_client):
    respx.get(f"{BASE}/v1/jobs/job-3").mock(
        return_value=httpx.Response(200, json={"status": "completed"})  # missing result
    )

    with pytest.raises(CVServiceError):
        await cv_client.get_job("job-3")


@respx.mock
async def test_delete_job_sends_delete(cv_client):
    route = respx.delete(f"{BASE}/v1/jobs/job-1").mock(return_value=httpx.Response(204))

    await cv_client.delete_job("job-1")

    assert route.called
    assert route.calls.last.request.headers["X-API-Key"] == API_KEY


@respx.mock
async def test_delete_job_tolerates_an_already_deleted_job(cv_client):
    respx.delete(f"{BASE}/v1/jobs/gone").mock(return_value=httpx.Response(404))

    await cv_client.delete_job("gone")  # must not raise


@respx.mock
async def test_delete_job_raises_on_a_server_error(cv_client):
    respx.delete(f"{BASE}/v1/jobs/job-1").mock(return_value=httpx.Response(500))

    with pytest.raises(CVServiceError):
        await cv_client.delete_job("job-1")


@respx.mock
async def test_get_video_returns_content_and_type_with_the_api_key(cv_client):
    route = respx.get(f"{BASE}/v1/jobs/job-1/video").mock(
        return_value=httpx.Response(200, content=b"bytes", headers={"content-type": "video/mp4"})
    )

    content, content_type = await cv_client.get_video("job-1")

    assert content == b"bytes"
    assert content_type == "video/mp4"
    assert route.calls.last.request.headers["X-API-Key"] == API_KEY


@respx.mock
async def test_get_video_raises_when_not_ready(cv_client):
    respx.get(f"{BASE}/v1/jobs/job-1/video").mock(return_value=httpx.Response(404))

    with pytest.raises(CVServiceError):
        await cv_client.get_video("job-1")

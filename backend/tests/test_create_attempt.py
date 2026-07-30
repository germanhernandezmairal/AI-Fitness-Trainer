import uuid
from pathlib import Path

import httpx
import pytest
import respx
import sqlalchemy as sa

from app.models import Attempt
from app.schemas.contract import AttemptStatus, UploadErrorCode
from app.services.attempts import create_attempt
from app.services.cv_client import CVClient

SQUAT = Path(__file__).parent / "fixtures" / "squat.mp4"


def _upload(filename: str = "squat.mp4", exercise: str = "squat", content: bytes | None = None):
    data = content if content is not None else SQUAT.read_bytes()
    return {"files": {"video": (filename, data, "video/mp4")}, "data": {"exercise_type": exercise}}


@respx.mock
async def test_creates_a_queued_attempt_and_submits_it_to_the_cv_service(
    client, auth_headers, session, user, settings
):
    route = respx.post(f"{settings.cv_service_url}/v1/jobs").mock(
        return_value=httpx.Response(202, json={"job_id": "job-42", "status": "queued"})
    )

    response = await client.post("/v1/attempts", headers=auth_headers, **_upload())

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"

    attempt = await session.get(Attempt, uuid.UUID(body["attempt_id"]))
    assert attempt is not None
    assert attempt.user_id == user.id
    assert attempt.exercise_type == "squat"
    assert attempt.status == AttemptStatus.QUEUED
    assert attempt.cv_job_id == "job-42"
    assert attempt.original_video_ref
    assert route.called


@respx.mock
async def test_records_consent_and_a_thirty_day_expiry(client, auth_headers, session, settings):
    respx.post(f"{settings.cv_service_url}/v1/jobs").mock(
        return_value=httpx.Response(202, json={"job_id": "job-43", "status": "queued"})
    )

    response = await client.post("/v1/attempts", headers=auth_headers, **_upload())
    attempt = await session.get(Attempt, uuid.UUID(response.json()["attempt_id"]))

    assert attempt.consent_at is not None
    retention_days = (attempt.expires_at - attempt.consent_at).days
    assert retention_days == settings.retention_days


@respx.mock
async def test_sends_a_callback_url_pointing_back_at_this_attempt(
    client, auth_headers, settings
):
    route = respx.post(f"{settings.cv_service_url}/v1/jobs").mock(
        return_value=httpx.Response(202, json={"job_id": "job-44", "status": "queued"})
    )

    response = await client.post("/v1/attempts", headers=auth_headers, **_upload())
    attempt_id = response.json()["attempt_id"]

    assert f"/v1/cv-callback/{attempt_id}".encode() in route.calls.last.request.content


async def test_requires_authentication(client):
    response = await client.post("/v1/attempts", **_upload())

    assert response.status_code == 401


async def test_rejects_an_unknown_exercise_type(client, auth_headers):
    response = await client.post(
        "/v1/attempts", headers=auth_headers, **_upload(exercise="backflip")
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == UploadErrorCode.UNKNOWN_EXERCISE_TYPE


async def test_rejects_an_unsupported_format(client, auth_headers):
    response = await client.post(
        "/v1/attempts", headers=auth_headers, **_upload(filename="clip.avi")
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == UploadErrorCode.UNSUPPORTED_FORMAT


async def test_rejects_a_file_that_is_not_a_video(client, auth_headers):
    response = await client.post(
        "/v1/attempts", headers=auth_headers, **_upload(content=b"nope")
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == UploadErrorCode.UNSUPPORTED_FORMAT


@respx.mock
async def test_no_attempt_row_survives_a_rejected_upload(client, auth_headers, session):
    before = await session.scalar(sa.select(sa.func.count()).select_from(Attempt))

    await client.post("/v1/attempts", headers=auth_headers, **_upload(exercise="backflip"))

    after = await session.scalar(sa.select(sa.func.count()).select_from(Attempt))
    assert after == before


@respx.mock
async def test_returns_502_and_stores_no_attempt_when_the_cv_service_is_down(
    client, auth_headers, session, settings
):
    respx.post(f"{settings.cv_service_url}/v1/jobs").mock(
        return_value=httpx.Response(503, text="down")
    )
    before = await session.scalar(sa.select(sa.func.count()).select_from(Attempt))

    response = await client.post("/v1/attempts", headers=auth_headers, **_upload())

    assert response.status_code == 502
    after = await session.scalar(sa.select(sa.func.count()).select_from(Attempt))
    assert after == before


@respx.mock
async def test_compensates_for_a_persist_failure_after_the_cv_service_accepted_the_job(
    session, user, settings, isolated_storage
):
    """A cv_job_id collision at commit time is a real scenario (see
    test_models.py::test_cv_job_id_is_unique) -- the CV service has already
    accepted the job by the time the commit fails, so both the stored file and
    the accepted CV job must be cleaned up rather than orphaned.

    Exercised directly against create_attempt rather than through the HTTP
    client: the exception this path raises (an IntegrityError, not
    UploadValidationError or CVServiceError) is not one the router translates
    to a response, so going through the ASGI transport would surface it as a
    raised exception rather than a status code. The service-level contract --
    no orphan row, no orphan file, a compensating delete sent -- is exactly
    what changed, so it is exactly what this test checks.
    """
    respx.post(f"{settings.cv_service_url}/v1/jobs").mock(
        return_value=httpx.Response(202, json={"job_id": "job-dup", "status": "queued"})
    )
    delete_route = respx.delete(f"{settings.cv_service_url}/v1/jobs/job-dup").mock(
        return_value=httpx.Response(204)
    )

    async with httpx.AsyncClient() as http:
        cv_client = CVClient(
            base_url=settings.cv_service_url, api_key=settings.cv_api_key, http=http
        )

        await create_attempt(
            db=session,
            user=user,
            video_path=SQUAT,
            filename="squat.mp4",
            exercise_type="squat",
            size_bytes=SQUAT.stat().st_size,
            storage=isolated_storage,
            cv_client=cv_client,
            settings=settings,
        )

        files_after_first = set(isolated_storage.root.iterdir())
        before = await session.scalar(sa.select(sa.func.count()).select_from(Attempt))

        with pytest.raises(sa.exc.IntegrityError):
            await create_attempt(
                db=session,
                user=user,
                video_path=SQUAT,
                filename="squat.mp4",
                exercise_type="squat",
                size_bytes=SQUAT.stat().st_size,
                storage=isolated_storage,
                cv_client=cv_client,
                settings=settings,
            )

    after = await session.scalar(sa.select(sa.func.count()).select_from(Attempt))
    assert after == before

    files_after_second = set(isolated_storage.root.iterdir())
    assert files_after_second == files_after_first, "the second attempt's video was not cleaned up"

    assert delete_route.called

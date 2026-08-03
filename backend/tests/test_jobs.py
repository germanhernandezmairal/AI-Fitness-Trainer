import io
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from app.models import Attempt
from app.services.cv_client import CVClient
from app.services.jobs import purge_expired_attempts, reconcile_stale_attempts

RESULT = {
    "exercise_type": "squat",
    "overall_score": 70,
    "summary": "Reconciled by polling.",
    "rep_count": 1,
    "reps": [
        {
            "rep_index": 1,
            "start_time_sec": 0.0,
            "end_time_sec": 2.0,
            "min_knee_angle_deg": 80,
            "score": 70,
            "errors": [],
        }
    ],
    "annotated_video_url": "https://cv-storage/x/annotated.mp4",
    "algorithm_version": "squat-rules-v1",
}


@pytest.fixture
async def cv_client(settings):
    async with httpx.AsyncClient() as http:
        yield CVClient(base_url=settings.cv_service_url, api_key=settings.cv_api_key, http=http)


@respx.mock
async def test_poller_completes_an_attempt_whose_webhook_never_arrived(
    session, user, make_attempt, cv_client, settings
):
    now = datetime.now(UTC)
    attempt = await make_attempt(
        user,
        status="queued",
        cv_job_id="job-stale",
        created_at=now - timedelta(seconds=settings.cv_poll_after_sec + 60),
    )
    respx.get(f"{settings.cv_service_url}/v1/jobs/job-stale").mock(
        return_value=httpx.Response(200, json={"status": "completed", "result": RESULT})
    )

    moved = await reconcile_stale_attempts(session, cv_client, settings, now=now)

    assert moved == 1
    await session.refresh(attempt)
    assert attempt.status == "completed"
    assert attempt.overall_score == 70


@respx.mock
async def test_poller_ignores_attempts_that_are_still_fresh(
    session, user, make_attempt, cv_client, settings
):
    now = datetime.now(UTC)
    await make_attempt(user, status="queued", cv_job_id="job-fresh", created_at=now)
    route = respx.get(f"{settings.cv_service_url}/v1/jobs/job-fresh").mock(
        return_value=httpx.Response(200, json={"status": "completed", "result": RESULT})
    )

    moved = await reconcile_stale_attempts(session, cv_client, settings, now=now)

    assert moved == 0
    assert not route.called


@respx.mock
async def test_poller_ignores_already_terminal_attempts(
    session, user, make_attempt, cv_client, settings
):
    now = datetime.now(UTC)
    await make_attempt(
        user,
        status="completed",
        cv_job_id="job-done",
        created_at=now - timedelta(hours=1),
        completed_at=now - timedelta(minutes=30),
    )
    route = respx.get(f"{settings.cv_service_url}/v1/jobs/job-done")

    moved = await reconcile_stale_attempts(session, cv_client, settings, now=now)

    assert moved == 0
    assert not route.called


@respx.mock
async def test_poller_survives_one_unreachable_job_and_still_processes_the_rest(
    session, user, make_attempt, cv_client, settings
):
    now = datetime.now(UTC)
    stale = now - timedelta(seconds=settings.cv_poll_after_sec + 60)
    await make_attempt(user, status="queued", cv_job_id="job-broken", created_at=stale)
    await make_attempt(user, status="queued", cv_job_id="job-ok", created_at=stale)
    respx.get(f"{settings.cv_service_url}/v1/jobs/job-broken").mock(
        return_value=httpx.Response(500)
    )
    respx.get(f"{settings.cv_service_url}/v1/jobs/job-ok").mock(
        return_value=httpx.Response(200, json={"status": "completed", "result": RESULT})
    )

    moved = await reconcile_stale_attempts(session, cv_client, settings, now=now)

    assert moved == 1


@respx.mock
async def test_purge_erases_expired_attempts_everywhere(
    session, user, make_attempt, cv_client, isolated_storage, settings
):
    now = datetime.now(UTC)
    ref = isolated_storage.save(io.BytesIO(b"old video"), key="old.mp4")
    attempt = await make_attempt(
        user,
        status="completed",
        cv_job_id="job-expired",
        original_video_ref=ref,
        created_at=now - timedelta(days=31),
        expires_at=now - timedelta(days=1),
    )
    cv_delete = respx.delete(f"{settings.cv_service_url}/v1/jobs/job-expired").mock(
        return_value=httpx.Response(204)
    )

    purged = await purge_expired_attempts(session, isolated_storage, cv_client, now=now)

    assert purged == 1
    assert cv_delete.called
    assert await session.get(Attempt, attempt.id) is None


@respx.mock
async def test_purge_leaves_unexpired_attempts_alone(
    session, user, make_attempt, cv_client, isolated_storage
):
    now = datetime.now(UTC)
    attempt = await make_attempt(user, expires_at=now + timedelta(days=10))

    purged = await purge_expired_attempts(session, isolated_storage, cv_client, now=now)

    assert purged == 0
    assert await session.get(Attempt, attempt.id) is not None

import io
import uuid

import httpx
import respx

from app.models import Attempt


@respx.mock
async def test_deletes_the_row_the_video_and_the_cv_artifacts(
    client, auth_headers, session, user, make_attempt, isolated_storage, settings
):
    ref = isolated_storage.save(io.BytesIO(b"video"), key="orig.mp4")
    attempt = await make_attempt(
        user, status="completed", cv_job_id="job-99", original_video_ref=ref
    )
    cv_delete = respx.delete(f"{settings.cv_service_url}/v1/jobs/job-99").mock(
        return_value=httpx.Response(204)
    )

    response = await client.delete(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 204
    assert cv_delete.called
    assert await session.get(Attempt, attempt.id) is None
    try:
        isolated_storage.open(ref)
    except FileNotFoundError:
        return
    raise AssertionError("the original video should have been deleted")


@respx.mock
async def test_deleting_twice_returns_404_the_second_time(
    client, auth_headers, user, make_attempt, settings
):
    attempt = await make_attempt(user, cv_job_id="job-98")
    respx.delete(f"{settings.cv_service_url}/v1/jobs/job-98").mock(
        return_value=httpx.Response(204)
    )

    first = await client.delete(f"/v1/attempts/{attempt.id}", headers=auth_headers)
    second = await client.delete(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert first.status_code == 204
    assert second.status_code == 404


@respx.mock
async def test_tolerates_a_cv_job_already_gone(
    client, auth_headers, session, user, make_attempt, settings
):
    attempt = await make_attempt(user, cv_job_id="job-97")
    respx.delete(f"{settings.cv_service_url}/v1/jobs/job-97").mock(
        return_value=httpx.Response(404)
    )

    response = await client.delete(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 204
    assert await session.get(Attempt, attempt.id) is None


@respx.mock
async def test_keeps_the_row_when_the_cv_service_cannot_confirm_erasure(
    client, auth_headers, session, user, make_attempt, settings
):
    """Never report erasure we could not carry out — the user must be able to retry."""
    attempt = await make_attempt(user, cv_job_id="job-96")
    respx.delete(f"{settings.cv_service_url}/v1/jobs/job-96").mock(
        return_value=httpx.Response(500)
    )

    response = await client.delete(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 502
    assert await session.get(Attempt, attempt.id) is not None


@respx.mock
async def test_deletes_an_attempt_that_never_reached_the_cv_service(
    client, auth_headers, session, user, make_attempt
):
    attempt = await make_attempt(user, cv_job_id=None)

    response = await client.delete(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 204
    assert await session.get(Attempt, attempt.id) is None


async def test_cannot_delete_another_users_attempt(
    client, auth_headers, session, other_user, make_attempt
):
    attempt = await make_attempt(other_user)

    response = await client.delete(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 404
    assert await session.get(Attempt, attempt.id) is not None


async def test_returns_404_for_an_unknown_id(client, auth_headers):
    response = await client.delete(f"/v1/attempts/{uuid.uuid4()}", headers=auth_headers)

    assert response.status_code == 404


async def test_requires_authentication(client, user, make_attempt):
    attempt = await make_attempt(user)

    response = await client.delete(f"/v1/attempts/{attempt.id}")

    assert response.status_code == 401

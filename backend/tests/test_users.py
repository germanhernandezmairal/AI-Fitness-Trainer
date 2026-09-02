import io
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import respx
import sqlalchemy as sa

from app.models import Attempt, RefreshToken, User
from app.services.auth import hash_refresh_token


@respx.mock
async def test_deletes_the_user_their_attempts_and_their_refresh_tokens(
    client, auth_headers, session, user, make_attempt, isolated_storage, settings
):
    ref = isolated_storage.save(io.BytesIO(b"video"), key="orig.mp4")
    attempt = await make_attempt(
        user, status="completed", cv_job_id="job-77", original_video_ref=ref
    )
    session.add(
        RefreshToken(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=hash_refresh_token("some-raw-refresh-token"),
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    await session.flush()
    cv_delete = respx.delete(f"{settings.cv_service_url}/v1/jobs/job-77").mock(
        return_value=httpx.Response(204)
    )

    response = await client.delete("/v1/users/me", headers=auth_headers)

    assert response.status_code == 204
    assert cv_delete.called
    assert await session.get(User, user.id) is None
    assert await session.get(Attempt, attempt.id) is None
    remaining_tokens = (
        await session.execute(sa.select(RefreshToken).where(RefreshToken.user_id == user.id))
    ).scalars().all()
    assert remaining_tokens == []
    try:
        isolated_storage.open(ref)
    except FileNotFoundError:
        return
    raise AssertionError("the original video should have been deleted")


async def test_deletes_an_account_with_no_attempts(client, auth_headers, session, user):
    response = await client.delete("/v1/users/me", headers=auth_headers)

    assert response.status_code == 204
    assert await session.get(User, user.id) is None


@respx.mock
async def test_keeps_the_account_when_the_cv_service_cannot_confirm_erasure(
    client, auth_headers, session, user, make_attempt, settings
):
    attempt = await make_attempt(user, cv_job_id="job-76")
    respx.delete(f"{settings.cv_service_url}/v1/jobs/job-76").mock(
        return_value=httpx.Response(500)
    )

    response = await client.delete("/v1/users/me", headers=auth_headers)

    assert response.status_code == 502
    assert await session.get(User, user.id) is not None
    assert await session.get(Attempt, attempt.id) is not None


@respx.mock
async def test_tolerates_a_cv_job_already_gone(
    client, auth_headers, session, user, make_attempt, settings
):
    attempt = await make_attempt(user, cv_job_id="job-75")
    respx.delete(f"{settings.cv_service_url}/v1/jobs/job-75").mock(
        return_value=httpx.Response(404)
    )

    response = await client.delete("/v1/users/me", headers=auth_headers)

    assert response.status_code == 204
    assert await session.get(User, user.id) is None
    assert await session.get(Attempt, attempt.id) is None


async def test_does_not_touch_another_users_data(
    client, auth_headers, session, user, other_user, make_attempt
):
    other_attempt = await make_attempt(other_user)

    response = await client.delete("/v1/users/me", headers=auth_headers)

    assert response.status_code == 204
    assert await session.get(User, other_user.id) is not None
    assert await session.get(Attempt, other_attempt.id) is not None


async def test_requires_authentication(client):
    response = await client.delete("/v1/users/me")

    assert response.status_code == 401

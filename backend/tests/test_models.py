import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from app.models import Attempt


async def test_attempt_round_trips_every_contract_column(session, user):
    now = datetime.now(UTC)
    attempt = Attempt(
        id=uuid.uuid4(),
        user_id=user.id,
        exercise_type="squat",
        status="queued",
        cv_job_id="abc123",
        original_video_ref="videos/abc.mp4",
        expires_at=now + timedelta(days=30),
        consent_at=now,
    )
    session.add(attempt)
    await session.flush()

    loaded = await session.get(Attempt, attempt.id)
    assert loaded is not None
    assert loaded.status == "queued"
    assert loaded.cv_job_id == "abc123"
    assert loaded.annotated_video_url is None
    assert loaded.result is None
    assert loaded.overall_score is None
    assert loaded.error_code is None
    assert loaded.completed_at is None


async def test_cv_job_id_is_unique(session, user):
    now = datetime.now(UTC)

    def build() -> Attempt:
        return Attempt(
            id=uuid.uuid4(),
            user_id=user.id,
            exercise_type="squat",
            status="queued",
            cv_job_id="duplicate-job",
            original_video_ref="videos/x.mp4",
            expires_at=now + timedelta(days=30),
            consent_at=now,
        )

    session.add(build())
    await session.flush()
    session.add(build())

    try:
        await session.flush()
    except sa.exc.IntegrityError:
        return
    raise AssertionError("expected a unique-constraint violation on cv_job_id")

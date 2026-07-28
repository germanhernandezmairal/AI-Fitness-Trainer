import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from app.models import Attempt


async def test_attempt_round_trips_every_contract_column(session, user):
    now = datetime.now(UTC)
    attempt_id = uuid.uuid4()
    expires_at = now + timedelta(days=30)
    attempt = Attempt(
        id=attempt_id,
        user_id=user.id,
        exercise_type="squat",
        status="queued",
        cv_job_id="abc123",
        original_video_ref="videos/abc.mp4",
        expires_at=expires_at,
        consent_at=now,
    )
    session.add(attempt)
    await session.flush()

    # session.get() returns straight from the identity map with no SQL when the
    # object isn't expired (expire_on_commit=False in this fixture) — `attempt`
    # would just be handed back to itself, making every comparison below a
    # tautology. refresh() forces a real SELECT so `loaded` reflects what
    # Postgres actually has, not what Python assigned moments ago.
    await session.refresh(attempt)
    loaded = attempt
    assert loaded is not None

    # Columns supplied explicitly on the row.
    assert loaded.id == attempt_id
    assert loaded.user_id == user.id
    assert loaded.exercise_type == "squat"
    assert loaded.status == "queued"
    assert loaded.cv_job_id == "abc123"
    assert loaded.original_video_ref == "videos/abc.mp4"

    # Timezone-aware datetimes must round-trip to the same instant.
    assert loaded.expires_at.tzinfo is not None
    assert loaded.expires_at == expires_at
    assert loaded.consent_at.tzinfo is not None
    assert loaded.consent_at == now

    # Server-generated column: not provided, but must come back populated and tz-aware.
    assert loaded.created_at is not None
    assert loaded.created_at.tzinfo is not None

    # Columns left unset must come back as their nullable defaults.
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

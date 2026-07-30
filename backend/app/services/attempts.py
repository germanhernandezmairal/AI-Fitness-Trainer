import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Attempt, User
from app.schemas.contract import AttemptStatus
from app.services.cv_client import CVClient
from app.services.storage import Storage
from app.services.validation import validate_upload


def callback_url_for(attempt_id: uuid.UUID, settings: Settings) -> str:
    return f"{settings.backend_public_url.rstrip('/')}/v1/cv-callback/{attempt_id}"


async def create_attempt(
    db: AsyncSession,
    user: User,
    video_path: Path,
    filename: str,
    exercise_type: str,
    size_bytes: int,
    storage: Storage,
    cv_client: CVClient,
    settings: Settings,
) -> Attempt:
    """Validate, store, submit, persist.

    Raises UploadValidationError (-> 400) or CVServiceError (-> 502). Nothing is
    persisted unless the CV service accepted the job, so a failed submission never
    leaves an orphan row for the reconciler to chew on.
    """
    exercise = validate_upload(video_path, filename, exercise_type, size_bytes, settings)

    with video_path.open("rb") as handle:
        video_ref = storage.save(handle, key=filename)

    attempt_id = uuid.uuid4()
    try:
        with storage.open(video_ref) as handle:
            accepted = await cv_client.submit_job(
                video=handle,
                filename=filename,
                exercise_type=exercise.value,
                callback_url=callback_url_for(attempt_id, settings),
            )
    except Exception:
        storage.delete(video_ref)
        raise

    now = datetime.now(UTC)
    attempt = Attempt(
        id=attempt_id,
        user_id=user.id,
        exercise_type=exercise.value,
        status=AttemptStatus.QUEUED.value,
        cv_job_id=accepted.job_id,
        original_video_ref=video_ref,
        created_at=now,
        expires_at=now + timedelta(days=settings.retention_days),
        consent_at=now,
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt

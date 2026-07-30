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

    Raises UploadValidationError (-> 400), CVServiceError (-> 502), or whatever
    the persist step itself raises (e.g. an IntegrityError from a cv_job_id
    collision). Nothing is left behind on any failure: a rejected upload never
    reaches storage; a failed CV submission deletes the file it just wrote; and
    if the CV service accepts the job but the commit that follows then fails,
    the stored file is deleted and a best-effort compensating delete is sent
    for the CV job, so neither an orphan file nor an orphan job survives a
    failed commit. A cleanup failure is swallowed so it never masks the
    original error.
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
    try:
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
    except Exception:
        await db.rollback()
        storage.delete(video_ref)
        try:
            await cv_client.delete_job(accepted.job_id)
        except Exception:
            pass
        raise
    return attempt

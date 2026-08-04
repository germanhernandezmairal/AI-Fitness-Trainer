import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Attempt, User
from app.schemas.contract import AttemptStatus, JobStatus
from app.services.cv_client import CVClient
from app.services.storage import Storage
from app.services.validation import validate_upload


def callback_url_for(attempt_id: uuid.UUID, settings: Settings) -> str:
    return f"{settings.backend_public_url.rstrip('/')}/v1/cv-callback/{attempt_id}"


def video_url_for(attempt_id: uuid.UUID, settings: Settings) -> str:
    """The URL an end-user client gets for the annotated video.

    Never the CV service's own /v1/jobs/{id}/video URL: that requires the internal
    X-API-Key, which is a backend<->CV service secret, not something to hand to a
    user's browser. This route is JWT-authenticated and proxies the video instead.
    """
    return f"{settings.backend_public_url.rstrip('/')}/v1/attempts/{attempt_id}/video"


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


async def apply_job_status(
    db: AsyncSession, attempt: Attempt, job_status: JobStatus, settings: Settings
) -> bool:
    """Write a CV result onto an attempt. Returns False if it was already terminal.

    Both the webhook (Task 11) and the polling reconciler (Task 13) call this, so a
    result delivered twice — or by both paths — lands exactly once (spec §8).
    """
    # SELECT ... FOR UPDATE: re-reads status AND serializes this call against a
    # concurrent caller (Task 13's poller racing this webhook), so a second delivery
    # that arrives while the first is still mid-transaction blocks here and then sees
    # the terminal state instead of both callers passing the guard below.
    await db.refresh(attempt, with_for_update=True)

    if AttemptStatus(attempt.status).is_terminal:
        return False

    if job_status.status is AttemptStatus.COMPLETED and job_status.result is not None:
        # Rewrite the CV service's own (X-API-Key-gated) video URL to our proxy route
        # before it ever reaches the DB or a response — see video_url_for.
        video_url = video_url_for(attempt.id, settings) if job_status.result.annotated_video_url else None
        result_dict = job_status.result.model_dump(mode="json")
        result_dict["annotated_video_url"] = video_url

        attempt.status = AttemptStatus.COMPLETED.value
        attempt.result = result_dict
        attempt.overall_score = job_status.result.overall_score
        attempt.annotated_video_url = video_url
        attempt.error_code = None
        attempt.completed_at = datetime.now(UTC)
    elif job_status.status is AttemptStatus.FAILED and job_status.error is not None:
        attempt.status = AttemptStatus.FAILED.value
        attempt.error_code = job_status.error.code.value
        attempt.completed_at = datetime.now(UTC)
        # A failed row must be coherent on its own, not merely by relying on no
        # other branch having run first: clear any result fields so a failure can
        # never carry a stale completed-job payload.
        attempt.result = None
        attempt.overall_score = None
        attempt.annotated_video_url = None
    else:
        # queued / processing — record the progress, stay non-terminal
        attempt.status = job_status.status.value

    await db.commit()
    return True


async def delete_attempt(
    db: AsyncSession,
    attempt: Attempt,
    storage: Storage,
    cv_client: CVClient,
) -> None:
    """One user action, one sweep across both services (spec §7).

    The CV call comes before the row delete on purpose: if the CV service cannot
    confirm erasure, CVServiceError propagates, the row survives, and the user can
    retry. Reporting success we could not deliver would break the GDPR promise.
    """
    storage.delete(attempt.original_video_ref)

    if attempt.cv_job_id:
        await cv_client.delete_job(attempt.cv_job_id)

    await db.delete(attempt)
    await db.commit()

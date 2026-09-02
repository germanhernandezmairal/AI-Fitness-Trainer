"""Business logic for account-level erasure (spec: 2026-09-02-privacy-compliance-design.md §2.6-2.7)."""

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Attempt, User
from app.services.cv_client import CVClient
from app.services.storage import Storage


async def delete_account(
    db: AsyncSession,
    user: User,
    storage: Storage,
    cv_client: CVClient,
) -> None:
    """Erase a user and everything they own.

    Mirrors delete_attempt's ordering and rationale: `attempts.user_id` and
    `refresh_tokens.user_id` both have ON DELETE CASCADE, so deleting the `User` row
    alone would silently wipe those Postgres rows — but it would never touch the
    video file on disk or the cv-service job, since those only ever get cleaned up
    by explicit Python calls (storage.delete, cv_client.delete_job), never a DB
    trigger. So every owned attempt gets that same external cleanup first; only then
    does the user row go. If a CVServiceError propagates mid-loop, it aborts here —
    some attempts may already be cleaned, the user row survives, and the request can
    be retried. Reporting success we could not fully deliver would break the GDPR
    promise, same as delete_attempt's own docstring.
    """
    attempts = (
        await db.execute(sa.select(Attempt).where(Attempt.user_id == user.id))
    ).scalars().all()
    for attempt in attempts:
        storage.delete(attempt.original_video_ref)
        if attempt.cv_job_id:
            await cv_client.delete_job(attempt.cv_job_id)
        await db.delete(attempt)

    await db.delete(user)
    await db.commit()

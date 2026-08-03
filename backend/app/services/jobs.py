"""Scheduled reconciliation (spec §4 polling fallback) and retention purge (spec §7).

Both take `now` explicitly so tests can place attempts in the past without patching
the clock, and both swallow per-attempt failures so one bad row cannot stall the sweep.
"""

import logging
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Attempt
from app.schemas.contract import AttemptStatus
from app.services.attempts import apply_job_status, delete_attempt
from app.services.cv_client import CVClient, CVServiceError
from app.services.storage import Storage

logger = logging.getLogger(__name__)

NON_TERMINAL = [AttemptStatus.QUEUED.value, AttemptStatus.PROCESSING.value]


async def reconcile_stale_attempts(
    db: AsyncSession,
    cv_client: CVClient,
    settings: Settings,
    now: datetime,
) -> int:
    """Ask the CV service directly about attempts whose webhook never arrived."""
    cutoff = now - timedelta(seconds=settings.cv_poll_after_sec)
    query = sa.select(Attempt).where(
        Attempt.status.in_(NON_TERMINAL),
        Attempt.cv_job_id.is_not(None),
        Attempt.created_at < cutoff,
    )
    stale = list((await db.execute(query)).scalars())

    moved = 0
    for attempt in stale:
        try:
            job_status = await cv_client.get_job(attempt.cv_job_id)
        except CVServiceError as exc:
            logger.warning("could not poll job %s: %s", attempt.cv_job_id, exc)
            continue

        await apply_job_status(db, attempt, job_status)
        if AttemptStatus(attempt.status).is_terminal:
            moved += 1

    return moved


async def purge_expired_attempts(
    db: AsyncSession,
    storage: Storage,
    cv_client: CVClient,
    now: datetime,
) -> int:
    """TTL fallback so nothing lingers past the retention period."""
    query = sa.select(Attempt).where(Attempt.expires_at < now)
    expired = list((await db.execute(query)).scalars())

    purged = 0
    for attempt in expired:
        try:
            await delete_attempt(db, attempt, storage, cv_client)
            purged += 1
        except CVServiceError as exc:
            logger.warning("could not purge attempt %s: %s", attempt.id, exc)

    return purged

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from app.api import attempts, auth_dev, webhooks
from app.config import get_settings
from app.db import session_factory
from app.services.cv_client import CVClient
from app.services.jobs import purge_expired_attempts, reconcile_stale_attempts
from app.services.storage import LocalFilesystemStorage

logger = logging.getLogger(__name__)


async def _run_reconcile() -> None:
    settings = get_settings()
    maker = session_factory(settings.database_url)
    async with maker() as db, httpx.AsyncClient() as http:
        cv_client = CVClient(settings.cv_service_url, settings.cv_api_key, http)
        moved = await reconcile_stale_attempts(db, cv_client, settings, now=datetime.now(UTC))
    if moved:
        logger.info("reconciled %s stale attempt(s) by polling", moved)


async def _run_purge() -> None:
    settings = get_settings()
    maker = session_factory(settings.database_url)
    storage = LocalFilesystemStorage(root=settings.storage_dir)
    async with maker() as db, httpx.AsyncClient() as http:
        cv_client = CVClient(settings.cv_service_url, settings.cv_api_key, http)
        purged = await purge_expired_attempts(db, storage, cv_client, now=datetime.now(UTC))
    if purged:
        logger.info("purged %s expired attempt(s)", purged)


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_run_reconcile, "interval", seconds=30, id="reconcile")
    scheduler.add_job(_run_purge, "interval", hours=6, id="purge")
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="AI Fitness Trainer Backend", version="0.1.0", lifespan=lifespan)
app.include_router(auth_dev.router)
app.include_router(attempts.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

import base64
import binascii
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CVClientDep, CurrentUser, DbDep, SettingsDep, StorageDep
from app.models import Attempt, User
from app.schemas.attempt import AttemptCreated, AttemptDetail, AttemptPage, AttemptSummary
from app.schemas.contract import (
    USER_MESSAGES,
    AnalysisResult,
    AttemptStatus,
    ErrorPayload,
    FailureCode,
)
from app.services.attempts import create_attempt, delete_attempt
from app.services.cv_client import CVServiceError
from app.services.validation import UploadValidationError

router = APIRouter(prefix="/v1/attempts", tags=["attempts"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=AttemptCreated)
async def create(
    user: CurrentUser,
    db: DbDep,
    storage: StorageDep,
    cv_client: CVClientDep,
    settings: SettingsDep,
    video: UploadFile = File(...),
    exercise_type: str = Form(...),
):
    """Spool to a temp file first: validation needs to seek, and a stream cannot."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(video.filename or "").suffix) as tmp:
        temp_path = Path(tmp.name)
        size_bytes = 0
        while chunk := await video.read(1024 * 1024):
            size_bytes += len(chunk)
            tmp.write(chunk)

    try:
        attempt = await create_attempt(
            db=db,
            user=user,
            video_path=temp_path,
            filename=video.filename or "upload.mp4",
            exercise_type=exercise_type,
            size_bytes=size_bytes,
            storage=storage,
            cv_client=cv_client,
            settings=settings,
        )
    except UploadValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": exc.code.value, "message": exc.message}},
        )
    except CVServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"the analysis service is unavailable: {exc}",
        ) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    return AttemptCreated(attempt_id=attempt.id, status=AttemptStatus(attempt.status))


async def _load_owned_attempt(db: AsyncSession, attempt_id: uuid.UUID, user: User) -> Attempt:
    """404 rather than 403 for a stranger's attempt — do not leak that it exists."""
    result = await db.execute(
        sa.select(Attempt).where(Attempt.id == attempt_id, Attempt.user_id == user.id)
    )
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attempt not found")
    return attempt


_UNKNOWN_ERROR_MESSAGE = "No pudimos analizar el vídeo. Inténtalo de nuevo en unos minutos."


def _error_payload(error_code: str) -> ErrorPayload:
    """Degrade gracefully on an unrecognized stored code rather than 500.

    error_code is a bare String(50) with no DB constraint, so a bad webhook write is
    enough to produce a value outside the FailureCode catalog. An attempt must stay
    readable even then.
    """
    try:
        code = FailureCode(error_code)
    except ValueError:
        # ErrorPayload.code is a closed FailureCode enum, so an unrecognized stored
        # string can't be echoed back verbatim. WORKER_ERROR is the closest fit
        # semantically (a system-side problem, safe to retry) and its is_retryable
        # property tells the client to let the user try again.
        return ErrorPayload(code=FailureCode.WORKER_ERROR, message=_UNKNOWN_ERROR_MESSAGE)
    return ErrorPayload(code=code, message=USER_MESSAGES[code])


@router.get("/{attempt_id}", response_model=AttemptDetail)
async def get_attempt(attempt_id: uuid.UUID, user: CurrentUser, db: DbDep) -> AttemptDetail:
    attempt = await _load_owned_attempt(db, attempt_id, user)

    error = _error_payload(attempt.error_code) if attempt.error_code else None

    return AttemptDetail(
        attempt_id=attempt.id,
        exercise_type=attempt.exercise_type,
        status=AttemptStatus(attempt.status),
        created_at=attempt.created_at,
        completed_at=attempt.completed_at,
        result=AnalysisResult.model_validate(attempt.result) if attempt.result else None,
        error=error,
    )


def _encode_cursor(when: datetime) -> str:
    return base64.urlsafe_b64encode(when.isoformat().encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> datetime:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        return datetime.fromisoformat(base64.urlsafe_b64decode(padded).decode())
    except (ValueError, binascii.Error) as exc:
        # binascii.Error (malformed base64) is NOT a ValueError subclass, so both
        # must be caught here or a bad cursor value escapes as a 500 instead of 400.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="malformed cursor"
        ) from exc


@router.get("", response_model=AttemptPage)
async def list_attempts(
    user: CurrentUser,
    db: DbDep,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> AttemptPage:
    """Keyset pagination on created_at descending.

    The cursor is an opaque base64url token wrapping the ISO timestamp of the last item
    on the previous page — callers must not depend on its interior format. Keeping it
    opaque means a future move to a compound (created_at, id) cursor (see below) stays
    a non-breaking change.

    Two attempts sharing an exact created_at would straddle a page boundary. Postgres
    timestamps are microsecond-precision and one user cannot upload twice in the same
    microsecond, so a compound (created_at, id) cursor is not worth the complexity yet.
    """
    query = sa.select(Attempt).where(Attempt.user_id == user.id)
    if cursor:
        query = query.where(Attempt.created_at < _decode_cursor(cursor))

    query = query.order_by(Attempt.created_at.desc()).limit(limit + 1)
    rows = list((await db.execute(query)).scalars())

    has_more = len(rows) > limit
    page = rows[:limit]
    return AttemptPage(
        items=[
            AttemptSummary(
                attempt_id=row.id,
                exercise_type=row.exercise_type,
                status=AttemptStatus(row.status),
                overall_score=row.overall_score,
                created_at=row.created_at,
            )
            for row in page
        ],
        next_cursor=_encode_cursor(page[-1].created_at) if has_more and page else None,
    )


@router.delete("/{attempt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def erase_attempt(
    attempt_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
    storage: StorageDep,
    cv_client: CVClientDep,
) -> Response:
    attempt = await _load_owned_attempt(db, attempt_id, user)

    try:
        await delete_attempt(db, attempt, storage, cv_client)
    except CVServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"could not confirm erasure with the analysis service: {exc}",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)

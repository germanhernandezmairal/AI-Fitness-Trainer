import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse

from app.api.deps import CVClientDep, CurrentUser, DbDep, SettingsDep, StorageDep
from app.models import Attempt
from app.schemas.attempt import AttemptCreated, AttemptDetail, AttemptPage, AttemptSummary
from app.schemas.contract import AnalysisResult, AttemptStatus, ErrorPayload, FailureCode
from app.services.attempts import create_attempt
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


async def _load_owned_attempt(db, attempt_id: uuid.UUID, user) -> Attempt:
    """404 rather than 403 for a stranger's attempt — do not leak that it exists."""
    result = await db.execute(
        sa.select(Attempt).where(Attempt.id == attempt_id, Attempt.user_id == user.id)
    )
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attempt not found")
    return attempt


@router.get("/{attempt_id}", response_model=AttemptDetail)
async def get_attempt(attempt_id: uuid.UUID, user: CurrentUser, db: DbDep) -> AttemptDetail:
    attempt = await _load_owned_attempt(db, attempt_id, user)

    error = None
    if attempt.error_code:
        error = ErrorPayload(
            code=FailureCode(attempt.error_code), message="see the CV service logs"
        )

    return AttemptDetail(
        attempt_id=attempt.id,
        exercise_type=attempt.exercise_type,
        status=AttemptStatus(attempt.status),
        created_at=attempt.created_at,
        completed_at=attempt.completed_at,
        result=AnalysisResult.model_validate(attempt.result) if attempt.result else None,
        error=error,
    )


@router.get("", response_model=AttemptPage)
async def list_attempts(
    user: CurrentUser,
    db: DbDep,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> AttemptPage:
    """Keyset pagination on created_at descending; the cursor is an ISO timestamp.

    Two attempts sharing an exact created_at would straddle a page boundary. Postgres
    timestamps are microsecond-precision and one user cannot upload twice in the same
    microsecond, so a compound (created_at, id) cursor is not worth the complexity yet.
    """
    query = sa.select(Attempt).where(Attempt.user_id == user.id)
    if cursor:
        # An unescaped "+" UTC offset (e.g. "...+00:00") is not safe raw in a query
        # string: both httpx's client-side query parsing and Starlette's server-side
        # parsing decode a literal "+" to a space per application/x-www-form-urlencoded
        # convention. isoformat() never emits a space on its own, so undoing that here
        # is safe and avoids requiring every caller to percent-encode the cursor first.
        try:
            query = query.where(
                Attempt.created_at < datetime.fromisoformat(cursor.replace(" ", "+"))
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="malformed cursor"
            ) from None

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
        next_cursor=page[-1].created_at.isoformat() if has_more and page else None,
    )

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.api.deps import CVClientDep, CurrentUser, DbDep, SettingsDep, StorageDep
from app.schemas.attempt import AttemptCreated
from app.schemas.contract import AttemptStatus
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

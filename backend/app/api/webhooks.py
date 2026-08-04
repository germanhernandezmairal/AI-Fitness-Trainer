"""CV service -> backend callback (spec §4).

Not JWT-authenticated: the CV service has no user session. Trust comes entirely
from the HMAC signature, which is verified over the RAW body before parsing.
"""

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import ValidationError

from app.api.deps import DbDep, SettingsDep
from app.models import Attempt
from app.schemas.contract import JobStatus
from app.security.signing import SignatureError, verify_signature
from app.services.attempts import apply_job_status

router = APIRouter(prefix="/v1/cv-callback", tags=["cv webhook"])


@router.post("/{attempt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def receive_result(
    attempt_id: uuid.UUID,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    x_cv_signature: str | None = Header(default=None),
    x_cv_timestamp: str | None = Header(default=None),
) -> Response:
    body = await request.body()

    try:
        verify_signature(
            body=body,
            timestamp=x_cv_timestamp or "",
            signature=x_cv_signature or "",
            secret=settings.cv_webhook_secret,
            tolerance_sec=settings.webhook_tolerance_sec,
        )
    except SignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid webhook: {exc}"
        ) from exc

    try:
        job_status = JobStatus.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(include_context=False, include_url=False),
        ) from exc

    result = await db.execute(sa.select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attempt not found")

    await apply_job_status(db, attempt, job_status, settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

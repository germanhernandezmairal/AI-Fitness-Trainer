"""Public-boundary response shapes (spec §3)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.contract import AnalysisResult, AttemptStatus, ErrorPayload


class AttemptCreated(BaseModel):
    attempt_id: uuid.UUID
    status: AttemptStatus


class AttemptDetail(BaseModel):
    attempt_id: uuid.UUID
    exercise_type: str
    status: AttemptStatus
    created_at: datetime
    completed_at: datetime | None = None
    result: AnalysisResult | None = None
    error: ErrorPayload | None = None


class AttemptSummary(BaseModel):
    """The light shape the progress view lists."""

    attempt_id: uuid.UUID
    exercise_type: str
    status: AttemptStatus
    overall_score: int | None = None
    created_at: datetime


class AttemptPage(BaseModel):
    items: list[AttemptSummary]
    next_cursor: str | None = None

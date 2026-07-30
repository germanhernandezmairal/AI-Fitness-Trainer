"""Client for the internal boundary: backend -> CV service (spec §4)."""

import mimetypes
from typing import BinaryIO

import httpx

from app.schemas.contract import JobAccepted, JobStatus

TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=120.0, pool=5.0)


class CVServiceError(Exception):
    """The CV service was unreachable or answered with an unexpected status."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CVClient:
    def __init__(self, base_url: str, api_key: str, http: httpx.AsyncClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.http = http

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key}

    async def submit_job(
        self,
        video: BinaryIO,
        filename: str,
        exercise_type: str,
        callback_url: str,
    ) -> JobAccepted:
        content_type = mimetypes.guess_type(filename)[0] or "video/mp4"
        try:
            response = await self.http.post(
                f"{self.base_url}/v1/jobs",
                headers=self._headers,
                files={"video": (filename, video, content_type)},
                data={"exercise_type": exercise_type, "callback_url": callback_url},
                timeout=TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise CVServiceError(f"could not reach the CV service: {exc}") from exc

        if response.status_code not in (200, 201, 202):
            raise CVServiceError(
                f"CV service rejected the job: {response.text}", response.status_code
            )
        try:
            return JobAccepted.model_validate(response.json())
        except ValueError as exc:
            raise CVServiceError(
                f"CV service sent an unusable job-accepted response: {exc}",
                response.status_code,
            ) from exc

    async def get_job(self, job_id: str) -> JobStatus:
        try:
            response = await self.http.get(
                f"{self.base_url}/v1/jobs/{job_id}", headers=self._headers, timeout=TIMEOUT
            )
        except httpx.HTTPError as exc:
            raise CVServiceError(f"could not reach the CV service: {exc}") from exc

        if response.status_code != 200:
            raise CVServiceError(
                f"unexpected status for job {job_id}: {response.text}", response.status_code
            )
        try:
            return JobStatus.model_validate(response.json())
        except ValueError as exc:
            raise CVServiceError(
                f"CV service sent an unusable job-status response for {job_id}: {exc}",
                response.status_code,
            ) from exc

    async def delete_job(self, job_id: str) -> None:
        """Idempotent (spec §4): an already-deleted job is a success."""
        try:
            response = await self.http.delete(
                f"{self.base_url}/v1/jobs/{job_id}", headers=self._headers, timeout=TIMEOUT
            )
        except httpx.HTTPError as exc:
            raise CVServiceError(f"could not reach the CV service: {exc}") from exc

        if response.status_code not in (200, 202, 204, 404):
            raise CVServiceError(
                f"unexpected status deleting job {job_id}: {response.text}", response.status_code
            )

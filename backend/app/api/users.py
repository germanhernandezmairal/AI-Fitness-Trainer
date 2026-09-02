"""Account-level operations (spec: 2026-09-02-privacy-compliance-design.md §2.6)."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, CVClientDep, DbDep, StorageDep
from app.services.cv_client import CVServiceError
from app.services.users import delete_account

router = APIRouter(prefix="/v1/users", tags=["users"])


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    user: CurrentUser, db: DbDep, storage: StorageDep, cv_client: CVClientDep
) -> None:
    try:
        await delete_account(db, user, storage, cv_client)
    except CVServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"could not confirm erasure with the analysis service: {exc}",
        ) from exc

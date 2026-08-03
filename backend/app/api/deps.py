from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import session_factory
from app.models import User
from app.security.tokens import InvalidToken, decode_access_token
from app.services.cv_client import CVClient
from app.services.storage import LocalFilesystemStorage, Storage

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_db(settings: SettingsDep) -> AsyncIterator[AsyncSession]:
    maker = session_factory(settings.database_url)
    async with maker() as session:
        yield session


DbDep = Annotated[AsyncSession, Depends(get_db)]

# auto_error=False: a missing/malformed header should fall through to our own 401,
# not FastAPI's default 403 — and declaring this as a proper security scheme (rather
# than a bare Header() param) is what gives Swagger UI a working Authorize button.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    settings: SettingsDep,
    db: DbDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        user_id = decode_access_token(credentials.credentials, settings.jwt_secret)
    except InvalidToken:
        raise unauthorized from None

    user = await db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_storage(settings: SettingsDep) -> Storage:
    return LocalFilesystemStorage(root=settings.storage_dir)


async def get_cv_client(settings: SettingsDep) -> AsyncIterator[CVClient]:
    async with httpx.AsyncClient() as http:
        yield CVClient(
            base_url=settings.cv_service_url, api_key=settings.cv_api_key, http=http
        )


StorageDep = Annotated[Storage, Depends(get_storage)]
CVClientDep = Annotated[CVClient, Depends(get_cv_client)]

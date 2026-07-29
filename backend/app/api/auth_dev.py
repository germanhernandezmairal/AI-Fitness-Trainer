"""Dev-only token issuance. NOT for production: no password, no verification.

Replaced wholesale by the auth plan; nothing outside this module depends on how
tokens are issued, only on `get_current_user`.
"""

import uuid

import sqlalchemy as sa
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.api.deps import DbDep, SettingsDep
from app.models import User
from app.security.tokens import create_access_token

router = APIRouter(prefix="/v1/auth", tags=["auth (dev)"])


class DevLoginRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/dev-login", response_model=TokenResponse)
async def dev_login(payload: DevLoginRequest, db: DbDep, settings: SettingsDep) -> TokenResponse:
    result = await db.execute(sa.select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(id=uuid.uuid4(), email=payload.email)
        db.add(user)
        await db.commit()

    token = create_access_token(user.id, settings.jwt_secret, settings.jwt_ttl_seconds)
    return TokenResponse(access_token=token)

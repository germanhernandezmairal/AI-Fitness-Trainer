"""Real (password-based) authentication: register, login, refresh, logout.

Lives alongside app/api/auth_dev.py, which is untouched. Both routers share the
/v1/auth prefix; there is no path collision (dev-login is /v1/auth/dev-login).
"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbDep, SettingsDep
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenPair
from app.services.auth import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidRefreshToken,
    authenticate_user,
    issue_token_pair,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenPair)
async def register(payload: RegisterRequest, db: DbDep, settings: SettingsDep) -> TokenPair:
    try:
        user = await register_user(db, payload.email, payload.password)
    except EmailAlreadyRegistered:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered") from None

    access_token, refresh_token = await issue_token_pair(db, user, settings)
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: DbDep, settings: SettingsDep) -> TokenPair:
    try:
        user = await authenticate_user(db, payload.email, payload.password)
    except InvalidCredentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid email or password") from None

    access_token, refresh_token = await issue_token_pair(db, user, settings)
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: DbDep, settings: SettingsDep) -> TokenPair:
    try:
        access_token, refresh_token = await rotate_refresh_token(
            db, payload.refresh_token, settings
        )
    except InvalidRefreshToken:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "invalid or expired refresh token"
        ) from None

    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, db: DbDep) -> None:
    await revoke_refresh_token(db, payload.refresh_token)

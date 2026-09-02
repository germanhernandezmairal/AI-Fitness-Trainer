"""Business logic for real (password-based) authentication.

Access tokens issued here reuse create_access_token/decode_access_token unchanged, so
app/api/deps.py's get_current_user needs no changes at all.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import RefreshToken, User
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_access_token

# Hashed once at import time so authenticate_user always does one bcrypt comparison,
# whether or not the email exists — avoids a timing signal that would let a caller
# distinguish "unknown email" from "wrong password".
_DUMMY_HASH = hash_password("equalize-timing-for-unknown-emails")


class EmailAlreadyRegistered(Exception):
    """Registration attempted with an email that already has an account."""


class InvalidCredentials(Exception):
    """Unknown email, wrong password, or a passwordless (dev-login-only) account."""


class InvalidRefreshToken(Exception):
    """Refresh presented a token that is missing, expired, or already revoked."""


class ConsentRequired(Exception):
    """Registration attempted with consent missing or explicitly false."""


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def register_user(db: AsyncSession, email: str, password: str, consent: bool) -> User:
    if not consent:
        raise ConsentRequired(email)

    existing = await db.execute(sa.select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise EmailAlreadyRegistered(email)

    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password(password),
        privacy_consent_at=datetime.now(UTC),
    )
    db.add(user)
    try:
        await db.commit()
    except sa.exc.IntegrityError:
        await db.rollback()
        raise EmailAlreadyRegistered(email) from None
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(sa.select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    hashed = user.hashed_password if (user and user.hashed_password) else _DUMMY_HASH
    ok = verify_password(password, hashed)
    if user is None or user.hashed_password is None or not ok:
        raise InvalidCredentials(email)
    return user


async def _issue_refresh_row(db: AsyncSession, user_id: uuid.UUID, settings: Settings) -> str:
    raw_token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db.add(
        RefreshToken(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=hash_refresh_token(raw_token),
            issued_at=now,
            expires_at=now + timedelta(seconds=settings.refresh_token_ttl_seconds),
        )
    )
    return raw_token


async def issue_token_pair(db: AsyncSession, user: User, settings: Settings) -> tuple[str, str]:
    access_token = create_access_token(
        user.id, settings.jwt_secret, settings.access_token_ttl_seconds
    )
    refresh_token = await _issue_refresh_row(db, user.id, settings)
    await db.commit()
    return access_token, refresh_token


async def rotate_refresh_token(
    db: AsyncSession, raw_token: str, settings: Settings
) -> tuple[str, str]:
    token_hash = hash_refresh_token(raw_token)
    result = await db.execute(sa.select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    record = result.scalar_one_or_none()
    if record is None:
        raise InvalidRefreshToken("unknown token")

    now = datetime.now(UTC)
    if record.revoked_at is not None:
        # Presenting an already-rotated token is treated as theft: kill every active
        # session for this user, not just the one presented.
        await db.execute(
            sa.update(RefreshToken)
            .where(RefreshToken.user_id == record.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await db.commit()
        raise InvalidRefreshToken("reused token")

    if record.expires_at < now:
        raise InvalidRefreshToken("expired token")

    user = await db.get(User, record.user_id)
    if user is None:
        raise InvalidRefreshToken("orphaned token")

    record.revoked_at = now
    access_token = create_access_token(
        user.id, settings.jwt_secret, settings.access_token_ttl_seconds
    )
    new_refresh_token = await _issue_refresh_row(db, user.id, settings)
    await db.commit()
    return access_token, new_refresh_token


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    """Idempotent: revoking an unknown or already-revoked token is a no-op."""
    token_hash = hash_refresh_token(raw_token)
    result = await db.execute(sa.select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    record = result.scalar_one_or_none()
    if record is not None and record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
        await db.commit()

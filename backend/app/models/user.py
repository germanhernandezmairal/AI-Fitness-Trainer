import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    # NULL means no password credential (e.g. a dev-login-created account) — never
    # NOT NULL, since app/api/auth_dev.py creates users with no password at all.
    hashed_password: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Set explicitly by every User-creation path (register_user, dev_login, test
    # fixtures) — no server default, so a code path that forgets it fails loudly at
    # insert time rather than silently recording a fabricated consent moment.
    privacy_consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

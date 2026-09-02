"""privacy: explicit consent timestamp on users

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NOT NULL from the start: a temporary server_default backfills any pre-existing
    # row in the same statement, then gets dropped so every future insert must supply
    # the value explicitly in application code — matching Attempt.consent_at, which
    # has no server default either.
    op.add_column(
        "users",
        sa.Column(
            "privacy_consent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.alter_column("users", "privacy_consent_at", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "privacy_consent_at")

"""initial: users and attempts

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("exercise_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("cv_job_id", sa.String(100), nullable=True, unique=True),
        sa.Column("original_video_ref", sa.String(500), nullable=False),
        sa.Column("annotated_video_url", sa.String(1000), nullable=True),
        sa.Column("result", postgresql.JSONB, nullable=True),
        sa.Column("overall_score", sa.Integer, nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_attempts_user_created", "attempts", ["user_id", "created_at"])
    op.create_index("ix_attempts_status", "attempts", ["status"])
    op.create_index("ix_attempts_expires_at", "attempts", ["expires_at"])


def downgrade() -> None:
    op.drop_table("attempts")
    op.drop_table("users")

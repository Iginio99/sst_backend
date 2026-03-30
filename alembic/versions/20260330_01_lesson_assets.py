"""Add lesson asset fields for uploads

Revision ID: 20260330_01
Revises: 20260324_01
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260330_01"
down_revision = "20260324_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lessons", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("lessons", sa.Column("thumbnail_url", sa.String(length=1024), nullable=True))
    op.add_column("lessons", sa.Column("thumbnail_path", sa.String(length=1024), nullable=True))
    op.add_column(
        "lessons",
        sa.Column("content_mode", sa.String(length=32), nullable=False, server_default="upload"),
    )
    op.add_column("lessons", sa.Column("content_url", sa.String(length=1024), nullable=True))
    op.add_column("lessons", sa.Column("content_path", sa.String(length=1024), nullable=True))
    op.add_column("lessons", sa.Column("content_mime_type", sa.String(length=255), nullable=True))
    op.add_column("lessons", sa.Column("content_size_bytes", sa.Integer(), nullable=True))
    op.add_column("lessons", sa.Column("external_url", sa.String(length=1024), nullable=True))

    op.execute(
        """
        UPDATE lessons
        SET thumbnail_url = image
        WHERE image IS NOT NULL AND thumbnail_url IS NULL
        """
    )
    op.alter_column("lessons", "content_mode", server_default=None)


def downgrade() -> None:
    op.drop_column("lessons", "external_url")
    op.drop_column("lessons", "content_size_bytes")
    op.drop_column("lessons", "content_mime_type")
    op.drop_column("lessons", "content_path")
    op.drop_column("lessons", "content_url")
    op.drop_column("lessons", "content_mode")
    op.drop_column("lessons", "thumbnail_path")
    op.drop_column("lessons", "thumbnail_url")
    op.drop_column("lessons", "description")

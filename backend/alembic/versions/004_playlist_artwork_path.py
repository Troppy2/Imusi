"""Add playlists.artwork_path column.

Revision ID: 004
Revises: 003
Create Date: 2026-03-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("playlists", sa.Column("artwork_path", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("playlists", "artwork_path")

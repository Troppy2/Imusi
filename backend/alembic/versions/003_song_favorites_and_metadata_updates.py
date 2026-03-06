"""Add songs.is_favorite column.

Revision ID: 003
Revises: 002
Create Date: 2026-03-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "songs",
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index(op.f("ix_songs_is_favorite"), "songs", ["is_favorite"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_songs_is_favorite"), table_name="songs")
    op.drop_column("songs", "is_favorite")

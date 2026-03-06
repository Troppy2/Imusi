"""Schema updates: updated_at, song fields, recently_played, playlist_songs PK.

Revision ID: 002
Revises: 001
Create Date: 2025-03-05

- Add updated_at to artists, albums, songs, folders, playlists
- Add file_size, bitrate, imported_at, search_vector to songs
- Create recently_played table
- Recreate playlist_songs with PK (playlist_id, position), add added_at
- Index on folders.parent_id
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ----- updated_at on all main tables -----
    for table in ("artists", "albums", "songs", "folders", "playlists"):
        op.add_column(
            table,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )

    # ----- songs: file_size, bitrate, imported_at, search_vector -----
    op.add_column("songs", sa.Column("file_size", sa.Integer(), nullable=True))
    op.add_column("songs", sa.Column("bitrate", sa.Integer(), nullable=True))
    op.add_column(
        "songs",
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
    )
    op.add_column("songs", sa.Column("search_vector", sa.Text(), nullable=True))
    op.create_index("ix_songs_search_vector", "songs", ["search_vector"], unique=False)

    # ----- index on folders.parent_id -----
    op.create_index(op.f("ix_folders_parent_id"), "folders", ["parent_id"], unique=False)

    # ----- recently_played -----
    op.create_table(
        "recently_played",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("song_id", sa.Integer(), nullable=False),
        sa.Column(
            "played_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["song_id"], ["songs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_recently_played_played_at"),
        "recently_played",
        ["played_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recently_played_song_id"),
        "recently_played",
        ["song_id"],
        unique=False,
    )

    # ----- playlist_songs: new PK (playlist_id, position), add added_at -----
    op.create_table(
        "playlist_songs_new",
        sa.Column("playlist_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("song_id", sa.Integer(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["playlist_id"], ["playlists.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["song_id"], ["songs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("playlist_id", "position"),
    )
    # Copy data: order by existing position and assign new position 0,1,2...
    op.execute(
        """
        INSERT INTO playlist_songs_new (playlist_id, position, song_id, added_at)
        SELECT playlist_id, row_number() OVER (PARTITION BY playlist_id ORDER BY position) - 1, song_id, CURRENT_TIMESTAMP
        FROM playlist_songs
    """
    )
    op.drop_table("playlist_songs")
    op.rename_table("playlist_songs_new", "playlist_songs")


def downgrade() -> None:
    # Revert playlist_songs to (playlist_id, song_id) PK
    op.create_table(
        "playlist_songs_old",
        sa.Column("playlist_id", sa.Integer(), nullable=False),
        sa.Column("song_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["playlist_id"], ["playlists.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["song_id"], ["songs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("playlist_id", "song_id"),
    )
    op.execute(
        """
        INSERT INTO playlist_songs_old (playlist_id, song_id, position)
        SELECT playlist_id, song_id, position FROM playlist_songs ORDER BY playlist_id, position
    """
    )
    op.drop_table("playlist_songs")
    op.rename_table("playlist_songs_old", "playlist_songs")

    op.drop_index(
        op.f("ix_recently_played_song_id"), table_name="recently_played"
    )
    op.drop_index(
        op.f("ix_recently_played_played_at"), table_name="recently_played"
    )
    op.drop_table("recently_played")

    op.drop_index(op.f("ix_folders_parent_id"), table_name="folders")

    op.drop_index("ix_songs_search_vector", table_name="songs")
    op.drop_column("songs", "search_vector")
    op.drop_column("songs", "imported_at")
    op.drop_column("songs", "bitrate")
    op.drop_column("songs", "file_size")

    for table in ("artists", "albums", "songs", "folders", "playlists"):
        op.drop_column(table, "updated_at")

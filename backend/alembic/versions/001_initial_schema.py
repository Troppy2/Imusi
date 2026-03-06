"""Initial schema: artists, albums, songs, folders, folder_songs, playlists, playlist_songs

Revision ID: 001
Revises:
Create Date: 2025-03-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "artists",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_artists_name"), "artists", ["name"], unique=False)

    op.create_table(
        "albums",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("artist_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("artwork_path", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_albums_artist_id"), "albums", ["artist_id"], unique=False)
    op.create_index(op.f("ix_albums_title"), "albums", ["title"], unique=False)

    op.create_table(
        "folders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["folders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "playlists",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "songs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("artist_id", sa.Integer(), nullable=False),
        sa.Column("album_id", sa.Integer(), nullable=True),
        sa.Column("duration", sa.Float(), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("track_number", sa.Integer(), nullable=True),
        sa.Column("file_format", sa.String(length=16), nullable=False),
        sa.Column("artwork_path", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["album_id"], ["albums.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_path", name="uq_songs_file_path"),
    )
    op.create_index(op.f("ix_songs_album_id"), "songs", ["album_id"], unique=False)
    op.create_index(op.f("ix_songs_artist_id"), "songs", ["artist_id"], unique=False)
    op.create_index(op.f("ix_songs_title"), "songs", ["title"], unique=False)

    op.create_table(
        "folder_songs",
        sa.Column("folder_id", sa.Integer(), nullable=False),
        sa.Column("song_id", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["folder_id"], ["folders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["song_id"], ["songs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("folder_id", "song_id"),
        sa.UniqueConstraint("folder_id", "song_id", name="uq_folder_song"),
    )

    op.create_table(
        "playlist_songs",
        sa.Column("playlist_id", sa.Integer(), nullable=False),
        sa.Column("song_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["playlist_id"], ["playlists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["song_id"], ["songs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("playlist_id", "song_id"),
    )


def downgrade() -> None:
    op.drop_table("playlist_songs")
    op.drop_table("folder_songs")
    op.drop_index(op.f("ix_songs_title"), table_name="songs")
    op.drop_index(op.f("ix_songs_artist_id"), table_name="songs")
    op.drop_index(op.f("ix_songs_album_id"), table_name="songs")
    op.drop_table("songs")
    op.drop_table("playlists")
    op.drop_table("folders")
    op.drop_index(op.f("ix_albums_title"), table_name="albums")
    op.drop_index(op.f("ix_albums_artist_id"), table_name="albums")
    op.drop_table("albums")
    op.drop_index(op.f("ix_artists_name"), table_name="artists")
    op.drop_table("artists")

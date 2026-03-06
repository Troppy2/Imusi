#!/usr/bin/env python3
"""
Migrate data from a local SQLite database to a PostgreSQL database.

Usage:
    python scripts/migrate_sqlite_to_postgres.py \
        --sqlite "sqlite:///./data/imusi.db" \
        --postgres "postgresql://user:pass@host/imusi?sslmode=require"

This script:
1. Connects to both databases
2. Creates all tables in PostgreSQL (if they don't exist)
3. Copies all rows from each table, preserving IDs
4. Resets PostgreSQL sequences to avoid ID conflicts

Prerequisites:
    pip install sqlalchemy psycopg2-binary
"""
import argparse
import sys
from pathlib import Path

# Add backend root to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

from app.models import Base


# Tables in dependency order (parents before children)
TABLE_ORDER = [
    "artists",
    "albums",
    "users",
    "songs",
    "folders",
    "playlists",
    "folder_songs",
    "playlist_songs",
    "recently_played",
    "refresh_tokens",
]


def migrate(sqlite_url: str, postgres_url: str, *, dry_run: bool = False) -> None:
    # Fix postgres:// -> postgresql://
    if postgres_url.startswith("postgres://"):
        postgres_url = postgres_url.replace("postgres://", "postgresql://", 1)

    sqlite_engine = create_engine(sqlite_url)
    pg_engine = create_engine(postgres_url)

    # Create all tables in PostgreSQL
    print("Creating tables in PostgreSQL...")
    Base.metadata.create_all(bind=pg_engine)

    sqlite_session = sessionmaker(bind=sqlite_engine)()
    pg_session = sessionmaker(bind=pg_engine)()

    sqlite_inspector = inspect(sqlite_engine)
    existing_sqlite_tables = set(sqlite_inspector.get_table_names())

    try:
        for table_name in TABLE_ORDER:
            if table_name not in existing_sqlite_tables:
                print(f"  Skipping {table_name} (not in SQLite)")
                continue

            # Read all rows from SQLite
            rows = sqlite_session.execute(text(f"SELECT * FROM {table_name}")).fetchall()
            if not rows:
                print(f"  {table_name}: 0 rows (empty)")
                continue

            # Get column names
            columns = [col["name"] for col in sqlite_inspector.get_columns(table_name)]
            col_list = ", ".join(columns)
            param_list = ", ".join(f":{c}" for c in columns)

            if dry_run:
                print(f"  {table_name}: {len(rows)} rows (dry run)")
                continue

            # Clear existing data in PostgreSQL (in case of re-run)
            pg_session.execute(text(f"DELETE FROM {table_name}"))

            # Insert rows
            insert_sql = text(f"INSERT INTO {table_name} ({col_list}) VALUES ({param_list})")
            for row in rows:
                row_dict = dict(zip(columns, row))
                pg_session.execute(insert_sql, row_dict)

            print(f"  {table_name}: {len(rows)} rows migrated")

        if not dry_run:
            # Reset PostgreSQL sequences for auto-increment columns
            print("\nResetting PostgreSQL sequences...")
            for table_name in TABLE_ORDER:
                if table_name not in existing_sqlite_tables:
                    continue
                pg_inspector = inspect(pg_engine)
                pg_columns = pg_inspector.get_columns(table_name)
                for col in pg_columns:
                    if col.get("autoincrement") or col["name"] == "id":
                        seq_name = f"{table_name}_{col['name']}_seq"
                        try:
                            pg_session.execute(text(
                                f"SELECT setval('{seq_name}', COALESCE((SELECT MAX({col['name']}) FROM {table_name}), 0) + 1, false)"
                            ))
                            print(f"  Reset sequence: {seq_name}")
                        except Exception:
                            pass  # Sequence might not exist for composite PKs

            pg_session.commit()
            print("\nMigration complete!")
        else:
            print("\nDry run complete. No data was written.")

    except Exception as e:
        pg_session.rollback()
        print(f"\nMigration failed: {e}")
        raise
    finally:
        sqlite_session.close()
        pg_session.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate IMUSI data from SQLite to PostgreSQL")
    parser.add_argument("--sqlite", required=True, help="SQLite connection URL")
    parser.add_argument("--postgres", required=True, help="PostgreSQL connection URL")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without writing")
    args = parser.parse_args()
    migrate(args.sqlite, args.postgres, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path
from typing import Final

from backend.app.persistence.db import get_connection


MIGRATIONS_DIR: Final[Path] = Path(
    "backend/app/persistence/migrations/sql"
)


def ensure_migrations_table() -> None:
    """
    Creates the migration tracking table if it does not exist.
    """

    conn = get_connection()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


def get_applied_versions() -> set[str]:
    """
    Returns all previously applied migration versions.
    """

    ensure_migrations_table()

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT version
        FROM schema_migrations
        """
    ).fetchall()

    return {row["version"] for row in rows}


def run_migrations() -> None:
    """
    Executes all pending SQL migrations in order.
    """

    ensure_migrations_table()

    MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)

    applied_versions = get_applied_versions()

    conn = get_connection()

    migration_files = sorted(
        MIGRATIONS_DIR.glob("*.sql")
    )

    for migration_file in migration_files:
        version = migration_file.stem

        if version in applied_versions:
            continue

        sql = migration_file.read_text(
            encoding="utf-8"
        )

        with conn:
            conn.executescript(sql)

            conn.execute(
                """
                INSERT INTO schema_migrations (
                    version,
                    applied_at
                )
                VALUES (
                    ?,
                    datetime('now')
                )
                """,
                (version,),
            )

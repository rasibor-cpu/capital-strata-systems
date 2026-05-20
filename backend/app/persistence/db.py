from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Optional


_DB_LOCK = threading.RLock()
_CONNECTION: Optional[sqlite3.Connection] = None

DEFAULT_DB_PATH = Path("data/css_runtime.db")


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Returns the singleton SQLite connection.

    Thread-safe.
    WAL-enabled.
    Foreign-key enforcement enabled.
    """

    global _CONNECTION

    with _DB_LOCK:
        if _CONNECTION is not None:
            return _CONNECTION

        resolved_path = db_path or DEFAULT_DB_PATH
        resolved_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(
            resolved_path,
            check_same_thread=False,
            isolation_level=None,
        )

        conn.row_factory = sqlite3.Row

        _configure_connection(conn)

        _CONNECTION = conn

        return conn


def _configure_connection(conn: sqlite3.Connection) -> None:
    """
    Applies all required SQLite runtime configuration.
    """

    cursor = conn.cursor()

    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA temp_store=MEMORY;")

    cursor.close()


def close_connection() -> None:
    """
    Gracefully closes the singleton DB connection.
    """

    global _CONNECTION

    with _DB_LOCK:
        if _CONNECTION is not None:
            _CONNECTION.close()
            _CONNECTION = None

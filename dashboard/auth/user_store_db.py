from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict


class SQLiteUserStore:
    """
    Lightweight local DB-backed user store.

    The record payload preserves the existing CSS auth schema, including hashed
    credentials and RBAC fields, while the SQLite layer provides restart-safe,
    auditable persistence for deployments that opt in via CSS_AUTH_STORE=db.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load_users(self) -> Dict[str, Any]:
        self._ensure_schema()
        users: Dict[str, Any] = {}
        conn = self._connect()
        try:
            for user_id, payload in conn.execute("SELECT user_id, payload FROM users ORDER BY user_id"):
                try:
                    record = json.loads(str(payload))
                except Exception:
                    continue
                if isinstance(record, dict):
                    users[str(user_id)] = record
        finally:
            conn.close()
        return users

    def save_users(self, users: Dict[str, Any]) -> None:
        self._ensure_schema()
        conn = self._connect()
        try:
            conn.execute("DELETE FROM users")
            for user_id, record in sorted(users.items()):
                if not isinstance(record, dict):
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO users(user_id, payload) VALUES(?, ?)",
                    (str(user_id), json.dumps(record, sort_keys=True)),
                )
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path)

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

from __future__ import annotations

import sqlite3
from typing import Any

from backend.app.persistence.db import get_connection


class BaseRepository:
    """
    Base repository abstraction for all persistence repositories.

    Centralizes:
    - DB connection access
    - transaction execution
    - common fetch helpers
    """

    @property
    def connection(self) -> sqlite3.Connection:
        return get_connection()

    def execute(
        self,
        sql: str,
        parameters: tuple[Any, ...] = (),
    ) -> sqlite3.Cursor:
        return self.connection.execute(sql, parameters)

    def executemany(
        self,
        sql: str,
        parameter_sets: list[tuple[Any, ...]],
    ) -> sqlite3.Cursor:
        return self.connection.executemany(sql, parameter_sets)

    def fetch_one(
        self,
        sql: str,
        parameters: tuple[Any, ...] = (),
    ) -> sqlite3.Row | None:
        cursor = self.connection.execute(sql, parameters)
        return cursor.fetchone()

    def fetch_all(
        self,
        sql: str,
        parameters: tuple[Any, ...] = (),
    ) -> list[sqlite3.Row]:
        cursor = self.connection.execute(sql, parameters)
        return list(cursor.fetchall())

    def transaction(self) -> sqlite3.Connection:
        return self.connection
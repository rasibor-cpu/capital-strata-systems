from __future__ import annotations

import sqlite3

import backend.app.persistence.db as db_module
import backend.app.persistence.migrations.runner as migration_runner
from backend.app.persistence.services.persistence_service import (
    PersistenceService,
)
from backend.app.persistence.repositories.attributable_performance_repository import (
    AttributablePerformanceRepository,
)


def _isolated_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def test_persistence_service_registers_attributable_performance(
    monkeypatch,
):
    connection = _isolated_connection()

    monkeypatch.setattr(
        db_module,
        "get_connection",
        lambda: connection,
    )
    monkeypatch.setattr(
        migration_runner,
        "get_connection",
        lambda: connection,
    )

    try:
        service = PersistenceService()

        assert isinstance(
            service.attributable_performance,
            AttributablePerformanceRepository,
        )

        health = service.healthcheck()

        assert (
            health["repositories"]["attributable_performance"]
            is True
        )
    finally:
        connection.close()


def test_migration_006_is_applied_by_persistence_service(
    monkeypatch,
):
    connection = _isolated_connection()

    monkeypatch.setattr(
        db_module,
        "get_connection",
        lambda: connection,
    )
    monkeypatch.setattr(
        migration_runner,
        "get_connection",
        lambda: connection,
    )

    try:
        PersistenceService()

        row = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'attributable_performance'
            """
        ).fetchone()

        assert row is not None
        assert row["name"] == "attributable_performance"
    finally:
        connection.close()


def test_service_registration_does_not_grant_execution_or_fee_authority(
    monkeypatch,
):
    connection = _isolated_connection()

    monkeypatch.setattr(
        db_module,
        "get_connection",
        lambda: connection,
    )
    monkeypatch.setattr(
        migration_runner,
        "get_connection",
        lambda: connection,
    )

    try:
        service = PersistenceService()

        repo = service.attributable_performance

        assert not hasattr(repo, "execute_trade")
        assert not hasattr(repo, "collect_fee")
        assert not hasattr(repo, "deduct_client_funds")
    finally:
        connection.close()

from __future__ import annotations

import sqlite3

import backend.app.persistence.db as db_module
import backend.app.persistence.migrations.runner as migration_runner

from backend.app.persistence.repositories.performance_accounting_transition_repository import (
    PerformanceAccountingTransitionRepository,
)
from backend.app.persistence.services.persistence_service import (
    PersistenceService,
)


def _isolated_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _patch_connection(
    monkeypatch,
    connection: sqlite3.Connection,
) -> None:
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


def test_persistence_service_registers_performance_accounting_transitions(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        assert isinstance(
            service.performance_accounting_transitions,
            PerformanceAccountingTransitionRepository,
        )

        health = service.healthcheck()

        assert (
            health["repositories"][
                "performance_accounting_transitions"
            ]
            is True
        )
    finally:
        connection.close()


def test_migration_007_is_applied_by_persistence_service(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        PersistenceService()

        row = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'performance_accounting_transitions'
            """
        ).fetchone()

        assert row is not None
        assert (
            row["name"]
            == "performance_accounting_transitions"
        )

        migration_row = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            WHERE version = ?
            """,
            ("007_performance_accounting_transitions",),
        ).fetchone()

        assert migration_row is not None
        assert (
            migration_row["version"]
            == "007_performance_accounting_transitions"
        )
    finally:
        connection.close()


def test_service_registration_preserves_insert_only_repository_contract(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        repo = service.performance_accounting_transitions

        assert hasattr(repo, "create_transition")
        assert hasattr(repo, "get_by_trade_id")
        assert hasattr(repo, "list_all")

        assert not hasattr(repo, "update_transition")
        assert not hasattr(repo, "delete_transition")
    finally:
        connection.close()


def test_service_registration_does_not_grant_fee_or_execution_authority(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        repo = service.performance_accounting_transitions

        assert not hasattr(repo, "collect_fee")
        assert not hasattr(repo, "create_fee_receivable")
        assert not hasattr(repo, "deduct_client_funds")
        assert not hasattr(repo, "execute_trade")
    finally:
        connection.close()

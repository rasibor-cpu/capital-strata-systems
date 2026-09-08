from __future__ import annotations

import sqlite3

import backend.app.persistence.db as db_module
import backend.app.persistence.migrations.runner as migration_runner

from backend.app.persistence.repositories.performance_compensation_terms_repository import (
    PerformanceCompensationTermsRepository,
)
from backend.app.persistence.repositories.shadow_compensation_entitlement_repository import (
    ShadowCompensationEntitlementRepository,
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


def test_persistence_service_registers_performance_compensation_terms(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        assert isinstance(
            service.performance_compensation_terms,
            PerformanceCompensationTermsRepository,
        )

        health = service.healthcheck()

        assert (
            health["repositories"][
                "performance_compensation_terms"
            ]
            is True
        )
    finally:
        connection.close()


def test_persistence_service_registers_shadow_compensation_entitlements(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        assert isinstance(
            service.shadow_compensation_entitlements,
            ShadowCompensationEntitlementRepository,
        )

        health = service.healthcheck()

        assert (
            health["repositories"][
                "shadow_compensation_entitlements"
            ]
            is True
        )
    finally:
        connection.close()


def test_migration_008_is_applied_by_persistence_service(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        PersistenceService()

        tables = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name IN (
                    'performance_compensation_terms',
                    'shadow_compensation_entitlements'
                  )
                """
            ).fetchall()
        }

        assert tables == {
            "performance_compensation_terms",
            "shadow_compensation_entitlements",
        }

        migration_row = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            WHERE version = ?
            """,
            ("008_performance_compensation",),
        ).fetchone()

        assert migration_row is not None
        assert (
            migration_row["version"]
            == "008_performance_compensation"
        )
    finally:
        connection.close()


def test_terms_repository_remains_insert_only_through_service(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.performance_compensation_terms

        assert hasattr(repo, "create_terms")
        assert hasattr(repo, "get_by_terms_id")
        assert hasattr(repo, "list_all")

        assert not hasattr(repo, "update_terms")
        assert not hasattr(repo, "delete_terms")
        assert not hasattr(repo, "update")
        assert not hasattr(repo, "delete")
    finally:
        connection.close()


def test_entitlement_repository_remains_insert_only_through_service(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.shadow_compensation_entitlements

        assert hasattr(repo, "create_entitlement")
        assert hasattr(repo, "get_by_trade_id")
        assert hasattr(repo, "get_by_terms_id")
        assert hasattr(repo, "list_all")

        assert not hasattr(repo, "update_entitlement")
        assert not hasattr(repo, "delete_entitlement")
        assert not hasattr(repo, "update")
        assert not hasattr(repo, "delete")
    finally:
        connection.close()


def test_service_registration_does_not_grant_fee_or_money_movement_authority(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repos = (
            service.performance_compensation_terms,
            service.shadow_compensation_entitlements,
        )

        forbidden = (
            "collect_fee",
            "deduct_client_funds",
            "automatic_debit",
            "settle_invoice",
            "execute_trade",
            "transfer_funds",
            "withdraw",
        )

        for repo in repos:
            for method_name in forbidden:
                assert not hasattr(repo, method_name)
    finally:
        connection.close()

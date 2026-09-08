from __future__ import annotations

import sqlite3

import backend.app.persistence.db as db_module
import backend.app.persistence.migrations.runner as migration_runner

from backend.app.persistence.repositories.crystallization_assessment_repository import (
    CrystallizationAssessmentRepository,
)
from backend.app.persistence.repositories.performance_compensation_lifecycle_policy_repository import (
    PerformanceCompensationLifecyclePolicyRepository,
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


def test_persistence_service_registers_lifecycle_policy_repository(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        assert isinstance(
            service.performance_compensation_lifecycle_policies,
            PerformanceCompensationLifecyclePolicyRepository,
        )

        health = service.healthcheck()

        assert (
            health["repositories"][
                "performance_compensation_lifecycle_policies"
            ]
            is True
        )
    finally:
        connection.close()


def test_persistence_service_registers_crystallization_assessment_repository(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        assert isinstance(
            service.crystallization_assessments,
            CrystallizationAssessmentRepository,
        )

        health = service.healthcheck()

        assert (
            health["repositories"][
                "crystallization_assessments"
            ]
            is True
        )
    finally:
        connection.close()


def test_migration_009_is_applied_by_persistence_service(
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
                    'performance_compensation_lifecycle_policies',
                    'crystallization_assessments'
                  )
                """
            ).fetchall()
        }

        assert tables == {
            "performance_compensation_lifecycle_policies",
            "crystallization_assessments",
        }

        migration_row = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            WHERE version = ?
            """,
            ("009_performance_crystallization",),
        ).fetchone()

        assert migration_row is not None
        assert (
            migration_row["version"]
            == "009_performance_crystallization"
        )
    finally:
        connection.close()


def test_lifecycle_policy_repository_remains_insert_only_through_service(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.performance_compensation_lifecycle_policies

        assert hasattr(repo, "create_policy")
        assert hasattr(repo, "get_by_policy_id")
        assert hasattr(repo, "get_by_terms_id")
        assert hasattr(repo, "list_all")

        assert not hasattr(repo, "update_policy")
        assert not hasattr(repo, "delete_policy")
        assert not hasattr(repo, "update")
        assert not hasattr(repo, "delete")
    finally:
        connection.close()


def test_crystallization_assessment_repository_remains_insert_only_through_service(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.crystallization_assessments

        assert hasattr(repo, "create_assessment")
        assert hasattr(repo, "get_by_period")
        assert hasattr(repo, "get_by_policy_id")
        assert hasattr(repo, "list_all")

        assert not hasattr(repo, "update_assessment")
        assert not hasattr(repo, "delete_assessment")
        assert not hasattr(repo, "update")
        assert not hasattr(repo, "delete")
    finally:
        connection.close()


def test_service_registration_does_not_grant_collection_or_money_movement_authority(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repos = (
            service.performance_compensation_lifecycle_policies,
            service.crystallization_assessments,
        )

        forbidden = (
            "collect_fee",
            "deduct_client_funds",
            "automatic_debit",
            "settle_invoice",
            "transfer_funds",
            "withdraw",
            "execute_trade",
        )

        for repo in repos:
            for method_name in forbidden:
                assert not hasattr(repo, method_name)
    finally:
        connection.close()

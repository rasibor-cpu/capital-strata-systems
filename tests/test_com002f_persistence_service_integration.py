from __future__ import annotations

import sqlite3

import backend.app.persistence.db as db_module
import backend.app.persistence.migrations.runner as migration_runner

from backend.app.persistence.repositories.settlement_readiness_repository import (
    SettlementReadinessRepository,
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


def test_persistence_service_registers_settlement_readiness_repository(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        assert isinstance(
            service.settlement_readiness,
            SettlementReadinessRepository,
        )

        health = service.healthcheck()

        assert (
            health["repositories"]["settlement_readiness"]
            is True
        )
    finally:
        connection.close()


def test_migration_010_is_applied_by_persistence_service(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        PersistenceService()

        table_row = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'commercial_settlement_readiness'
            """
        ).fetchone()

        assert table_row is not None
        assert table_row["name"] == "commercial_settlement_readiness"

        migration_row = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            WHERE version = ?
            """,
            ("010_settlement_readiness",),
        ).fetchone()

        assert migration_row is not None
        assert migration_row["version"] == "010_settlement_readiness"
    finally:
        connection.close()


def test_settlement_readiness_repository_remains_insert_only_through_service(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.settlement_readiness

        assert hasattr(repo, "create_readiness")
        assert hasattr(repo, "get_by_period")
        assert hasattr(repo, "get_by_policy_id")
        assert hasattr(repo, "get_by_terms_id")
        assert hasattr(repo, "list_all")

        assert not hasattr(repo, "update_readiness")
        assert not hasattr(repo, "delete_readiness")
        assert not hasattr(repo, "update")
        assert not hasattr(repo, "delete")
    finally:
        connection.close()


def test_service_registration_does_not_grant_payment_or_money_movement_authority(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.settlement_readiness

        forbidden = (
            "collect_fee",
            "deduct_client_funds",
            "automatic_debit",
            "settle_invoice",
            "initiate_payment",
            "transfer_funds",
            "withdraw",
            "execute_trade",
        )

        for method_name in forbidden:
            assert not hasattr(repo, method_name)
    finally:
        connection.close()


def test_composite_relationship_survives_service_migrations(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        PersistenceService()

        fk_rows = connection.execute(
            """
            PRAGMA foreign_key_list('commercial_settlement_readiness')
            """
        ).fetchall()

        assessment_cols = {
            row["from"]: row
            for row in fk_rows
            if row["table"] == "crystallization_assessments"
        }
        terms_cols = {
            row["from"]: row
            for row in fk_rows
            if row["table"] == "performance_compensation_terms"
        }

        assert set(assessment_cols) == {
            "policy_id",
            "period_start",
            "period_end",
        }
        assert assessment_cols["policy_id"]["to"] == "policy_id"
        assert assessment_cols["period_start"]["to"] == "period_start"
        assert assessment_cols["period_end"]["to"] == "period_end"

        assessment_ids = {
            row["id"]
            for row in fk_rows
            if row["table"] == "crystallization_assessments"
        }
        assert len(assessment_ids) == 1

        for row in assessment_cols.values():
            assert row["on_delete"] in ("RESTRICT", "NO ACTION")

        assert set(terms_cols) == {"terms_id"}
        assert terms_cols["terms_id"]["to"] == "terms_id"
        assert terms_cols["terms_id"]["on_delete"] in (
            "RESTRICT",
            "NO ACTION",
        )
    finally:
        connection.close()

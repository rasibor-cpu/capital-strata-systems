from __future__ import annotations

import sqlite3

import backend.app.persistence.db as db_module
import backend.app.persistence.migrations.runner as migration_runner

from backend.app.persistence.repositories.billable_obligation_repository import (
    BillableObligationRepository,
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


def test_persistence_service_registers_billable_obligation_repository(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        assert isinstance(
            service.billable_obligations,
            BillableObligationRepository,
        )

        health = service.healthcheck()

        assert (
            health["repositories"]["billable_obligations"]
            is True
        )
    finally:
        connection.close()


def test_migration_011_is_applied_by_persistence_service(
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
              AND name = 'commercial_billable_obligations'
            """
        ).fetchone()

        assert table_row is not None
        assert table_row["name"] == "commercial_billable_obligations"

        migration_row = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            WHERE version = ?
            """,
            ("011_billable_obligation",),
        ).fetchone()

        assert migration_row is not None
        assert migration_row["version"] == "011_billable_obligation"
    finally:
        connection.close()


def test_billable_obligation_repository_remains_insert_only_through_service(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.billable_obligations

        assert hasattr(repo, "create_obligation")
        assert hasattr(repo, "get_by_period")
        assert hasattr(repo, "get_by_policy_id")
        assert hasattr(repo, "get_by_terms_id")
        assert hasattr(repo, "list_all")

        assert not hasattr(repo, "update_obligation")
        assert not hasattr(repo, "delete_obligation")
        assert not hasattr(repo, "update")
        assert not hasattr(repo, "delete")
    finally:
        connection.close()


def test_service_registration_does_not_add_invoice_or_receivable_authority(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.billable_obligations

        forbidden = (
            "create_invoice",
            "create_receivable",
            "post_to_ledger",
            "recognize_revenue",
            "calculate_tax",
        )

        for method_name in forbidden:
            assert not hasattr(repo, method_name)
    finally:
        connection.close()


def test_service_registration_does_not_grant_payment_or_money_movement_authority(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.billable_obligations

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


def test_readiness_composite_fk_survives_service_migrations(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        PersistenceService()

        fk_rows = connection.execute(
            """
            PRAGMA foreign_key_list('commercial_billable_obligations')
            """
        ).fetchall()

        readiness_cols = {
            row["from"]: row
            for row in fk_rows
            if row["table"] == "commercial_settlement_readiness"
        }
        terms_cols = {
            row["from"]: row
            for row in fk_rows
            if row["table"] == "performance_compensation_terms"
        }

        assert set(readiness_cols) == {
            "policy_id",
            "period_start",
            "period_end",
        }
        assert readiness_cols["policy_id"]["to"] == "policy_id"
        assert readiness_cols["period_start"]["to"] == "period_start"
        assert readiness_cols["period_end"]["to"] == "period_end"

        readiness_ids = {
            row["id"]
            for row in fk_rows
            if row["table"] == "commercial_settlement_readiness"
        }
        assert len(readiness_ids) == 1

        for row in readiness_cols.values():
            assert row["on_delete"] in ("RESTRICT", "NO ACTION")

        assert set(terms_cols) == {"terms_id"}
        assert terms_cols["terms_id"]["to"] == "terms_id"
        assert terms_cols["terms_id"]["on_delete"] in (
            "RESTRICT",
            "NO ACTION",
        )
    finally:
        connection.close()


def test_billable_table_has_no_invoice_ar_or_tax_columns(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        PersistenceService()

        columns = {
            row["name"]
            for row in connection.execute(
                """
                PRAGMA table_info('commercial_billable_obligations')
                """
            ).fetchall()
        }

        forbidden_columns = {
            "invoice_id",
            "invoice_number",
            "invoice_date",
            "receivable_id",
            "amount_due",
            "balance_due",
            "due_date",
            "tax_rate",
            "tax_amount",
            "billing_party_id",
            "client_id",
            "customer_id",
        }

        assert columns.isdisjoint(forbidden_columns)
        assert {
            "policy_id",
            "terms_id",
            "currency",
            "period_start",
            "period_end",
            "billable_amount",
            "recognized_at",
            "status",
            "evidence_refs_json",
            "created_at",
        }.issubset(columns)
    finally:
        connection.close()

from __future__ import annotations

import sqlite3

import backend.app.persistence.db as db_module
import backend.app.persistence.migrations.runner as migration_runner

from backend.app.persistence.repositories.invoice_correction_repository import (
    InvoiceCorrectionRepository,
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


def test_persistence_service_registers_invoice_correction_repository(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        assert isinstance(
            service.invoice_corrections,
            InvoiceCorrectionRepository,
        )

        health = service.healthcheck()

        assert health["repositories"]["invoice_corrections"] is True
    finally:
        connection.close()


def test_migration_016_is_applied_by_persistence_service(
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
              AND name = 'commercial_invoice_corrections'
            """
        ).fetchone()

        assert table_row is not None
        assert table_row["name"] == "commercial_invoice_corrections"

        migration_row = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            WHERE version = ?
            """,
            ("016_invoice_correction",),
        ).fetchone()

        assert migration_row is not None
        assert migration_row["version"] == "016_invoice_correction"
    finally:
        connection.close()


def test_foreign_keys_survive_service_migrations(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        PersistenceService()

        fk_rows = connection.execute(
            """
            PRAGMA foreign_key_list(
                'commercial_invoice_corrections'
            )
            """
        ).fetchall()

        original_cols = {
            row["from"]: row
            for row in fk_rows
            if row["from"] == "invoice_id"
            and row["table"] == "commercial_invoice_issued_records"
        }
        replacement_cols = {
            row["from"]: row
            for row in fk_rows
            if row["from"] == "replacement_invoice_id"
            and row["table"] == "commercial_invoice_issued_records"
        }

        assert set(original_cols) == {"invoice_id"}
        assert original_cols["invoice_id"]["to"] == "invoice_id"
        assert original_cols["invoice_id"]["on_delete"] in (
            "RESTRICT",
            "NO ACTION",
        )

        assert set(replacement_cols) == {"replacement_invoice_id"}
        assert replacement_cols["replacement_invoice_id"]["to"] == (
            "invoice_id"
        )
        assert replacement_cols["replacement_invoice_id"][
            "on_delete"
        ] in ("RESTRICT", "NO ACTION")
    finally:
        connection.close()


def test_conditional_void_supersede_check_survives_migrations(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        PersistenceService()

        sql = connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'commercial_invoice_corrections'
            """
        ).fetchone()["sql"]

        assert "VOID" in sql
        assert "SUPERSEDE" in sql
        assert "replacement_invoice_id IS NULL" in sql
        assert "replacement_invoice_id IS NOT NULL" in sql
        assert "replacement_invoice_id <> invoice_id" in sql
    finally:
        connection.close()


def test_invoice_correction_repository_remains_insert_only_through_service(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.invoice_corrections

        assert hasattr(repo, "create_correction")
        assert hasattr(repo, "get_by_correction_id")
        assert hasattr(repo, "get_by_invoice_id")
        assert hasattr(repo, "get_by_replacement_invoice_id")
        assert hasattr(repo, "list_all")

        assert not hasattr(repo, "update_correction")
        assert not hasattr(repo, "delete_correction")
        assert not hasattr(repo, "update")
        assert not hasattr(repo, "delete")
    finally:
        connection.close()


def test_multiple_corrections_per_invoice_remain_allowed_structurally(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        PersistenceService()

        index_rows = connection.execute(
            """
            PRAGMA index_list('commercial_invoice_corrections')
            """
        ).fetchall()

        unique_col_sets = []
        for index in index_rows:
            if index["unique"] != 1:
                continue
            cols = connection.execute(
                f"PRAGMA index_info('{index['name']}')"
            ).fetchall()
            unique_col_sets.append(
                tuple(col["name"] for col in cols)
            )

        assert ("invoice_id",) not in unique_col_sets
        assert not any(
            set(cols) == {"invoice_id"} for cols in unique_col_sets
        )
    finally:
        connection.close()


def test_service_registration_does_not_add_prohibited_authority(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.invoice_corrections

        forbidden = (
            "mutate_invoice",
            "void_invoice",
            "supersede_invoice",
            "create_replacement_invoice",
            "create_credit_note",
            "adjust_receivable",
            "reverse_ledger",
            "reverse_revenue",
            "issue_refund",
            "collect_fee",
            "deduct_client_funds",
            "automatic_debit",
            "initiate_payment",
            "transfer_funds",
            "withdraw",
            "execute_trade",
        )

        for method_name in forbidden:
            assert not hasattr(repo, method_name)
            assert not hasattr(service, method_name)
    finally:
        connection.close()


def test_invoice_correction_table_has_no_prohibited_columns(
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
                PRAGMA table_info(
                    'commercial_invoice_corrections'
                )
                """
            ).fetchall()
        }

        forbidden_columns = {
            "credit_amount",
            "credit_note_id",
            "refund_amount",
            "receivable_adjustment",
            "revenue_reversal",
            "journal_id",
            "ar_account",
            "payment_status",
            "collection_status",
            "voided_at",
            "superseded_status",
        }

        assert columns.isdisjoint(forbidden_columns)
        assert {
            "correction_id",
            "invoice_id",
            "correction_type",
            "corrected_at",
            "reason_reference",
            "evidence_refs_json",
            "replacement_invoice_id",
            "created_at",
        }.issubset(columns)
    finally:
        connection.close()

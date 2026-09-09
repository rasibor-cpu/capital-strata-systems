from __future__ import annotations

import sqlite3

import backend.app.persistence.db as db_module
import backend.app.persistence.migrations.runner as migration_runner

from backend.app.persistence.repositories.receivable_reversal_repository import (
    ReceivableReversalRepository,
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


def test_persistence_service_registers_receivable_reversal_repository(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        assert isinstance(
            service.receivable_reversals,
            ReceivableReversalRepository,
        )

        health = service.healthcheck()

        assert health["repositories"]["receivable_reversals"] is True
    finally:
        connection.close()


def test_migration_018_is_applied_by_persistence_service(
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
              AND name = 'commercial_receivable_reversals'
            """
        ).fetchone()

        assert table_row is not None
        assert table_row["name"] == "commercial_receivable_reversals"

        migration_row = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            WHERE version = ?
            """,
            ("018_receivable_reversal",),
        ).fetchone()

        assert migration_row is not None
        assert migration_row["version"] == "018_receivable_reversal"
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
                'commercial_receivable_reversals'
            )
            """
        ).fetchall()

        receivable_cols = {
            row["from"]: row
            for row in fk_rows
            if row["table"] == "commercial_receivable_recognitions"
        }
        issued_cols = {
            row["from"]: row
            for row in fk_rows
            if row["table"] == "commercial_invoice_issued_records"
        }
        correction_cols = {
            row["from"]: row
            for row in fk_rows
            if row["table"] == "commercial_invoice_corrections"
        }

        assert set(receivable_cols) == {"receivable_id"}
        assert receivable_cols["receivable_id"]["to"] == "receivable_id"
        assert receivable_cols["receivable_id"]["on_delete"] in (
            "RESTRICT",
            "NO ACTION",
        )

        assert set(issued_cols) == {"invoice_id"}
        assert issued_cols["invoice_id"]["to"] == "invoice_id"
        assert issued_cols["invoice_id"]["on_delete"] in (
            "RESTRICT",
            "NO ACTION",
        )

        assert set(correction_cols) == {"correction_id"}
        assert correction_cols["correction_id"]["to"] == "correction_id"
        assert correction_cols["correction_id"]["on_delete"] in (
            "RESTRICT",
            "NO ACTION",
        )
    finally:
        connection.close()


def test_receivable_id_uniqueness_preserved(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        PersistenceService()

        index_rows = connection.execute(
            """
            PRAGMA index_list(
                'commercial_receivable_reversals'
            )
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

        assert ("receivable_id",) in unique_col_sets or any(
            set(cols) == {"receivable_id"} for cols in unique_col_sets
        )
    finally:
        connection.close()


def test_receivable_reversal_repository_remains_insert_only(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.receivable_reversals

        assert hasattr(repo, "create_reversal")
        assert hasattr(repo, "get_by_reversal_id")
        assert hasattr(repo, "get_by_receivable_id")
        assert hasattr(repo, "get_by_invoice_id")
        assert hasattr(repo, "get_by_correction_id")
        assert hasattr(repo, "list_all")

        assert not hasattr(repo, "update_reversal")
        assert not hasattr(repo, "delete_reversal")
        assert not hasattr(repo, "update")
        assert not hasattr(repo, "delete")
    finally:
        connection.close()


def test_no_raw_reversal_bypass_api(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.receivable_reversals

        assert not hasattr(repo, "reverse_receivable")
        assert not hasattr(service, "reverse_receivable")
        assert not hasattr(repo, "reverse_invoice")
        assert not hasattr(service, "reverse_invoice")
        assert not hasattr(repo, "create_reversal_from_ids")
        assert not hasattr(service, "create_reversal_from_ids")
    finally:
        connection.close()


def test_service_registration_does_not_add_prohibited_authority(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.receivable_reversals

        forbidden = (
            "reverse_receivable",
            "reverse_invoice",
            "rereverse_receivable",
            "adjust_receivable",
            "create_partial_adjustment",
            "create_outstanding_balance",
            "apply_payment",
            "writeoff_receivable",
            "create_credit_note",
            "post_to_ledger",
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


def test_receivable_reversal_table_has_no_prohibited_columns(
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
                    'commercial_receivable_reversals'
                )
                """
            ).fetchall()
        }

        forbidden_columns = {
            "adjustment_type",
            "reversal_type",
            "status",
            "reversal_status",
            "adjustment_amount",
            "partial_amount",
            "remaining_amount",
            "net_amount",
            "outstanding_amount",
            "balance_due",
            "amount_paid",
            "amount_credited",
            "amount_written_off",
            "journal_id",
            "ar_account",
            "revenue_account",
            "credit_amount",
            "credit_note_id",
            "writeoff_amount",
            "refund_amount",
            "payment_status",
            "collection_status",
        }

        assert columns.isdisjoint(forbidden_columns)
        assert {
            "reversal_id",
            "receivable_id",
            "invoice_id",
            "correction_id",
            "currency",
            "reversal_amount",
            "reversed_at",
            "reason_reference",
            "evidence_refs_json",
            "created_at",
        }.issubset(columns)
    finally:
        connection.close()

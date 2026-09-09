from __future__ import annotations

import sqlite3

import backend.app.persistence.db as db_module
import backend.app.persistence.migrations.runner as migration_runner

from backend.app.persistence.repositories.receivable_due_repository import (
    ReceivableDueRepository,
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


def test_persistence_service_registers_receivable_due_repository(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        assert isinstance(
            service.receivable_due_records,
            ReceivableDueRepository,
        )

        health = service.healthcheck()

        assert health["repositories"]["receivable_due_records"] is True
    finally:
        connection.close()


def test_migration_019_is_applied_by_persistence_service(
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
              AND name = 'commercial_receivable_due_records'
            """
        ).fetchone()

        assert table_row is not None
        assert table_row["name"] == "commercial_receivable_due_records"

        migration_row = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            WHERE version = ?
            """,
            ("019_receivable_due",),
        ).fetchone()

        assert migration_row is not None
        assert migration_row["version"] == "019_receivable_due"
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
                'commercial_receivable_due_records'
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

        assert all(
            row["table"]
            not in (
                "commercial_receivable_reversals",
                "customers",
                "accounts",
            )
            for row in fk_rows
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
                'commercial_receivable_due_records'
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


def test_receivable_due_repository_remains_insert_only(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.receivable_due_records

        assert hasattr(repo, "create_due_record")
        assert hasattr(repo, "get_by_due_record_id")
        assert hasattr(repo, "get_by_receivable_id")
        assert hasattr(repo, "get_by_invoice_id")
        assert hasattr(repo, "list_all")

        assert not hasattr(repo, "update_due_record")
        assert not hasattr(repo, "delete_due_record")
        assert not hasattr(repo, "update")
        assert not hasattr(repo, "delete")
    finally:
        connection.close()


def test_no_raw_due_date_bypass_api(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.receivable_due_records

        assert not hasattr(repo, "set_due_date")
        assert not hasattr(service, "set_due_date")
        assert not hasattr(repo, "determine_due_date")
        assert not hasattr(service, "determine_due_date")
        assert not hasattr(repo, "create_due_record_from_ids")
        assert not hasattr(service, "create_due_record_from_ids")
    finally:
        connection.close()


def test_service_registration_does_not_add_prohibited_authority(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.receivable_due_records

        forbidden = (
            "set_due_date",
            "determine_due_date",
            "redetermine_due_date",
            "mark_due",
            "mark_overdue",
            "create_outstanding_balance",
            "update_balance",
            "apply_payment",
            "writeoff_receivable",
            "create_credit_note",
            "post_to_ledger",
            "recognize_revenue_posting",
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


def test_receivable_due_table_has_no_prohibited_columns(
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
                    'commercial_receivable_due_records'
                )
                """
            ).fetchall()
        }

        forbidden_columns = {
            "status",
            "due_status",
            "overdue_status",
            "is_due",
            "is_overdue",
            "days_overdue",
            "days_outstanding",
            "ageing_bucket",
            "aging_bucket",
            "outstanding_amount",
            "balance_due",
            "amount_due",
            "remaining_amount",
            "amount_paid",
            "amount_credited",
            "amount_written_off",
            "net_days",
            "grace_days",
            "business_days",
            "payment_term_days",
            "journal_id",
            "ar_account",
            "revenue_account",
            "payment_status",
            "collection_status",
            "credit_amount",
            "credit_note_id",
            "writeoff_amount",
        }

        assert columns.isdisjoint(forbidden_columns)
        assert {
            "due_record_id",
            "receivable_id",
            "invoice_id",
            "due_date",
            "determined_at",
            "terms_reference",
            "evidence_refs_json",
            "created_at",
        }.issubset(columns)
    finally:
        connection.close()

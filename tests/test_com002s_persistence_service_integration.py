from __future__ import annotations

import sqlite3

import backend.app.persistence.db as db_module
import backend.app.persistence.migrations.runner as migration_runner

from backend.app.persistence.repositories.receivable_credit_repository import (
    ReceivableCreditRepository,
)
from backend.app.persistence.repositories.receivable_writeoff_repository import (
    ReceivableWriteOffRepository,
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


def test_persistence_service_registers_credit_and_writeoff_repositories(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)
    try:
        service = PersistenceService()
        assert isinstance(
            service.receivable_credits,
            ReceivableCreditRepository,
        )
        assert isinstance(
            service.receivable_writeoffs,
            ReceivableWriteOffRepository,
        )
        health = service.healthcheck()
        assert health["repositories"]["receivable_credits"] is True
        assert health["repositories"]["receivable_writeoffs"] is True
    finally:
        connection.close()


def test_migrations_022_and_023_are_applied_by_persistence_service(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)
    try:
        PersistenceService()
        credit_table = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table'
              AND name = 'commercial_receivable_credits'
            """
        ).fetchone()
        writeoff_table = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table'
              AND name = 'commercial_receivable_writeoffs'
            """
        ).fetchone()
        assert credit_table is not None
        assert writeoff_table is not None
        migration_022 = connection.execute(
            """
            SELECT version FROM schema_migrations
            WHERE version = ?
            """,
            ("022_receivable_credit",),
        ).fetchone()
        migration_023 = connection.execute(
            """
            SELECT version FROM schema_migrations
            WHERE version = ?
            """,
            ("023_receivable_writeoff",),
        ).fetchone()
        assert migration_022 is not None
        assert migration_023 is not None
    finally:
        connection.close()


def test_foreign_keys_survive_service_migrations(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)
    try:
        PersistenceService()

        for table_name in (
            "commercial_receivable_credits",
            "commercial_receivable_writeoffs",
        ):
            fk_rows = connection.execute(
                f"PRAGMA foreign_key_list('{table_name}')"
            ).fetchall()
            receivable_cols = {
                row["from"]: row
                for row in fk_rows
                if row["table"]
                == "commercial_receivable_recognitions"
            }
            issued_cols = {
                row["from"]: row
                for row in fk_rows
                if row["table"]
                == "commercial_invoice_issued_records"
            }
            assert set(receivable_cols) == {"receivable_id"}
            assert (
                receivable_cols["receivable_id"]["to"]
                == "receivable_id"
            )
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
    finally:
        connection.close()


def test_multiple_rows_per_receivable_supported(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)
    try:
        PersistenceService()
        for table_name in (
            "commercial_receivable_credits",
            "commercial_receivable_writeoffs",
        ):
            index_rows = connection.execute(
                f"PRAGMA index_list('{table_name}')"
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
            assert ("receivable_id",) not in unique_col_sets
            assert ("invoice_id",) not in unique_col_sets
    finally:
        connection.close()


def test_repositories_remain_insert_only(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)
    try:
        service = PersistenceService()
        credit_repo = service.receivable_credits
        writeoff_repo = service.receivable_writeoffs

        assert hasattr(credit_repo, "create_credit")
        assert hasattr(credit_repo, "get_by_credit_id")
        assert hasattr(credit_repo, "get_by_receivable_id")
        assert hasattr(credit_repo, "get_by_invoice_id")
        assert hasattr(credit_repo, "list_all")
        assert not hasattr(credit_repo, "update")
        assert not hasattr(credit_repo, "delete")

        assert hasattr(writeoff_repo, "create_writeoff")
        assert hasattr(writeoff_repo, "get_by_writeoff_id")
        assert hasattr(writeoff_repo, "get_by_receivable_id")
        assert hasattr(writeoff_repo, "get_by_invoice_id")
        assert hasattr(writeoff_repo, "list_all")
        assert not hasattr(writeoff_repo, "update")
        assert not hasattr(writeoff_repo, "delete")
    finally:
        connection.close()


def test_no_prohibited_authority_methods(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)
    try:
        service = PersistenceService()
        credit_repo = service.receivable_credits
        writeoff_repo = service.receivable_writeoffs
        forbidden = (
            "credit_receivable",
            "apply_credit",
            "issue_credit_note",
            "create_credit_note",
            "writeoff_receivable",
            "post_bad_debt",
            "calculate_open_balance",
            "calculate_remaining_balance",
            "issue_refund",
            "initiate_payment",
            "collect_payment",
            "collect_fee",
            "deduct_client_funds",
            "automatic_debit",
            "transfer_funds",
            "withdraw",
            "post_to_ledger",
            "execute_trade",
        )
        for method_name in forbidden:
            assert not hasattr(credit_repo, method_name)
            assert not hasattr(writeoff_repo, method_name)
            assert not hasattr(service, method_name)
    finally:
        connection.close()


def test_credit_table_has_no_prohibited_columns(
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
                PRAGMA table_info('commercial_receivable_credits')
                """
            ).fetchall()
        }
        forbidden = {
            "correction_id",
            "credit_note_id",
            "credit_note_number",
            "credit_note_status",
            "refund_id",
            "refund_amount",
            "refund_status",
            "journal_id",
            "ar_account",
            "revenue_account",
            "posting_status",
            "outstanding_amount",
            "balance_due",
            "remaining_amount",
            "open_amount",
            "payment_status",
            "collection_status",
        }
        assert columns.isdisjoint(forbidden)
        assert {
            "credit_id",
            "receivable_id",
            "invoice_id",
            "currency",
            "credit_amount",
            "credited_at",
            "reason_reference",
            "evidence_refs_json",
            "created_at",
        }.issubset(columns)
    finally:
        connection.close()


def test_writeoff_table_has_no_prohibited_columns(
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
                PRAGMA table_info('commercial_receivable_writeoffs')
                """
            ).fetchall()
        }
        forbidden = {
            "due_record_id",
            "due_date",
            "bad_debt_status",
            "journal_id",
            "ar_account",
            "revenue_account",
            "bad_debt_account",
            "allowance_account",
            "posting_status",
            "refund_id",
            "refund_amount",
            "refund_status",
            "outstanding_amount",
            "balance_due",
            "remaining_amount",
            "open_amount",
            "payment_status",
            "collection_status",
        }
        assert columns.isdisjoint(forbidden)
        assert {
            "writeoff_id",
            "receivable_id",
            "invoice_id",
            "currency",
            "writeoff_amount",
            "written_off_at",
            "reason_reference",
            "evidence_refs_json",
            "created_at",
        }.issubset(columns)
    finally:
        connection.close()

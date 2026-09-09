from __future__ import annotations

import sqlite3

import backend.app.persistence.db as db_module
import backend.app.persistence.migrations.runner as migration_runner

from backend.app.persistence.repositories.receivable_recognition_repository import (
    ReceivableRecognitionRepository,
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


def test_persistence_service_registers_receivable_recognition_repository(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        assert isinstance(
            service.receivable_recognitions,
            ReceivableRecognitionRepository,
        )

        health = service.healthcheck()

        assert (
            health["repositories"]["receivable_recognitions"] is True
        )
    finally:
        connection.close()


def test_migration_017_is_applied_by_persistence_service(
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
              AND name = 'commercial_receivable_recognitions'
            """
        ).fetchone()

        assert table_row is not None
        assert table_row["name"] == (
            "commercial_receivable_recognitions"
        )

        migration_row = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            WHERE version = ?
            """,
            ("017_receivable_recognition",),
        ).fetchone()

        assert migration_row is not None
        assert migration_row["version"] == (
            "017_receivable_recognition"
        )
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
                'commercial_receivable_recognitions'
            )
            """
        ).fetchall()

        issued_cols = {
            row["from"]: row
            for row in fk_rows
            if row["table"] == "commercial_invoice_issued_records"
        }
        profile_cols = {
            row["from"]: row
            for row in fk_rows
            if row["table"] == "commercial_billing_profiles"
        }

        assert set(issued_cols) == {"invoice_id"}
        assert issued_cols["invoice_id"]["to"] == "invoice_id"
        assert issued_cols["invoice_id"]["on_delete"] in (
            "RESTRICT",
            "NO ACTION",
        )

        assert set(profile_cols) == {"billing_profile_id"}
        assert profile_cols["billing_profile_id"]["to"] == (
            "billing_profile_id"
        )
        assert profile_cols["billing_profile_id"]["on_delete"] in (
            "RESTRICT",
            "NO ACTION",
        )
    finally:
        connection.close()


def test_invoice_id_uniqueness_preserved(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        PersistenceService()

        index_rows = connection.execute(
            """
            PRAGMA index_list(
                'commercial_receivable_recognitions'
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

        assert ("invoice_id",) in unique_col_sets or any(
            set(cols) == {"invoice_id"} for cols in unique_col_sets
        )
    finally:
        connection.close()


def test_receivable_recognition_repository_remains_insert_only(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.receivable_recognitions

        assert hasattr(repo, "create_recognition")
        assert hasattr(repo, "get_by_receivable_id")
        assert hasattr(repo, "get_by_invoice_id")
        assert hasattr(repo, "get_by_billing_profile_id")
        assert hasattr(repo, "list_all")

        assert not hasattr(repo, "update_recognition")
        assert not hasattr(repo, "delete_recognition")
        assert not hasattr(repo, "update")
        assert not hasattr(repo, "delete")
    finally:
        connection.close()


def test_no_raw_correction_bypass_recognition_api(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.receivable_recognitions

        assert not hasattr(repo, "recognize_invoice")
        assert not hasattr(service, "recognize_invoice")
        assert not hasattr(repo, "create_from_invoice_id")
        assert not hasattr(service, "create_from_invoice_id")
    finally:
        connection.close()


def test_service_registration_does_not_add_prohibited_authority(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.receivable_recognitions

        forbidden = (
            "recognize_invoice",
            "rerecognize_invoice",
            "adjust_receivable",
            "create_outstanding_balance",
            "mark_due",
            "mark_overdue",
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


def test_receivable_recognition_table_has_no_prohibited_columns(
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
                    'commercial_receivable_recognitions'
                )
                """
            ).fetchall()
        }

        forbidden_columns = {
            "status",
            "receivable_status",
            "due_date",
            "outstanding_amount",
            "amount_paid",
            "amount_credited",
            "amount_written_off",
            "balance_due",
            "journal_id",
            "ar_account",
            "revenue_account",
            "payment_status",
            "collection_status",
            "customer_id",
            "client_id",
            "account_id",
        }

        assert columns.isdisjoint(forbidden_columns)
        assert {
            "receivable_id",
            "invoice_id",
            "billing_profile_id",
            "currency",
            "receivable_amount",
            "recognized_at",
            "evidence_refs_json",
            "created_at",
        }.issubset(columns)
    finally:
        connection.close()

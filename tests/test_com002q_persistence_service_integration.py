from __future__ import annotations

import sqlite3

import backend.app.persistence.db as db_module
import backend.app.persistence.migrations.runner as migration_runner

from backend.app.persistence.repositories.receivable_payment_allocation_repository import (
    ReceivablePaymentAllocationRepository,
)
from backend.app.persistence.repositories.receivable_payment_repository import (
    ReceivablePaymentRepository,
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


def test_persistence_service_registers_payment_repositories(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        assert isinstance(
            service.receivable_payments,
            ReceivablePaymentRepository,
        )
        assert isinstance(
            service.receivable_payment_allocations,
            ReceivablePaymentAllocationRepository,
        )

        health = service.healthcheck()

        assert health["repositories"]["receivable_payments"] is True
        assert (
            health["repositories"]["receivable_payment_allocations"]
            is True
        )
    finally:
        connection.close()


def test_migrations_020_and_021_are_applied_by_persistence_service(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        PersistenceService()

        payment_table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'commercial_receivable_payments'
            """
        ).fetchone()
        allocation_table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'commercial_receivable_payment_allocations'
            """
        ).fetchone()

        assert payment_table is not None
        assert allocation_table is not None

        migration_020 = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            WHERE version = ?
            """,
            ("020_receivable_payment",),
        ).fetchone()
        migration_021 = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            WHERE version = ?
            """,
            ("021_receivable_payment_allocation",),
        ).fetchone()

        assert migration_020 is not None
        assert migration_021 is not None
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
                'commercial_receivable_payment_allocations'
            )
            """
        ).fetchall()

        payment_cols = {
            row["from"]: row
            for row in fk_rows
            if row["table"] == "commercial_receivable_payments"
        }
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

        assert set(payment_cols) == {"payment_id"}
        assert payment_cols["payment_id"]["to"] == "payment_id"
        assert payment_cols["payment_id"]["on_delete"] in (
            "RESTRICT",
            "NO ACTION",
        )

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
    finally:
        connection.close()


def test_allocation_has_no_unique_payment_or_receivable(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        PersistenceService()

        index_rows = connection.execute(
            """
            PRAGMA index_list(
                'commercial_receivable_payment_allocations'
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

        assert ("payment_id",) not in unique_col_sets
        assert ("receivable_id",) not in unique_col_sets
        assert ("invoice_id",) not in unique_col_sets
        assert not any(
            set(cols) == {"payment_id"} for cols in unique_col_sets
        )
        assert not any(
            set(cols) == {"receivable_id"} for cols in unique_col_sets
        )
    finally:
        connection.close()


def test_repositories_remain_insert_only(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        payment_repo = service.receivable_payments
        allocation_repo = service.receivable_payment_allocations

        assert hasattr(payment_repo, "create_payment")
        assert hasattr(payment_repo, "get_by_payment_id")
        assert hasattr(payment_repo, "get_by_external_reference")
        assert hasattr(payment_repo, "list_all")
        assert not hasattr(payment_repo, "update")
        assert not hasattr(payment_repo, "delete")

        assert hasattr(allocation_repo, "create_allocation")
        assert hasattr(allocation_repo, "get_by_allocation_id")
        assert hasattr(allocation_repo, "get_by_payment_id")
        assert hasattr(allocation_repo, "get_by_receivable_id")
        assert hasattr(allocation_repo, "get_by_invoice_id")
        assert hasattr(allocation_repo, "list_all")
        assert not hasattr(allocation_repo, "update")
        assert not hasattr(allocation_repo, "delete")
    finally:
        connection.close()


def test_no_prohibited_authority_methods(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        payment_repo = service.receivable_payments
        allocation_repo = service.receivable_payment_allocations

        forbidden = (
            "record_payment_for_invoice",
            "allocate_payment",
            "apply_payment",
            "cash_apply",
            "calculate_open_balance",
            "calculate_remaining_payment",
            "calculate_amount_paid",
            "validate_aggregate_allocations",
            "initiate_payment",
            "collect_payment",
            "collect_fee",
            "deduct_client_funds",
            "automatic_debit",
            "transfer_funds",
            "withdraw",
            "post_to_ledger",
            "post_cash",
            "create_credit_note",
            "writeoff_receivable",
            "issue_refund",
            "execute_trade",
        )

        for method_name in forbidden:
            assert not hasattr(payment_repo, method_name)
            assert not hasattr(allocation_repo, method_name)
            assert not hasattr(service, method_name)
    finally:
        connection.close()


def test_payment_table_has_no_prohibited_columns(
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
                    'commercial_receivable_payments'
                )
                """
            ).fetchall()
        }

        forbidden_columns = {
            "receivable_id",
            "invoice_id",
            "billing_profile_id",
            "payment_status",
            "settlement_status",
            "payment_method",
            "bank_account",
            "debit_instruction",
            "collection_instruction",
            "transfer_id",
            "journal_id",
            "cash_account",
            "ar_account",
            "revenue_account",
            "outstanding_amount",
            "remaining_payment_amount",
            "amount_paid_total",
            "refund_amount",
            "credit_amount",
            "writeoff_amount",
        }

        assert columns.isdisjoint(forbidden_columns)
        assert {
            "payment_id",
            "currency",
            "payment_amount",
            "observed_at",
            "external_reference",
            "evidence_refs_json",
            "created_at",
        }.issubset(columns)
    finally:
        connection.close()


def test_allocation_table_has_no_prohibited_columns(
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
                    'commercial_receivable_payment_allocations'
                )
                """
            ).fetchall()
        }

        forbidden_columns = {
            "status",
            "allocation_status",
            "outstanding_amount",
            "balance_due",
            "remaining_receivable_amount",
            "remaining_payment_amount",
            "amount_paid_total",
            "open_amount",
            "overpayment_amount",
            "journal_id",
            "cash_account",
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
            "allocation_id",
            "payment_id",
            "receivable_id",
            "invoice_id",
            "currency",
            "allocated_amount",
            "allocated_at",
            "evidence_refs_json",
            "created_at",
        }.issubset(columns)
    finally:
        connection.close()

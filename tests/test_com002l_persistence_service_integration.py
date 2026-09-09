from __future__ import annotations

import sqlite3

import backend.app.persistence.db as db_module
import backend.app.persistence.migrations.runner as migration_runner

from backend.app.persistence.repositories.invoice_issued_repository import (
    InvoiceIssuedRepository,
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


def test_persistence_service_registers_invoice_issued_repository(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        assert isinstance(
            service.invoice_issued_records,
            InvoiceIssuedRepository,
        )

        health = service.healthcheck()

        assert health["repositories"]["invoice_issued_records"] is True
    finally:
        connection.close()


def test_migration_015_is_applied_by_persistence_service(
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
              AND name = 'commercial_invoice_issued_records'
            """
        ).fetchone()

        assert table_row is not None
        assert table_row["name"] == "commercial_invoice_issued_records"

        migration_row = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            WHERE version = ?
            """,
            ("015_invoice_issued",),
        ).fetchone()

        assert migration_row is not None
        assert migration_row["version"] == "015_invoice_issued"
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
                'commercial_invoice_issued_records'
            )
            """
        ).fetchall()

        identity_cols = {
            row["from"]: row
            for row in fk_rows
            if row["table"] == "commercial_invoice_identity_allocations"
        }
        profile_cols = {
            row["from"]: row
            for row in fk_rows
            if row["table"] == "commercial_billing_profiles"
        }
        terms_cols = {
            row["from"]: row
            for row in fk_rows
            if row["table"] == "performance_compensation_terms"
        }

        assert set(identity_cols) == {"invoice_id"}
        assert identity_cols["invoice_id"]["to"] == "invoice_id"
        assert identity_cols["invoice_id"]["on_delete"] in (
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

        assert set(terms_cols) == {"terms_id"}
        assert terms_cols["terms_id"]["to"] == "terms_id"
        assert terms_cols["terms_id"]["on_delete"] in (
            "RESTRICT",
            "NO ACTION",
        )
    finally:
        connection.close()


def test_invoice_issued_repository_remains_insert_only_through_service(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.invoice_issued_records

        assert hasattr(repo, "create_issued_record")
        assert hasattr(repo, "get_by_invoice_id")
        assert hasattr(repo, "get_by_invoice_number")
        assert hasattr(repo, "get_by_terms_id")
        assert hasattr(repo, "get_by_billing_profile_id")
        assert hasattr(repo, "list_all")

        assert not hasattr(repo, "update_issued_record")
        assert not hasattr(repo, "delete_issued_record")
        assert not hasattr(repo, "update")
        assert not hasattr(repo, "delete")
        assert not hasattr(repo, "reissue")
        assert not hasattr(repo, "void")
    finally:
        connection.close()


def test_service_registration_does_not_add_prohibited_authority(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.invoice_issued_records

        forbidden = (
            "void_invoice",
            "supersede_invoice",
            "create_credit_note",
            "create_receivable",
            "post_to_ledger",
            "recognize_revenue",
            "calculate_tax",
            "create_due_balance",
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
            assert not hasattr(service, method_name)
    finally:
        connection.close()


def test_invoice_issued_table_has_no_prohibited_columns(
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
                    'commercial_invoice_issued_records'
                )
                """
            ).fetchall()
        }

        forbidden_columns = {
            "status",
            "invoice_status",
            "due_date",
            "receivable_id",
            "amount_due",
            "balance_due",
            "tax_rate",
            "tax_amount",
            "tax_jurisdiction",
            "journal_id",
            "ar_account",
            "payment_status",
            "collection_status",
            "voided_at",
            "superseded_by",
            "credit_note_id",
        }

        assert columns.isdisjoint(forbidden_columns)
        assert {
            "invoice_id",
            "policy_id",
            "terms_id",
            "billing_profile_id",
            "currency",
            "period_start",
            "period_end",
            "invoice_amount",
            "invoice_number",
            "issued_at",
            "evidence_refs_json",
            "created_at",
        }.issubset(columns)
    finally:
        connection.close()

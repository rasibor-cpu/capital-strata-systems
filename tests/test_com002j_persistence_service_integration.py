from __future__ import annotations

import sqlite3

import backend.app.persistence.db as db_module
import backend.app.persistence.migrations.runner as migration_runner

from backend.app.persistence.repositories.invoice_candidate_repository import (
    InvoiceCandidateRepository,
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


def test_persistence_service_registers_invoice_candidate_repository(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        assert isinstance(
            service.invoice_candidates,
            InvoiceCandidateRepository,
        )

        health = service.healthcheck()

        assert health["repositories"]["invoice_candidates"] is True
    finally:
        connection.close()


def test_migration_013_is_applied_by_persistence_service(
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
              AND name = 'commercial_invoice_candidates'
            """
        ).fetchone()

        assert table_row is not None
        assert table_row["name"] == "commercial_invoice_candidates"

        migration_row = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            WHERE version = ?
            """,
            ("013_invoice_candidate",),
        ).fetchone()

        assert migration_row is not None
        assert migration_row["version"] == "013_invoice_candidate"
    finally:
        connection.close()


def test_invoice_candidate_repository_remains_insert_only_through_service(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.invoice_candidates

        assert hasattr(repo, "create_candidate")
        assert hasattr(repo, "get_by_period")
        assert hasattr(repo, "get_by_policy_id")
        assert hasattr(repo, "get_by_terms_id")
        assert hasattr(repo, "get_by_billing_profile_id")
        assert hasattr(repo, "list_all")

        assert not hasattr(repo, "update_candidate")
        assert not hasattr(repo, "delete_candidate")
        assert not hasattr(repo, "update")
        assert not hasattr(repo, "delete")
    finally:
        connection.close()


def test_service_registration_does_not_add_prohibited_authority(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.invoice_candidates

        forbidden = (
            "create_invoice",
            "assign_invoice_number",
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
            PRAGMA foreign_key_list('commercial_invoice_candidates')
            """
        ).fetchall()

        billable_cols = {
            row["from"]: row
            for row in fk_rows
            if row["table"] == "commercial_billable_obligations"
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

        assert set(billable_cols) == {
            "policy_id",
            "period_start",
            "period_end",
        }
        billable_ids = {
            row["id"]
            for row in fk_rows
            if row["table"] == "commercial_billable_obligations"
        }
        assert len(billable_ids) == 1
        for row in billable_cols.values():
            assert row["on_delete"] in ("RESTRICT", "NO ACTION")

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


def test_invoice_candidate_table_has_no_prohibited_columns(
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
                PRAGMA table_info('commercial_invoice_candidates')
                """
            ).fetchall()
        }

        forbidden_columns = {
            "invoice_candidate_id",
            "invoice_id",
            "invoice_number",
            "invoice_date",
            "issue_date",
            "receivable_id",
            "amount_due",
            "balance_due",
            "due_date",
            "tax_rate",
            "tax_amount",
            "tax_jurisdiction",
            "customer_id",
            "client_id",
            "account_id",
            "payment_status",
            "collection_status",
        }

        assert columns.isdisjoint(forbidden_columns)
        assert {
            "policy_id",
            "terms_id",
            "billing_profile_id",
            "currency",
            "period_start",
            "period_end",
            "candidate_amount",
            "assessed_at",
            "status",
            "evidence_refs_json",
            "created_at",
        }.issubset(columns)
    finally:
        connection.close()

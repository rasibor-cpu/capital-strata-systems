from __future__ import annotations

import sqlite3

import backend.app.persistence.db as db_module
import backend.app.persistence.migrations.runner as migration_runner

from backend.app.persistence.repositories.billing_profile_repository import (
    BillingProfileRepository,
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


def test_persistence_service_registers_billing_profile_repository(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()

        assert isinstance(
            service.billing_profiles,
            BillingProfileRepository,
        )

        health = service.healthcheck()

        assert health["repositories"]["billing_profiles"] is True
    finally:
        connection.close()


def test_migration_012_is_applied_by_persistence_service(
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
              AND name = 'commercial_billing_profiles'
            """
        ).fetchone()

        assert table_row is not None
        assert table_row["name"] == "commercial_billing_profiles"

        migration_row = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            WHERE version = ?
            """,
            ("012_billing_profile",),
        ).fetchone()

        assert migration_row is not None
        assert migration_row["version"] == "012_billing_profile"
    finally:
        connection.close()


def test_billing_profile_repository_remains_insert_only_through_service(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.billing_profiles

        assert hasattr(repo, "create_profile")
        assert hasattr(repo, "get_by_profile_id")
        assert hasattr(repo, "get_by_terms_id")
        assert hasattr(repo, "list_all")

        assert not hasattr(repo, "update_profile")
        assert not hasattr(repo, "delete_profile")
        assert not hasattr(repo, "update")
        assert not hasattr(repo, "delete")
    finally:
        connection.close()


def test_service_registration_does_not_add_invoice_ar_or_payment_authority(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        service = PersistenceService()
        repo = service.billing_profiles

        forbidden = (
            "create_invoice",
            "create_receivable",
            "post_to_ledger",
            "recognize_revenue",
            "calculate_tax",
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


def test_terms_fk_survives_service_migrations(
    monkeypatch,
):
    connection = _isolated_connection()
    _patch_connection(monkeypatch, connection)

    try:
        PersistenceService()

        fk_rows = connection.execute(
            """
            PRAGMA foreign_key_list('commercial_billing_profiles')
            """
        ).fetchall()

        terms_cols = {
            row["from"]: row
            for row in fk_rows
            if row["table"] == "performance_compensation_terms"
        }

        assert set(terms_cols) == {"terms_id"}
        assert terms_cols["terms_id"]["to"] == "terms_id"
        assert terms_cols["terms_id"]["on_delete"] in (
            "RESTRICT",
            "NO ACTION",
        )
    finally:
        connection.close()


def test_billing_profile_table_has_no_prohibited_columns(
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
                PRAGMA table_info('commercial_billing_profiles')
                """
            ).fetchall()
        }

        forbidden_columns = {
            "customer_id",
            "client_id",
            "account_id",
            "broker_account_id",
            "policy_id",
            "invoice_id",
            "invoice_number",
            "invoice_date",
            "amount_due",
            "balance_due",
            "due_date",
            "tax_rate",
            "tax_amount",
            "tax_jurisdiction",
            "billing_address",
        }

        assert columns.isdisjoint(forbidden_columns)
        assert {
            "billing_profile_id",
            "terms_id",
            "party_type",
            "bill_to_name",
            "bill_to_reference",
            "seller_reference",
            "tax_treatment_status",
            "payment_terms_status",
            "effective_from",
            "evidence_refs_json",
            "effective_to",
            "created_at",
        }.issubset(columns)
    finally:
        connection.close()

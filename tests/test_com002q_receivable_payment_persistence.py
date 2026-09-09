from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.repositories.receivable_payment_repository import (
    ReceivablePaymentRepository,
)
from backend.commercialization.receivable_payment import (
    CommercialReceivablePaymentRecord,
    build_receivable_payment,
)


MIGRATION_020 = Path(
    "backend/app/persistence/migrations/sql/"
    "020_receivable_payment.sql"
)

OBSERVED_AT = "2026-04-12T18:00:00+00:00"
OBSERVED_AT_2 = "2026-04-13T19:00:00+00:00"


@pytest.fixture
def db(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        MIGRATION_020.read_text(encoding="utf-8-sig")
    )

    monkeypatch.setattr(
        base_repository,
        "get_connection",
        lambda: connection,
    )

    yield connection

    connection.close()


def _payment(
    *,
    payment_id: str = "PAY-1",
    currency: str = "CAD",
    payment_amount: Decimal = Decimal("100.00"),
    observed_at: str = OBSERVED_AT,
    external_reference: str = "EXT-REF-001",
    evidence_refs: tuple[str, ...] = ("payment:OPS-1",),
) -> CommercialReceivablePaymentRecord:
    return build_receivable_payment(
        payment_id=payment_id,
        currency=currency,
        payment_amount=payment_amount,
        observed_at=observed_at,
        external_reference=external_reference,
        evidence_refs=evidence_refs,
    )


def _seed_payment(
    *,
    payment_id: str = "PAY-1",
    currency: str = "CAD",
    payment_amount: Decimal = Decimal("100.00"),
    observed_at: str = OBSERVED_AT,
    external_reference: str = "EXT-REF-001",
    evidence_refs: tuple[str, ...] = ("payment:OPS-1",),
) -> CommercialReceivablePaymentRecord:
    record = _payment(
        payment_id=payment_id,
        currency=currency,
        payment_amount=payment_amount,
        observed_at=observed_at,
        external_reference=external_reference,
        evidence_refs=evidence_refs,
    )
    ReceivablePaymentRepository().create_payment(record)
    return record


def test_payment_round_trip(db):
    record = _seed_payment()

    row = ReceivablePaymentRepository().get_by_payment_id("PAY-1")

    assert row is not None
    assert row["payment_id"] == "PAY-1"
    assert row["currency"] == "CAD"
    assert row["payment_amount"] == "100.00"
    assert row["observed_at"] == OBSERVED_AT
    assert row["external_reference"] == "EXT-REF-001"
    assert isinstance(record, CommercialReceivablePaymentRecord)


def test_exact_decimal_serialization(db):
    _seed_payment(payment_amount=Decimal("3.50"))

    row = ReceivablePaymentRepository().get_by_payment_id("PAY-1")

    assert row is not None
    assert row["payment_amount"] == "3.50"
    assert Decimal(row["payment_amount"]) == Decimal("3.50")


def test_zero_amount_persists(db):
    _seed_payment(payment_amount=Decimal("0"))

    row = ReceivablePaymentRepository().get_by_payment_id("PAY-1")

    assert row is not None
    assert row["payment_amount"] == "0"
    assert Decimal(row["payment_amount"]) == Decimal("0")


def test_evidence_round_trip(db):
    _seed_payment(
        evidence_refs=("payment:OPS-1", "review:OPS-2"),
    )

    row = ReceivablePaymentRepository().get_by_payment_id("PAY-1")

    assert row is not None
    assert row["evidence_refs_json"] == (
        '["payment:OPS-1","review:OPS-2"]'
    )
    assert tuple(json.loads(row["evidence_refs_json"])) == (
        "payment:OPS-1",
        "review:OPS-2",
    )


def test_timestamp_round_trip(db):
    _seed_payment(observed_at=OBSERVED_AT)

    row = ReceivablePaymentRepository().get_by_payment_id("PAY-1")

    assert row is not None
    assert row["observed_at"] == OBSERVED_AT


def test_external_reference_round_trip(db):
    _seed_payment(external_reference="EXT-REF-OPAQUE-9")

    row = ReceivablePaymentRepository().get_by_payment_id("PAY-1")
    by_ref = ReceivablePaymentRepository().get_by_external_reference(
        "EXT-REF-OPAQUE-9"
    )

    assert row is not None
    assert row["external_reference"] == "EXT-REF-OPAQUE-9"
    assert [r["payment_id"] for r in by_ref] == ["PAY-1"]


def test_duplicate_payment_id_rejected(db):
    _seed_payment(payment_id="PAY-1")

    with pytest.raises(sqlite3.IntegrityError):
        ReceivablePaymentRepository().create_payment(
            _payment(payment_id="PAY-1", external_reference="EXT-2")
        )


def test_lowercase_currency_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_payments (
                payment_id,
                currency,
                payment_amount,
                observed_at,
                external_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "PAY-1",
                "cad",
                "100.00",
                OBSERVED_AT,
                "EXT-REF-001",
                '["payment:OPS-1"]',
            ),
        )


def test_empty_evidence_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_payments (
                payment_id,
                currency,
                payment_amount,
                observed_at,
                external_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "PAY-1",
                "CAD",
                "100.00",
                OBSERVED_AT,
                "EXT-REF-001",
                "[]",
            ),
        )


def test_blank_external_reference_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_payments (
                payment_id,
                currency,
                payment_amount,
                observed_at,
                external_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "PAY-1",
                "CAD",
                "100.00",
                OBSERVED_AT,
                " ",
                '["payment:OPS-1"]',
            ),
        )


def test_deterministic_reads(db):
    _seed_payment(
        payment_id="PAY-B",
        observed_at=OBSERVED_AT_2,
        external_reference="EXT-SHARED",
    )
    _seed_payment(
        payment_id="PAY-A",
        observed_at=OBSERVED_AT,
        external_reference="EXT-SHARED",
    )

    listed = ReceivablePaymentRepository().list_all()
    by_ref = ReceivablePaymentRepository().get_by_external_reference(
        "EXT-SHARED"
    )

    assert [row["payment_id"] for row in listed] == [
        "PAY-A",
        "PAY-B",
    ]
    assert [row["payment_id"] for row in by_ref] == [
        "PAY-A",
        "PAY-B",
    ]


def test_no_update_delete_api():
    assert not hasattr(ReceivablePaymentRepository, "update_payment")
    assert not hasattr(ReceivablePaymentRepository, "delete_payment")
    assert not hasattr(ReceivablePaymentRepository, "update")
    assert not hasattr(ReceivablePaymentRepository, "delete")
    assert not hasattr(ReceivablePaymentRepository, "replace")


def _table_columns(db) -> set[str]:
    return {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info('commercial_receivable_payments')"
        ).fetchall()
    }


def test_no_receivable_id_column(db):
    assert "receivable_id" not in _table_columns(db)


def test_no_invoice_id_column(db):
    columns = _table_columns(db)
    assert "invoice_id" not in columns
    assert "billing_profile_id" not in columns


def test_no_status_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "payment_status",
        "settlement_status",
        "status",
        "cleared",
        "settled",
        "applied",
        "unapplied",
        "partial",
        "paid",
    }
    assert columns.isdisjoint(forbidden)


def test_no_gl_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "journal_id",
        "cash_account",
        "ar_account",
        "revenue_account",
        "posting_status",
        "cash_posted",
    }
    assert columns.isdisjoint(forbidden)


def test_no_execution_bank_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "payment_method",
        "bank_account",
        "debit_instruction",
        "collection_instruction",
        "transfer_id",
        "withdrawal_id",
        "execution_status",
        "outstanding_amount",
        "remaining_payment_amount",
        "amount_paid_total",
        "refund_amount",
        "credit_amount",
        "writeoff_amount",
    }
    assert columns.isdisjoint(forbidden)


def test_no_raw_payment_bypass_api():
    assert not hasattr(
        ReceivablePaymentRepository,
        "record_payment",
    )
    assert not hasattr(
        ReceivablePaymentRepository,
        "record_payment_for_invoice",
    )
    assert not hasattr(
        ReceivablePaymentRepository,
        "apply_payment",
    )
    assert not hasattr(
        ReceivablePaymentRepository,
        "cash_apply",
    )

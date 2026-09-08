from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.repositories.attributable_performance_repository import (
    AttributablePerformanceRepository,
)
from backend.commercialization.performance_attribution import (
    AttributablePerformance,
)


MIGRATION = Path(
    "backend/app/persistence/migrations/sql/"
    "006_attributable_performance.sql"
)


@pytest.fixture
def db(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    connection.executescript(
        """
        CREATE TABLE trades (
            trade_id TEXT PRIMARY KEY
        );

        CREATE TABLE trade_provenance (
            trade_id TEXT PRIMARY KEY,

            FOREIGN KEY (trade_id)
                REFERENCES trades(trade_id)
                ON DELETE RESTRICT
        );
        """
    )

    connection.executescript(
        MIGRATION.read_text(encoding="utf-8-sig")
    )

    monkeypatch.setattr(
        base_repository,
        "get_connection",
        lambda: connection,
    )

    yield connection

    connection.close()


def _create_trade(
    connection: sqlite3.Connection,
    trade_id: str,
) -> None:
    connection.execute(
        "INSERT INTO trades (trade_id) VALUES (?)",
        (trade_id,),
    )
    connection.execute(
        "INSERT INTO trade_provenance (trade_id) VALUES (?)",
        (trade_id,),
    )


def _performance(
    trade_id: str = "TRADE-001",
    pnl: Decimal = Decimal("125.50"),
) -> AttributablePerformance:
    return AttributablePerformance(
        trade_id=trade_id,
        advice_id="ADVICE-001",
        realized_pnl=pnl,
        currency="CAD",
        verification_timestamp="2026-09-08T18:10:00Z",
        provenance_evidence_refs=(
            "trade-card:ADVICE-001",
        ),
        economics_evidence_refs=(
            "canonical-pnl:TRADE-001",
        ),
    )


def test_insert_and_read_attributable_performance(db):
    _create_trade(db, "TRADE-001")

    repo = AttributablePerformanceRepository()
    repo.create_attributable_performance(
        _performance()
    )

    row = repo.get_by_trade_id("TRADE-001")

    assert row is not None
    assert row["trade_id"] == "TRADE-001"
    assert row["advice_id"] == "ADVICE-001"
    assert row["realized_pnl"] == "125.50"
    assert row["currency"] == "CAD"
    assert (
        row["verification_timestamp"]
        == "2026-09-08T18:10:00Z"
    )


def test_decimal_serialization_is_exact(db):
    _create_trade(db, "TRADE-001")

    repo = AttributablePerformanceRepository()
    repo.create_attributable_performance(
        _performance(
            pnl=Decimal("-42.7500"),
        )
    )

    row = repo.get_by_trade_id("TRADE-001")

    assert row is not None
    assert row["realized_pnl"] == "-42.7500"
    assert Decimal(row["realized_pnl"]) == Decimal("-42.7500")


def test_zero_realized_pnl_persists(db):
    _create_trade(db, "TRADE-001")

    repo = AttributablePerformanceRepository()
    repo.create_attributable_performance(
        _performance(
            pnl=Decimal("0"),
        )
    )

    row = repo.get_by_trade_id("TRADE-001")

    assert row is not None
    assert row["realized_pnl"] == "0"


def test_evidence_references_round_trip(db):
    _create_trade(db, "TRADE-001")

    repo = AttributablePerformanceRepository()
    repo.create_attributable_performance(
        _performance()
    )

    row = repo.get_by_trade_id("TRADE-001")

    assert row is not None
    assert json.loads(
        row["provenance_evidence_refs_json"]
    ) == ["trade-card:ADVICE-001"]

    assert json.loads(
        row["economics_evidence_refs_json"]
    ) == ["canonical-pnl:TRADE-001"]


def test_duplicate_trade_attribution_is_rejected(db):
    _create_trade(db, "TRADE-001")

    repo = AttributablePerformanceRepository()
    repo.create_attributable_performance(
        _performance()
    )

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_attributable_performance(
            replace(
                _performance(),
                realized_pnl=Decimal("999"),
            )
        )


def test_missing_trade_foreign_key_is_rejected(db):
    repo = AttributablePerformanceRepository()

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_attributable_performance(
            _performance(
                trade_id="MISSING-TRADE",
            )
        )


def test_existing_trade_without_provenance_is_rejected(db):
    db.execute(
        "INSERT INTO trades (trade_id) VALUES (?)",
        ("TRADE-NO-PROVENANCE",),
    )

    repo = AttributablePerformanceRepository()

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_attributable_performance(
            _performance(
                trade_id="TRADE-NO-PROVENANCE",
            )
        )


def test_database_rejects_lowercase_currency(db):
    _create_trade(db, "TRADE-001")

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO attributable_performance (
                trade_id,
                advice_id,
                realized_pnl,
                currency,
                verification_timestamp,
                provenance_evidence_refs_json,
                economics_evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TRADE-001",
                "ADVICE-001",
                "1",
                "cad",
                "2026-09-08T18:10:00Z",
                '["trade-card:ADVICE-001"]',
                '["canonical-pnl:TRADE-001"]',
            ),
        )


def test_database_rejects_empty_evidence(db):
    _create_trade(db, "TRADE-001")

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO attributable_performance (
                trade_id,
                advice_id,
                realized_pnl,
                currency,
                verification_timestamp,
                provenance_evidence_refs_json,
                economics_evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TRADE-001",
                "ADVICE-001",
                "1",
                "CAD",
                "2026-09-08T18:10:00Z",
                "[]",
                "[]",
            ),
        )


def test_get_by_advice_id_is_deterministic(db):
    _create_trade(db, "TRADE-002")
    _create_trade(db, "TRADE-001")

    repo = AttributablePerformanceRepository()

    repo.create_attributable_performance(
        _performance(
            trade_id="TRADE-002",
            pnl=Decimal("-1"),
        )
    )
    repo.create_attributable_performance(
        _performance(
            trade_id="TRADE-001",
            pnl=Decimal("2"),
        )
    )

    rows = repo.get_by_advice_id("ADVICE-001")

    assert [row["trade_id"] for row in rows] == [
        "TRADE-001",
        "TRADE-002",
    ]


def test_repository_has_no_mutation_api():
    assert not hasattr(
        AttributablePerformanceRepository,
        "update_attributable_performance",
    )
    assert not hasattr(
        AttributablePerformanceRepository,
        "delete_attributable_performance",
    )
    assert not hasattr(
        AttributablePerformanceRepository,
        "update",
    )
    assert not hasattr(
        AttributablePerformanceRepository,
        "delete",
    )


def test_persistence_contract_contains_no_fee_or_execution_authority():
    record = _performance()

    assert record.real_fee_collection_allowed is False
    assert record.client_funds_deduction_allowed is False
    assert record.execution_authority is False

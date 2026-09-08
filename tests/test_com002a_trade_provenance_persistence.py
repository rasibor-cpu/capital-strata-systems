from __future__ import annotations

import json
import sqlite3

import pytest

from backend.app.persistence.db import close_connection, get_connection
from backend.app.persistence.migrations.runner import run_migrations
from backend.app.persistence.repositories.trade_provenance_repository import (
    TradeProvenanceRepository,
)
from backend.commercialization.trade_provenance import (
    AttributionClass,
    MandateCompliance,
    TradeProvenance,
)


@pytest.fixture()
def provenance_db(tmp_path, monkeypatch):
    from backend.app.persistence import db

    close_connection()

    test_db = tmp_path / "com002a_provenance.db"

    monkeypatch.setattr(
        db,
        "DEFAULT_DB_PATH",
        test_db,
    )

    run_migrations()

    conn = get_connection()

    conn.execute(
        """
        INSERT INTO sessions (
            session_id,
            started_at,
            status,
            mode,
            broker_name,
            broker_mode
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "SESSION-COM002A",
            "2026-09-08T18:00:00Z",
            "running",
            "paper",
            "internal",
            "paper",
        ),
    )

    def create_trade(trade_id: str, symbol: str = "XYZ") -> None:
        conn.execute(
            """
            INSERT INTO trades (
                trade_id,
                session_id,
                broker_name,
                broker_mode,
                symbol,
                direction,
                status,
                order_type,
                quantity,
                filled_quantity,
                entry_price,
                opened_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade_id,
                "SESSION-COM002A",
                "internal",
                "paper",
                symbol,
                "long",
                "open",
                "market",
                "1",
                "1",
                "10",
                "2026-09-08T18:01:00Z",
            ),
        )

    yield conn, create_trade

    close_connection()


def accepted_provenance(
    trade_id: str,
    advice_id: str = "ADVICE-001",
) -> TradeProvenance:
    return TradeProvenance(
        trade_id=trade_id,
        advice_id=advice_id,
        attribution_class=AttributionClass.CSS_ADVISED_ACCEPTED,
        mandate_compliance=MandateCompliance.COMPLIANT,
        recommendation_timestamp="2026-09-08T18:00:00Z",
        acceptance_timestamp="2026-09-08T18:01:00Z",
        evidence_refs=(
            "trade-card:ADVICE-001",
            "acceptance:CLIENT-001",
        ),
    )


def test_persists_and_reads_provenance(provenance_db):
    _, create_trade = provenance_db
    create_trade("TRADE-001")

    repo = TradeProvenanceRepository()
    repo.create_provenance(
        accepted_provenance("TRADE-001")
    )

    row = repo.get_by_trade_id("TRADE-001")

    assert row is not None
    assert row["trade_id"] == "TRADE-001"
    assert row["advice_id"] == "ADVICE-001"
    assert row["attribution_class"] == "CSS_ADVISED_ACCEPTED"
    assert row["mandate_compliance"] == "COMPLIANT"

    assert json.loads(row["evidence_refs_json"]) == [
        "trade-card:ADVICE-001",
        "acceptance:CLIENT-001",
    ]


def test_duplicate_trade_provenance_fails_closed(provenance_db):
    _, create_trade = provenance_db
    create_trade("TRADE-002")

    repo = TradeProvenanceRepository()

    repo.create_provenance(
        accepted_provenance("TRADE-002")
    )

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_provenance(
            TradeProvenance(
                trade_id="TRADE-002",
                attribution_class=AttributionClass.CUSTOMER_DIRECTED,
                mandate_compliance=MandateCompliance.OUTSIDE_CSS,
                evidence_refs=("customer-order:TRADE-002",),
            )
        )

    row = repo.get_by_trade_id("TRADE-002")

    assert row is not None
    assert row["advice_id"] == "ADVICE-001"
    assert row["attribution_class"] == "CSS_ADVISED_ACCEPTED"


def test_provenance_requires_existing_trade(provenance_db):
    repo = TradeProvenanceRepository()

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_provenance(
            accepted_provenance("TRADE-DOES-NOT-EXIST")
        )


def test_one_advice_can_link_to_multiple_trades(provenance_db):
    _, create_trade = provenance_db

    create_trade("TRADE-003")
    create_trade("TRADE-004", symbol="ABC")

    repo = TradeProvenanceRepository()

    repo.create_provenance(
        accepted_provenance(
            "TRADE-003",
            advice_id="ADVICE-MULTI",
        )
    )

    repo.create_provenance(
        accepted_provenance(
            "TRADE-004",
            advice_id="ADVICE-MULTI",
        )
    )

    rows = repo.get_by_advice_id("ADVICE-MULTI")

    assert [row["trade_id"] for row in rows] == [
        "TRADE-003",
        "TRADE-004",
    ]


def test_repository_exposes_no_mutation_api():
    assert not hasattr(
        TradeProvenanceRepository,
        "update_provenance",
    )

    assert not hasattr(
        TradeProvenanceRepository,
        "delete_provenance",
    )


def test_database_rejects_invalid_accepted_attribution(provenance_db):
    conn, create_trade = provenance_db
    create_trade("TRADE-005")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO trade_provenance (
                trade_id,
                advice_id,
                attribution_class,
                mandate_compliance,
                acceptance_timestamp,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "TRADE-005",
                "ADVICE-005",
                "CSS_ADVISED_ACCEPTED",
                "MODIFIED",
                "2026-09-08T18:01:00Z",
                '["evidence"]',
            ),
        )
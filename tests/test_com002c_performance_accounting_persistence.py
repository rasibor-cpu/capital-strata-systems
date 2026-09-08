from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.repositories.performance_accounting_transition_repository import (
    PerformanceAccountingTransitionRepository,
)
from backend.commercialization.performance_accounting import (
    PerformanceAccountState,
    apply_attributable_performance,
)
from backend.commercialization.performance_attribution import (
    AttributablePerformance,
)


MIGRATION = Path(
    "backend/app/persistence/migrations/sql/"
    "007_performance_accounting_transitions.sql"
)


@pytest.fixture
def db(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    connection.executescript(
        """
        CREATE TABLE attributable_performance (
            trade_id TEXT PRIMARY KEY
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


def _create_attributable_performance(
    connection: sqlite3.Connection,
    trade_id: str,
) -> None:
    connection.execute(
        """
        INSERT INTO attributable_performance (trade_id)
        VALUES (?)
        """,
        (trade_id,),
    )


def _performance(
    pnl: Decimal,
    trade_id: str = "TRADE-001",
) -> AttributablePerformance:
    return AttributablePerformance(
        trade_id=trade_id,
        advice_id="ADVICE-001",
        realized_pnl=pnl,
        currency="CAD",
        verification_timestamp="2026-09-08T19:00:00Z",
        provenance_evidence_refs=(
            "trade-card:ADVICE-001",
        ),
        economics_evidence_refs=(
            "canonical-pnl:TRADE-001",
        ),
    )


def _transition(
    trade_id: str = "TRADE-001",
    pnl: Decimal = Decimal("15"),
):
    previous = PerformanceAccountState(
        currency="CAD",
        cumulative_attributable_pnl=Decimal("90"),
        high_water_mark=Decimal("100"),
        loss_carryforward=Decimal("10"),
    )

    return apply_attributable_performance(
        previous,
        _performance(
            pnl=pnl,
            trade_id=trade_id,
        ),
    )


def test_insert_and_read_transition(db):
    _create_attributable_performance(
        db,
        "TRADE-001",
    )

    repo = PerformanceAccountingTransitionRepository()
    repo.create_transition(
        _transition()
    )

    row = repo.get_by_trade_id("TRADE-001")

    assert row is not None
    assert row["trade_id"] == "TRADE-001"
    assert row["currency"] == "CAD"

    assert (
        row["previous_cumulative_attributable_pnl"]
        == "90"
    )
    assert row["previous_high_water_mark"] == "100"
    assert row["previous_loss_carryforward"] == "10"

    assert row["attributable_realized_pnl"] == "15"
    assert row["recovered_loss"] == "10"
    assert row["new_economic_gain"] == "5"

    assert (
        row["new_cumulative_attributable_pnl"]
        == "105"
    )
    assert row["new_high_water_mark"] == "105"
    assert row["new_loss_carryforward"] == "0"


def test_decimal_serialization_is_exact(db):
    _create_attributable_performance(
        db,
        "TRADE-001",
    )

    previous = PerformanceAccountState(
        currency="CAD",
        cumulative_attributable_pnl=Decimal("100.0000"),
        high_water_mark=Decimal("100.0000"),
        loss_carryforward=Decimal("0.0000"),
    )

    transition = apply_attributable_performance(
        previous,
        _performance(
            Decimal("-42.7500"),
        ),
    )

    repo = PerformanceAccountingTransitionRepository()
    repo.create_transition(transition)

    row = repo.get_by_trade_id("TRADE-001")

    assert row is not None
    assert row["attributable_realized_pnl"] == "-42.7500"
    assert Decimal(
        row["attributable_realized_pnl"]
    ) == Decimal("-42.7500")


def test_duplicate_transition_is_rejected(db):
    _create_attributable_performance(
        db,
        "TRADE-001",
    )

    repo = PerformanceAccountingTransitionRepository()

    repo.create_transition(
        _transition()
    )

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_transition(
            _transition(
                pnl=Decimal("20"),
            )
        )


def test_missing_attributable_performance_is_rejected(db):
    repo = PerformanceAccountingTransitionRepository()

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_transition(
            _transition(
                trade_id="MISSING-TRADE",
            )
        )


def test_loss_transition_persists_recovery_state(db):
    _create_attributable_performance(
        db,
        "TRADE-001",
    )

    previous = PerformanceAccountState(
        currency="CAD",
        cumulative_attributable_pnl=Decimal("100"),
        high_water_mark=Decimal("100"),
        loss_carryforward=Decimal("0"),
    )

    transition = apply_attributable_performance(
        previous,
        _performance(
            Decimal("-30"),
        ),
    )

    repo = PerformanceAccountingTransitionRepository()
    repo.create_transition(transition)

    row = repo.get_by_trade_id("TRADE-001")

    assert row is not None
    assert row["new_cumulative_attributable_pnl"] == "70"
    assert row["new_high_water_mark"] == "100"
    assert row["new_loss_carryforward"] == "30"
    assert row["recovered_loss"] == "0"
    assert row["new_economic_gain"] == "0"


def test_list_all_is_deterministic(db):
    _create_attributable_performance(
        db,
        "TRADE-002",
    )
    _create_attributable_performance(
        db,
        "TRADE-001",
    )

    repo = PerformanceAccountingTransitionRepository()

    repo.create_transition(
        _transition(
            trade_id="TRADE-002",
            pnl=Decimal("5"),
        )
    )

    repo.create_transition(
        _transition(
            trade_id="TRADE-001",
            pnl=Decimal("5"),
        )
    )

    rows = repo.list_all()

    assert [row["trade_id"] for row in rows] == [
        "TRADE-001",
        "TRADE-002",
    ]


def test_repository_has_no_mutation_api():
    assert not hasattr(
        PerformanceAccountingTransitionRepository,
        "update_transition",
    )
    assert not hasattr(
        PerformanceAccountingTransitionRepository,
        "delete_transition",
    )
    assert not hasattr(
        PerformanceAccountingTransitionRepository,
        "update",
    )
    assert not hasattr(
        PerformanceAccountingTransitionRepository,
        "delete",
    )


def test_transition_persistence_does_not_authorize_fee_or_execution():
    transition = _transition()

    assert transition.real_fee_collection_allowed is False
    assert transition.client_funds_deduction_allowed is False
    assert transition.execution_authority is False

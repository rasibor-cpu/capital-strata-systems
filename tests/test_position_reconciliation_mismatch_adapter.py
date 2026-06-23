from backend.reconciliation.position_reconciliation import (
    PositionReconciliationReport,
)
from backend.reconciliation.position_reconciliation_mismatch_adapter import (
    build_mismatches_from_position_report,
)


def test_builds_position_manager_mismatch():
    report = PositionReconciliationReport(
        broker_count=1,
        position_manager_count=0,
        ledger_count=1,
        broker_symbols=["EURUSD"],
        position_manager_symbols=[],
        ledger_symbols=["EURUSD"],
        missing_from_position_manager=["EURUSD"],
        missing_from_ledger=[],
        reconciled=False,
    )

    mismatches = build_mismatches_from_position_report(report)

    assert len(mismatches) == 1
    assert mismatches[0].symbol == "EURUSD"
    assert mismatches[0].source_a == "broker"
    assert mismatches[0].source_b == "position_manager"


def test_builds_ledger_mismatch():
    report = PositionReconciliationReport(
        broker_count=1,
        position_manager_count=1,
        ledger_count=0,
        broker_symbols=["GBPUSD"],
        position_manager_symbols=["GBPUSD"],
        ledger_symbols=[],
        missing_from_position_manager=[],
        missing_from_ledger=["GBPUSD"],
        reconciled=False,
    )

    mismatches = build_mismatches_from_position_report(report)

    assert len(mismatches) == 1
    assert mismatches[0].symbol == "GBPUSD"
    assert mismatches[0].source_a == "broker"
    assert mismatches[0].source_b == "ledger"


def test_returns_empty_when_reconciled():
    report = PositionReconciliationReport(
        broker_count=1,
        position_manager_count=1,
        ledger_count=1,
        broker_symbols=["BTCUSD"],
        position_manager_symbols=["BTCUSD"],
        ledger_symbols=["BTCUSD"],
        missing_from_position_manager=[],
        missing_from_ledger=[],
        reconciled=True,
    )

    mismatches = build_mismatches_from_position_report(report)

    assert mismatches == []
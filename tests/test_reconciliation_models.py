from backend.reconciliation.reconciliation_models import (
    ReconciliationMismatch,
    ReconciliationSummary,
)


def test_reconciliation_mismatch_model():
    mismatch = ReconciliationMismatch(
        symbol="BTCUSD",
        source_a="broker",
        source_b="ledger",
        details="Broker has position but ledger is missing it.",
        severity="WARNING",
    )

    assert mismatch.symbol == "BTCUSD"
    assert mismatch.source_a == "broker"
    assert mismatch.source_b == "ledger"
    assert mismatch.severity == "WARNING"


def test_reconciliation_summary_model():
    mismatch = ReconciliationMismatch(
        symbol="ETHUSD",
        source_a="broker",
        source_b="position_manager",
        details="Broker has position but PositionManager is missing it.",
        severity="CRITICAL",
    )

    summary = ReconciliationSummary(
        reconciled=False,
        broker_symbols=2,
        position_manager_symbols=1,
        ledger_symbols=2,
        mismatch_count=1,
        mismatches=[mismatch],
    )

    assert summary.reconciled is False
    assert summary.mismatch_count == 1
    assert summary.mismatches[0].symbol == "ETHUSD"
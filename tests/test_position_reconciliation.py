from backend.reconciliation.position_reconciliation import (
    PositionReconciliationService,
)


def test_reconciliation_success():
    service = PositionReconciliationService()

    report = service.reconcile(
        broker_positions=[
            {"symbol": "BTCUSD"},
            {"symbol": "ETHUSD"},
        ],
        position_manager_positions=[
            {"symbol": "BTCUSD"},
            {"symbol": "ETHUSD"},
        ],
        ledger_positions=[
            {"symbol": "BTCUSD"},
            {"symbol": "ETHUSD"},
        ],
    )

    assert report.reconciled is True
    assert report.missing_from_position_manager == []
    assert report.missing_from_ledger == []


def test_reconciliation_detects_position_manager_gap():
    service = PositionReconciliationService()

    report = service.reconcile(
        broker_positions=[
            {"symbol": "BTCUSD"},
            {"symbol": "ETHUSD"},
        ],
        position_manager_positions=[
            {"symbol": "BTCUSD"},
        ],
        ledger_positions=[
            {"symbol": "BTCUSD"},
            {"symbol": "ETHUSD"},
        ],
    )

    assert report.reconciled is False
    assert report.missing_from_position_manager == ["ETHUSD"]


def test_reconciliation_detects_ledger_gap():
    service = PositionReconciliationService()

    report = service.reconcile(
        broker_positions=[
            {"symbol": "BTCUSD"},
            {"symbol": "ETHUSD"},
        ],
        position_manager_positions=[
            {"symbol": "BTCUSD"},
            {"symbol": "ETHUSD"},
        ],
        ledger_positions=[
            {"symbol": "BTCUSD"},
        ],
    )

    assert report.reconciled is False
    assert report.missing_from_ledger == ["ETHUSD"]


def test_symbol_normalization():
    service = PositionReconciliationService()

    report = service.reconcile(
        broker_positions=[
            {"symbol": "btcusd"},
        ],
        position_manager_positions=[
            {"symbol": "BTCUSD"},
        ],
        ledger_positions=[
            {"symbol": "BtcUsd"},
        ],
    )

    assert report.reconciled is True
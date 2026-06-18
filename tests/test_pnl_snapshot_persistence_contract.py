from __future__ import annotations

import importlib
from decimal import Decimal

import pytest

from backend.app.persistence import db


@pytest.fixture()
def isolated_runtime_db(tmp_path, monkeypatch):
    db.close_connection()
    db_path = tmp_path / "fresh_css_runtime.db"
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", db_path)
    yield db_path
    db.close_connection()


def _create_session(mode="paper", broker_name="internal", broker_mode="paper"):
    from backend.app.persistence.services.session_runtime_service import (
        SessionRuntimeService,
    )

    return SessionRuntimeService().create_runtime_session(
        mode=mode,
        broker_name=broker_name,
        broker_mode=broker_mode,
    )


def test_pnl_runtime_service_maps_to_repository_contract(isolated_runtime_db):
    from backend.app.persistence.services.pnl_runtime_service import (
        PnlRuntimeService,
    )

    service = PnlRuntimeService()
    session_id = _create_session()

    service.create_snapshot(
        session_id=session_id,
        account_id="acct-123",
        broker_name="internal",
        broker_mode="paper",
        equity=Decimal("10000.00"),
        cash_balance=Decimal("9000.00"),
        buying_power=Decimal("12000.00"),
        available_cash=Decimal("8750.00"),
        unrealized_pnl=Decimal("25.50"),
        realized_pnl=Decimal("15.25"),
        open_positions=3,
        winning_positions=2,
        losing_positions=1,
        snapshot_reason="contract_test",
        payload_json='{"ignored": true}',
    )

    snapshot = service.get_latest_snapshot(session_id)

    assert snapshot is not None
    assert snapshot["account_id"] == "acct-123"
    assert snapshot["broker_name"] == "internal"
    assert snapshot["broker_mode"] == "paper"
    assert snapshot["realized_pnl"] == "15.25"
    assert snapshot["unrealized_pnl"] == "25.50"
    assert snapshot["equity"] == "10000.00"
    assert snapshot["available_cash"] == "8750.00"
    assert snapshot["open_positions"] == 3
    assert snapshot["winning_positions"] == 2
    assert snapshot["losing_positions"] == 1
    assert snapshot["snapshot_reason"] == "contract_test"


def test_pnl_runtime_service_uses_safe_defaults_for_missing_repository_fields(
    isolated_runtime_db,
):
    from backend.app.persistence.services.pnl_runtime_service import (
        PnlRuntimeService,
    )

    service = PnlRuntimeService()
    session_id = _create_session()

    service.create_snapshot(
        session_id=session_id,
        broker_name="internal",
        broker_mode="paper",
        equity=Decimal("50000"),
        cash_balance=Decimal("50000"),
        buying_power=Decimal("50000"),
        unrealized_pnl=Decimal("0"),
        realized_pnl=Decimal("0"),
        open_positions=0,
    )

    snapshot = service.get_latest_snapshot(session_id)

    assert snapshot is not None
    assert snapshot["account_id"] == "INTERNAL-PAPER"
    assert snapshot["available_cash"] == "50000"
    assert snapshot["winning_positions"] == 0
    assert snapshot["losing_positions"] == 0
    assert snapshot["snapshot_reason"] is None


def test_pnl_runtime_service_calls_repository_with_supported_arguments(
    monkeypatch,
):
    from backend.app.persistence.services.pnl_runtime_service import (
        PnlRuntimeService,
    )

    captured_kwargs = {}

    class FakePnlSnapshotRepository:
        def create_snapshot(self, **kwargs):
            captured_kwargs.update(kwargs)

    class FakePersistenceService:
        def __init__(self):
            self.pnl_snapshots = FakePnlSnapshotRepository()

    import backend.app.persistence.services.pnl_runtime_service as module

    monkeypatch.setattr(module, "PersistenceService", FakePersistenceService)

    service = PnlRuntimeService()
    service.create_snapshot(
        session_id="session-argument-check",
        broker_name="internal",
        broker_mode="paper",
        equity=Decimal("1"),
        cash_balance=Decimal("2"),
        buying_power=Decimal("3"),
        unrealized_pnl=Decimal("4"),
        realized_pnl=Decimal("5"),
        open_positions=6,
        payload_json="ignored",
    )

    assert set(captured_kwargs) == {
        "session_id",
        "account_id",
        "broker_name",
        "broker_mode",
        "realized_pnl",
        "unrealized_pnl",
        "equity",
        "available_cash",
        "open_positions",
        "winning_positions",
        "losing_positions",
        "snapshot_reason",
    }
    assert "snapshot_time" not in captured_kwargs
    assert "cash_balance" not in captured_kwargs
    assert "buying_power" not in captured_kwargs
    assert "payload_json" not in captured_kwargs


def test_trade_decision_orchestrator_persists_pnl_snapshot(
    isolated_runtime_db,
    monkeypatch,
):
    monkeypatch.setenv("CSS_TOTAL_CAPITAL", "50000")

    import backend.intelligence.trade_decision_orchestrator as tdo

    importlib.reload(tdo)
    orchestrator = tdo.TradeDecisionOrchestrator()

    decision = orchestrator.evaluate_trade(
        {
            "symbol": "BTC-USD",
            "asset_class": "crypto",
            "expected_value": 1,
            "cost": 0,
            "probability": 1,
        }
    )

    snapshot = (
        orchestrator.pnl_runtime_service
        .get_latest_snapshot(orchestrator.session_id)
    )

    assert decision["runtime"]["pnl_tracking"] is True
    assert snapshot is not None
    assert snapshot["session_id"] == orchestrator.session_id
    assert snapshot["account_id"] == "INTERNAL-PAPER"
    assert snapshot["broker_name"] == "internal"
    assert snapshot["broker_mode"] == "paper"
    assert snapshot["equity"] == "50000.0"
    assert snapshot["available_cash"] == "50000.0"

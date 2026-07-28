from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from backend.app.persistence import db
from backend.analytics.trade_outcome_repository import TradeOutcomeRepository
from backend.execution.canonical_trade_lifecycle import CanonicalTradeLifecycle


@pytest.fixture()
def isolated_runtime_db(tmp_path, monkeypatch):
    db.close_connection()
    db_path = tmp_path / "fresh_css_runtime.db"
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", db_path)
    yield db_path
    db.close_connection()


class RecordingTradeGate:
    def __init__(self) -> None:
        self.calls = []

    def approve_trade(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            approved=True,
            reason="canonical gate approved",
            details={"source": "recording_gate"},
        )


def test_trade_decision_orchestrator_sources_governance_from_canonical_gate(
    isolated_runtime_db,
    monkeypatch,
    tmp_path,
):
    import backend.intelligence.trade_decision_orchestrator as tdo

    importlib.reload(tdo)
    outcome_repository = TradeOutcomeRepository(tmp_path / "trade_outcomes.json")
    outcome_repository.create_storage()
    trade_runtime_service = tdo.TradeRuntimeService
    monkeypatch.setattr(
        tdo,
        "TradeRuntimeService",
        lambda: trade_runtime_service(
            canonical_lifecycle=CanonicalTradeLifecycle(outcome_repository)
        ),
    )
    gate = RecordingTradeGate()
    monkeypatch.setattr(tdo, "CSSUnifiedTradeGate", lambda: gate)

    orchestrator = tdo.TradeDecisionOrchestrator()

    decision = orchestrator.evaluate_trade(
        {
            "symbol": "BTC-USD",
            "asset_class": "crypto",
            "expected_value": 1,
            "cost": 0,
            "probability": 1,
            "engine_mode": "SAFE",
        }
    )

    assert gate.calls
    assert gate.calls[0]["candidate"] == {
        "symbol": "BTC-USD",
        "asset_class": "crypto",
        "expected_value": 1.0,
        "cost": 0.0,
        "probability": 1.0,
    }
    assert gate.calls[0]["engine_mode"] == "SAFE"
    assert decision["execute_trade"] is False
    assert decision["filters"]["governance_approved"] is True
    assert decision["filters"]["governance_reason"] == "canonical gate approved"
    assert decision["filters"]["governance_details"] == {"source": "recording_gate"}
    assert decision["filters"]["governance_source"] == "CSSUnifiedTradeGate"

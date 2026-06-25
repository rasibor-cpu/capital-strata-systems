from __future__ import annotations

import pytest

from backend.analytics.execution_selection_engine import (
    ExecutionSelectionEngine,
    ExecutionSelectionEngineError,
)


def _row(trade_id, symbol, score, confidence, recommendation="PREFERRED"):
    return {
        "trade_id": trade_id,
        "symbol": symbol,
        "quality_score": score,
        "confidence": confidence,
        "recommendation": recommendation,
    }


def test_top_candidate_selection() -> None:
    engine = ExecutionSelectionEngine()
    result = engine.select(
        [
            _row("t1", "AAPL", 90.0, 0.9, "EXECUTE"),
            _row("t2", "MSFT", 70.0, 0.8, "PREFERRED"),
            _row("t3", "TSLA", 60.0, 0.7, "WATCH"),
        ],
        acceptance_threshold=65.0,
        top_n=1,
    )

    assert [row["trade_id"] for row in result["selected"]] == ["t1"]


def test_rejected_candidate_reasons() -> None:
    engine = ExecutionSelectionEngine()
    result = engine.select(
        [
            _row("t1", "AAPL", 90.0, 0.9, "EXECUTE"),
            _row("t2", "MSFT", 50.0, 0.8, "WATCH"),
            _row("t3", "TSLA", 92.0, 0.95, "REJECT"),
        ],
        acceptance_threshold=65.0,
        top_n=2,
    )

    reasons = {row["trade_id"]: row["reason"] for row in result["rejected"]}
    assert reasons["t2"] == "below_threshold"
    assert reasons["t3"] == "recommendation_reject"


def test_invalid_inputs_fail_closed() -> None:
    engine = ExecutionSelectionEngine()
    with pytest.raises(ExecutionSelectionEngineError):
        engine.select("bad", acceptance_threshold=60.0, top_n=1)
    with pytest.raises(ExecutionSelectionEngineError):
        engine.select([], acceptance_threshold=120.0, top_n=1)


def test_empty_inputs_return_safe_empty_results() -> None:
    engine = ExecutionSelectionEngine()
    result = engine.select([], acceptance_threshold=60.0, top_n=2)
    assert result["selected"] == []
    assert result["rejected"] == []

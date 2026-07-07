from __future__ import annotations

import pytest
from backend.analytics.execution_quality_monitor import (
    ExecutionQualityMonitor,
    ExecutionQualityMonitorError,
)


def test_excellent_execution() -> None:
    monitor = ExecutionQualityMonitor()
    execution_event = {
        "trade_id": "tx1",
        "symbol": "BTCUSD",
        "fill_status": "FILLED",
        "expected_entry_price": 100.0,
        "actual_fill_price": 100.0,
        "latency_ms": 20.0,
        "spread_bps": 1.0,
    }

    result = monitor.evaluate_execution(execution_event)

    assert result["execution_quality_score"] >= 90.0
    assert result["execution_grade"] == "A"
    assert result["slippage_bps"] == 0.0
    assert result["latency_ms"] == 20.0
    assert result["spread_bps"] == 1.0
    assert "Low Slippage" in result["strengths"]
    assert "Tight Bid-Ask Spread" in result["strengths"]
    assert "Low Execution Latency" in result["strengths"]
    assert "Complete Fill" in result["strengths"]
    assert len(result["weaknesses"]) == 0


def test_poor_execution() -> None:
    monitor = ExecutionQualityMonitor()
    execution_event = {
        "trade_id": "tx2",
        "symbol": "BTCUSD",
        "fill_status": "FILLED",
        "expected_entry_price": 100.0,
        "actual_fill_price": 100.3,  # 30 bps slippage
        "latency_ms": 600.0,         # 40 latency score
        "spread_bps": 30.0,          # 40 spread score
    }

    result = monitor.evaluate_execution(execution_event)

    # (40 + 40 + 40 + 100)/4 = 55.0
    assert result["execution_quality_score"] == 55.0
    assert result["execution_grade"] == "F"
    assert "High Slippage" in result["weaknesses"]
    assert "Wide Bid-Ask Spread" in result["weaknesses"]
    assert "High Execution Latency" in result["weaknesses"]
    assert result["strengths"] == ["Complete Fill"]


def test_failed_rejected_execution() -> None:
    monitor = ExecutionQualityMonitor()
    execution_event_failed = {
        "trade_id": "tx3",
        "symbol": "BTCUSD",
        "fill_status": "FAILED",
        "expected_entry_price": 100.0,
        "actual_fill_price": 100.0,
        "latency_ms": 20.0,
        "spread_bps": 1.0,
    }
    execution_event_rejected = {
        "trade_id": "tx4",
        "symbol": "BTCUSD",
        "fill_status": "REJECTED",
        "expected_entry_price": 100.0,
        "actual_fill_price": 100.0,
        "latency_ms": 20.0,
        "spread_bps": 1.0,
    }

    result_failed = monitor.evaluate_execution(execution_event_failed)
    result_rejected = monitor.evaluate_execution(execution_event_rejected)

    assert result_failed["execution_quality_score"] == 0.0
    assert result_failed["execution_grade"] == "F"
    assert "Failed/Rejected Fill" in result_failed["weaknesses"]

    assert result_rejected["execution_quality_score"] == 0.0
    assert result_rejected["execution_grade"] == "F"
    assert "Failed/Rejected Fill" in result_rejected["weaknesses"]


def test_tight_spread_vs_wide_spread() -> None:
    monitor = ExecutionQualityMonitor()
    base_event = {
        "trade_id": "tx_spread",
        "symbol": "BTCUSD",
        "fill_status": "FILLED",
        "expected_entry_price": 100.0,
        "actual_fill_price": 100.0,
        "latency_ms": 10.0,
    }

    result_tight = monitor.evaluate_execution({**base_event, "spread_bps": 1.0})
    result_wide = monitor.evaluate_execution({**base_event, "spread_bps": 25.0})

    assert result_tight["execution_quality_score"] > result_wide["execution_quality_score"]
    assert result_tight["spread_bps"] == 1.0
    assert result_wide["spread_bps"] == 25.0


def test_low_latency_vs_high_latency() -> None:
    monitor = ExecutionQualityMonitor()
    base_event = {
        "trade_id": "tx_latency",
        "symbol": "BTCUSD",
        "fill_status": "FILLED",
        "expected_entry_price": 100.0,
        "actual_fill_price": 100.0,
        "spread_bps": 1.0,
    }

    result_low = monitor.evaluate_execution({**base_event, "latency_ms": 10.0})
    result_high = monitor.evaluate_execution({**base_event, "latency_ms": 500.0})

    assert result_low["execution_quality_score"] > result_high["execution_quality_score"]


def test_low_slippage_vs_high_slippage() -> None:
    monitor = ExecutionQualityMonitor()
    base_event = {
        "trade_id": "tx_slip",
        "symbol": "BTCUSD",
        "fill_status": "FILLED",
        "latency_ms": 10.0,
        "spread_bps": 1.0,
    }

    result_low = monitor.evaluate_execution({**base_event, "slippage_bps": 2.0})
    result_high = monitor.evaluate_execution({**base_event, "slippage_bps": 15.0})

    assert result_low["execution_quality_score"] > result_high["execution_quality_score"]


def test_invalid_input_fail_closed() -> None:
    monitor = ExecutionQualityMonitor()

    with pytest.raises(ExecutionQualityMonitorError, match="execution_event must be a Mapping"):
        monitor.evaluate_execution("not-a-dict")  # type: ignore

    with pytest.raises(ExecutionQualityMonitorError, match="Missing or empty required field in execution_event: trade_id"):
        monitor.evaluate_execution({"symbol": "BTCUSD", "fill_status": "FILLED"})

    with pytest.raises(ExecutionQualityMonitorError, match="Missing or empty required field in execution_event: symbol"):
        monitor.evaluate_execution({"trade_id": "tx1", "fill_status": "FILLED"})

    with pytest.raises(ExecutionQualityMonitorError, match="Missing or empty required field in execution_event: fill_status"):
        monitor.evaluate_execution({"trade_id": "tx1", "symbol": "BTCUSD"})

    with pytest.raises(ExecutionQualityMonitorError, match="Invalid fill_status"):
        monitor.evaluate_execution({"trade_id": "tx1", "symbol": "BTCUSD", "fill_status": "PENDING"})


def test_deterministic_output() -> None:
    monitor = ExecutionQualityMonitor()
    execution_event = {
        "trade_id": "tx_det",
        "symbol": "BTCUSD",
        "fill_status": "FILLED",
        "expected_entry_price": 100.0,
        "actual_fill_price": 100.0,
        "latency_ms": 50.0,
        "spread_bps": 2.0,
    }

    result1 = monitor.evaluate_execution(execution_event)
    result2 = monitor.evaluate_execution(execution_event)

    assert result1 == result2


def test_advisory_only_output() -> None:
    monitor = ExecutionQualityMonitor()
    execution_event = {
        "trade_id": "tx_adv",
        "symbol": "BTCUSD",
        "fill_status": "FILLED",
        "expected_entry_price": 100.0,
        "actual_fill_price": 100.0,
        "latency_ms": 50.0,
        "spread_bps": 2.0,
    }

    result = monitor.evaluate_execution(execution_event)

    assert result["advisory_only"] is True
    assert result["shadow_mode"] is True
    assert result["execution_action"] == "NO_EXECUTION"

"""ExecutionGate volatility sizing is applied (reduce-only, per instrument) instead of silently skipped.

Before the repair, ExecutionGate called VolatilityPositionSizer.size() without `price`, every call
raised TypeError, and the gate fell back to the unreduced notional with a warning.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from engine.execution.execution_gate import ExecutionGate


def _gate() -> ExecutionGate:
    return ExecutionGate()


def test_no_price_is_an_explicit_skip_not_a_hidden_fallback(caplog):
    gate, debug = _gate(), {}
    with caplog.at_level(logging.WARNING):
        assert gate._vol_size(instrument="EUR/USD", base_notional=100.0, price=None, debug=debug) == 100.0
    assert debug["vol_size_status"] == "skipped:price_unavailable"
    assert "fallback" not in caplog.text


def test_high_volatility_reduces_size():
    gate = _gate()
    out = None
    for i in range(30):  # alternating +/-5% moves: realized vol far above the 0.2% target
        debug = {}
        out = gate._vol_size(instrument="BTC/USD", base_notional=100.0, price=100.0 * (1.05 if i % 2 else 1.0),
                             debug=debug)
    assert debug["vol_size_status"] == "applied" and debug["vol_mult"] == 0.5
    assert out == 50.0


def test_low_volatility_never_enlarges_size():
    gate = _gate()
    for i in range(30):  # almost flat: the raw multiplier would be 2.0
        debug = {}
        out = gate._vol_size(instrument="EUR/USD", base_notional=100.0, price=1.0 + i * 1e-7, debug=debug)
    assert debug["vol_mult"] == 2.0
    assert out == 100.0 and debug["vol_upsizing_suppressed"] is True


def test_instruments_keep_separate_price_streams():
    gate = _gate()
    for i in range(30):
        gate._vol_size(instrument="BTC/USD", base_notional=100.0, price=100.0 * (1.05 if i % 2 else 1.0), debug={})
    debug = {}
    gate._vol_size(instrument="EUR/USD", base_notional=100.0, price=1.08, debug=debug)
    assert debug["vol_mult"] == 1.0  # EUR/USD is still in warm-up; BTC volatility does not leak into it


def test_evaluate_trade_passes_price_and_never_hits_the_old_fallback(caplog, tmp_path):
    margin = SimpleNamespace(buying_power=10_000.0, margin_state="NORMAL", margin_ratio=0.0)
    kwargs = dict(margin_snapshot=margin, instrument="EUR/USD", side="BUY", notional=500.0, stop_distance_pct=0.02, equity=10_000.0,
                  equity_peak=10_000.0, regime_persistence=0.6, expected_move_bps=80.0, fee_bps=2.0, spread_bps=1.0,
                  slippage_bps=1.0, broker_mode="PAPER")
    gate = ExecutionGate(anti_bleed_guard=AntiBleedGuard(state_file=str(tmp_path / "ab1.json")))
    with caplog.at_level(logging.WARNING):
        decision = gate.evaluate_trade(**kwargs, price=1.08)
    assert decision["debug"]["vol_size_status"] == "applied", decision["reason"]
    assert "volatility sizing fallback" not in caplog.text
    legacy_gate = ExecutionGate(anti_bleed_guard=AntiBleedGuard(state_file=str(tmp_path / "ab2.json")))
    legacy = legacy_gate.evaluate_trade(**kwargs)  # callers without a price keep working
    assert legacy["debug"]["vol_size_status"] == "skipped:price_unavailable"

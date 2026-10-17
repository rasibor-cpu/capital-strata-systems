"""Closeout C1: ExecutionGate sizing (volatility #120, drawdown) reaches paper fills, reduce-only.

Before: CanonicalExecutionIntegration kept only the gate's ALLOW/BLOCK reason, so the gate's
scaled_notional never affected the router's fill. Now the engine applies min(notional, scaled):
never larger, never below AntiBleed's minimum, invalid values fail closed.
"""
from __future__ import annotations

import pytest

from css118_support import NOW, activate, follower, signal, system
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, CopyTradeEngine
from engine.execution import execution_gate as eg


@pytest.fixture(autouse=True)
def _no_ambient_kill_switch(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH"):
        monkeypatch.delenv(name, raising=False)


def _engine(tmp_path):
    engine = CopyTradeEngine(tmp_path / "tp", key_provider=None)
    activate(engine.consent, "auto-1", "CSS Autonomous Trading", "Balanced")
    return engine


def _force_scaled(monkeypatch, value):
    real = eg.ExecutionGate.evaluate_trade

    def patched(self, **kw):
        out = real(self, **kw)
        out.setdefault("debug", {})["scaled_notional"] = value(kw["notional"]) if callable(value) else value
        return out
    monkeypatch.setattr(eg.ExecutionGate, "evaluate_trade", patched)


def _evaluate(engine, **kw):
    return engine.evaluate(signal(trader_id=AUTONOMOUS_SOURCE_ID, **kw), follower("auto-1"), system(), now=NOW)


def test_price_reaches_the_gate_and_sizing_is_recorded(tmp_path):
    d = _evaluate(_engine(tmp_path))
    assert d.outcome == "COPIED"
    assert d.fill["gate_sizing"]["vol_size_status"] in {"applied", "applied:capped_at_base"}
    assert d.fill["notional"] <= d.fill["requested_notional"] == 500.0


def test_gate_reduction_is_applied_to_the_fill(tmp_path, monkeypatch):
    _force_scaled(monkeypatch, lambda n: n * 0.6)
    d = _evaluate(_engine(tmp_path))
    assert d.outcome == "COPIED" and d.fill["notional"] == 300.0 and d.notional == 300.0
    assert d.fill["requested_notional"] == 500.0


def test_gate_can_never_enlarge_the_order(tmp_path, monkeypatch):
    _force_scaled(monkeypatch, lambda n: n * 3.0)  # e.g. low-volatility expansion
    d = _evaluate(_engine(tmp_path))
    assert d.outcome == "COPIED" and d.fill["notional"] == 500.0


def test_reduction_below_antibleed_minimum_is_rejected_not_kept(tmp_path, monkeypatch):
    _force_scaled(monkeypatch, 49.99)
    d = _evaluate(_engine(tmp_path))
    assert (d.outcome, d.stage, d.reason) == ("REJECTED", "execution_gate", "anti_bleed_min_size_after_gate_reduction")
    assert d.fill is None


@pytest.mark.parametrize("bad", [0.0, -5.0, float("nan"), float("inf")])
def test_invalid_gate_size_fails_closed(tmp_path, monkeypatch, bad):
    _force_scaled(monkeypatch, bad)
    d = _evaluate(_engine(tmp_path))
    assert (d.outcome, d.stage, d.reason) == ("REJECTED", "execution_gate", "gate_scaled_size_invalid_or_zero")


def test_volatility_state_is_shared_per_instrument_across_evaluations(tmp_path):
    engine = _engine(tmp_path)
    for i in range(12):
        _evaluate(engine, signal_id=f"s{i}", reference_price=1.08 * (1.05 if i % 2 else 1.0))
    assert "EUR/USD" in engine._vol_sizers  # one rolling stream per instrument, kept between calls

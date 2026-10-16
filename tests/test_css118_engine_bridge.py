"""Closeout C2: CSS engine signals enter the governed router only through the provenance-checked bridge."""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from css118_support import KEY, SESSION, activate, system
from backend.trading_profiles.copy_engine import CopyTradeEngine
from backend.trading_profiles.engine_bridge import (
    CssEngineSignalBridge,
    Provenance,
    source_signal_from_engine_event,
)
from backend.trading_profiles.router import PaperBook, TradingRouter
from engine.engine_loop import EngineLoop


@pytest.fixture(autouse=True)
def _no_ambient_kill_switch(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def bridge(tmp_path):
    engine = CopyTradeEngine(tmp_path / "tp", key_provider=lambda: KEY)
    sess = (SESSION, time.time())
    router = TradingRouter(engine, book=PaperBook(engine.root), role_resolver=lambda u: "TRADER",
                           session_resolver=lambda u: sess, system_provider=lambda: system())
    activate(engine.consent, "auto-1", "CSS Autonomous Trading", "Balanced")
    return CssEngineSignalBridge(router)


def _event(**kw):
    base = {"instrument": "EUR/USD", "price": 1.08, "step": 7, "direction": "BUY", "strength": 0.8,
            "stop_distance_fraction": 0.02, "fee_bps": 1.0, "spread_bps": 1.0, "slippage_bps": 1.0,
            "regime_persistence": 0.95}
    base.update(kw)
    return base


def CALIBRATED(event):  # synthetic stand-in for an owner-approved calibration
    return {"probability": 0.67, "signal_score": 16.0, "strategy_score": 0.9, "replay_confidence": 0.9}


def test_uncalibrated_engine_signal_is_refused_and_routes_to_nobody(bridge):
    sink = bridge.engine_loop_sink(None, asset_class="FX")
    sink(_event())
    assert bridge.refusals[-1]["reason"] == "engine_signal_uncalibrated"
    assert bridge.router.book.positions() == [] and bridge.router.engine.ledger.records() == []


def test_calibrated_engine_signal_reaches_followers_through_all_gates(bridge):
    signal, provenance, _ = source_signal_from_engine_event(_event(), CALIBRATED, asset_class="FX")
    assert provenance is Provenance.ENGINE_LOOP_CALIBRATED
    assert signal.stop_distance_pct == 2.0 and signal.expected_move_bps == 80.0  # fraction -> percent
    result = bridge.publish(signal, provenance)
    (d,) = result.decisions
    assert result.accepted and d.outcome == "COPIED" and d.pipeline_status == "validated_not_executed"


def test_legacy_random_candidates_are_never_routed(bridge):
    r = bridge.publish_legacy_candidate(symbol="BTC-USD", asset_class="CRYPTO", signal_score=12.0, probability=0.68)
    assert (r.accepted, r.reason) == (False, "engine_signal_provenance_not_approved:LEGACY_RANDOM_CANDIDATE")
    assert bridge.router.engine.ledger.records() == []


@pytest.mark.parametrize("calibration,reason", [
    (lambda e: None, "engine_signal_calibration_declined"),
    (lambda e: {"probability": 1.5, "signal_score": 16.0}, "engine_signal_calibration_invalid"),
    (lambda e: {"probability": 0.6, "signal_score": float("nan")}, "engine_signal_calibration_invalid"),
    (lambda e: {"probability": 0.6, "signal_score": 16.0, "strategy_score": -1}, "engine_signal_calibration_invalid"),
    (lambda e: (0.6, 16.0), "engine_signal_calibration_declined"),
    (lambda e: 1 / 0, "engine_signal_calibration_declined"),
])
def test_bad_calibration_fails_closed(bridge, calibration, reason):
    bridge.engine_loop_sink(calibration, asset_class="FX")(_event())
    assert bridge.refusals[-1]["reason"] == reason


@pytest.mark.parametrize("event,reason", [
    (_event(direction="FLAT"), "engine_event_not_directional"),
    (_event(price=0), "engine_event_incomplete"),
    (_event(stop_distance_fraction=float("inf")), "engine_event_incomplete"),
    (_event(fee_bps=-1), "engine_event_costs_invalid"),
])
def test_malformed_engine_events_fail_closed(bridge, event, reason):
    bridge.engine_loop_sink(CALIBRATED, asset_class="FX")(event)
    assert bridge.refusals[-1]["reason"] == reason


def test_uncalibrated_quality_inputs_keep_conservative_defaults_and_are_gated(bridge):
    signal, provenance, _ = source_signal_from_engine_event(
        _event(), lambda e: {"probability": 0.67, "signal_score": 16.0}, asset_class="FX")
    (d,) = bridge.publish(signal, provenance).decisions
    assert (d.outcome, d.stage) == ("REJECTED", "trade_quality")  # no invented quality: the gate decides


@pytest.mark.parametrize("provenance", [Provenance.LEGACY_RANDOM_CANDIDATE, Provenance.UNCALIBRATED])
def test_valid_signal_with_unapproved_provenance_is_refused(bridge, provenance):
    signal, _, _ = source_signal_from_engine_event(_event(), CALIBRATED, asset_class="FX")
    r = bridge.publish(signal, provenance)
    assert (r.accepted, r.reason) == (False, f"engine_signal_provenance_not_approved:{provenance.value}")
    assert bridge.router.book.positions() == [] and bridge.router.engine.ledger.records() == []


def test_bridge_cannot_widen_routable_provenance(bridge):
    wide = CssEngineSignalBridge(bridge.router, routable=frozenset(Provenance))
    assert wide.routable == frozenset({Provenance.ENGINE_LOOP_CALIBRATED})


def _loop_with_sink(sink):
    loop = EngineLoop(starting_equity=1000.0)
    loop.signal_engine = SimpleNamespace(generate=lambda **_: SimpleNamespace(direction="BUY", strength=0.9))
    loop.regime_gate = lambda inputs: {"decision": "ALLOW", "reason": "ok"}
    loop.audit_logger = None
    loop.css_signal_sink = sink
    return loop


def test_engine_loop_publishes_events_through_the_bridge(bridge):
    loop = _loop_with_sink(bridge.engine_loop_sink(CALIBRATED, asset_class="FX"))
    loop.process_bar("EUR/USD", 1.10)
    loop.process_bar("EUR/USD", 1.11)
    copied = [p for p in bridge.router.book.positions() if p.follower_user_id == "auto-1"]
    assert len(copied) == 1 and copied[0].symbol == "EUR/USD"


def test_engine_loop_unchanged_without_sink_and_isolated_from_sink_errors():
    calls = []
    plain = _loop_with_sink(None)
    plain.process_bar("EUR/USD", 1.10)
    plain.process_bar("EUR/USD", 1.11)

    def broken(event):
        calls.append(event)
        raise RuntimeError("router down")
    noisy = _loop_with_sink(broken)
    noisy.process_bar("EUR/USD", 1.10)
    noisy.process_bar("EUR/USD", 1.11)  # must not raise
    assert len(calls) == 1
    assert noisy.total_signals == plain.total_signals and noisy.gate_blocks == plain.gate_blocks

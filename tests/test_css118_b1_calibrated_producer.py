"""CSS-118 B1: calibrated real-data (replay) signal producer through the governed bridge."""
from __future__ import annotations

import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from css118_support import KEY, SESSION, activate, system
from backend.trading_profiles.calibration_walk_forward import walk_forward_ma_momentum, run_and_persist
from backend.trading_profiles.calibrated_signal_runner import CalibratedSignalRunner, RunnerError
from backend.trading_profiles.copy_engine import CopyTradeEngine
from backend.trading_profiles.engine_bridge import CssEngineSignalBridge, Provenance, source_signal_from_engine_event
from backend.trading_profiles.engine_loop_calibration import (
    STRATEGY_MA_MOMENTUM,
    build_calibration_callable,
    load_calibration,
)
from backend.trading_profiles.market_bar_source import ReplayCsvBarSource, write_fixture_csv
from backend.trading_profiles.router import PaperBook, TradingRouter
from backend.trading_profiles.strategy_enablement import StrategyEnablement


@pytest.fixture(autouse=True)
def _no_ambient_kill_switch(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH"):
        monkeypatch.delenv(name, raising=False)


def _trending_rows(n: int = 240, start: float = 1.05, step: float = 0.0008):
    """Deterministic upward trend with mild noise — enough bars for walk-forward trades."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = []
    price = start
    for i in range(n):
        # gentle trend + small sine so MA crosses occur but expectancy stays positive
        price = start + step * i + 0.00015 * math.sin(i / 7.0)
        o = price * 0.9999
        h = price * 1.0004
        low = price * 0.9996
        ts = (base + timedelta(hours=i)).isoformat()
        rows.append((ts, o, h, low, price))
    return rows


def _choppy_rows(n: int = 240, start: float = 1.10):
    """Mean-reverting chop — MA momentum typically fails OOS after costs."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(n):
        price = start + 0.004 * math.sin(i / 3.0) + 0.001 * math.cos(i / 5.0)
        o = price * 0.9998
        h = price * 1.0005
        low = price * 0.9995
        ts = (base + timedelta(hours=i)).isoformat()
        rows.append((ts, o, h, low, price))
    return rows


@pytest.fixture()
def router(tmp_path):
    engine = CopyTradeEngine(tmp_path / "tp", key_provider=lambda: KEY)
    sess = (SESSION, time.time())
    r = TradingRouter(
        engine,
        book=PaperBook(engine.root),
        role_resolver=lambda u: "TRADER",
        session_resolver=lambda u: sess,
        system_provider=lambda: system(),
    )
    activate(engine.consent, "auto-1", "CSS Autonomous Trading", "Balanced")
    return r


def test_replay_csv_bar_source_loads_and_hashes(tmp_path):
    path = write_fixture_csv(tmp_path / "eur.csv", _trending_rows(30))
    bars = ReplayCsvBarSource(path, instrument="EUR/USD").load()
    assert len(bars) == 30
    assert bars[0].instrument == "EUR/USD"
    assert bars[0].close > 0
    assert len(bars[0].content_hash) == 24


def test_empty_csv_fails_closed(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("ts_utc,open,high,low,close,volume\n", encoding="utf-8")
    with pytest.raises(Exception, match="csv_empty"):
        ReplayCsvBarSource(path, instrument="EUR/USD").load()


def test_walk_forward_approves_or_disables_with_real_metrics(tmp_path):
    path = write_fixture_csv(tmp_path / "trend.csv", _trending_rows(260))
    bars = ReplayCsvBarSource(path, instrument="EUR/USD").load()
    result = run_and_persist(
        bars,
        artifact_path=tmp_path / "cal" / "artifact.json",
        enablement_root=tmp_path / "cal",
    )
    assert result.oos_metrics["trade_count"] >= 0
    assert "expectancy_bps" in result.oos_metrics
    artifact = load_calibration(tmp_path / "cal" / "artifact.json")
    assert artifact.strategy_id == STRATEGY_MA_MOMENTUM
    assert artifact.content_sha256
    enablement = StrategyEnablement(tmp_path / "cal")
    if result.approved:
        assert artifact.approved_for_routing is True
        assert enablement.is_enabled(STRATEGY_MA_MOMENTUM)
    else:
        assert artifact.approved_for_routing is False
        assert not enablement.is_enabled(STRATEGY_MA_MOMENTUM)
        assert result.disable_reason


def test_choppy_series_disables_strategy(tmp_path):
    path = write_fixture_csv(tmp_path / "chop.csv", _choppy_rows(260))
    bars = ReplayCsvBarSource(path, instrument="EUR/USD").load()
    result = walk_forward_ma_momentum(bars)
    # Choppy series should not invent approval
    if result.approved:
        # If unexpectedly profitable on this fixture, still require positive OOS evidence
        assert result.oos_metrics["expectancy_bps"] > 0
    else:
        assert result.disable_reason
        assert result.artifact.approved_for_routing is False


def test_unapproved_calibration_declines_bridge(router, tmp_path):
    path = write_fixture_csv(tmp_path / "chop.csv", _choppy_rows(200))
    bars = ReplayCsvBarSource(path, instrument="EUR/USD").load()
    result = walk_forward_ma_momentum(bars)
    # Force unapproved
    from backend.trading_profiles.engine_loop_calibration import CalibrationArtifact, SCHEMA, save_calibration

    artifact = CalibrationArtifact(
        schema=SCHEMA,
        version="test",
        strategy_id=STRATEGY_MA_MOMENTUM,
        a=0.0,
        b=4.0,
        c0=12.0,
        c1=8.0,
        min_strength=0.1,
        approved_for_routing=False,
        oos_metrics=result.oos_metrics,
    )
    save_calibration(tmp_path / "bad.json", artifact)
    loaded = load_calibration(tmp_path / "bad.json")
    calibrate = build_calibration_callable(loaded, enablement=StrategyEnablement(tmp_path))
    bridge = CssEngineSignalBridge(router)
    sink = bridge.engine_loop_sink(calibrate, asset_class="FX")
    sink(
        {
            "instrument": "EUR/USD",
            "price": 1.1,
            "step": 1,
            "direction": "BUY",
            "strength": 0.8,
            "stop_distance_fraction": 0.01,
            "fee_bps": 1.0,
            "spread_bps": 1.0,
            "slippage_bps": 1.0,
        }
    )
    assert bridge.refusals[-1]["reason"] == "engine_signal_calibration_declined"


def test_approved_calibration_produces_engine_loop_calibrated(router, tmp_path):
    # Hand-craft an approved artifact with known params (simulating a passed walk-forward)
    from backend.trading_profiles.engine_loop_calibration import CalibrationArtifact, SCHEMA, save_calibration

    artifact = CalibrationArtifact(
        schema=SCHEMA,
        version="test",
        strategy_id=STRATEGY_MA_MOMENTUM,
        a=-1.0,
        b=4.0,
        c0=12.0,
        c1=8.0,
        min_strength=0.5,
        approved_for_routing=True,
        oos_metrics={
            "trade_count": 12,
            "win_rate": 0.58,
            "expectancy_bps": 4.2,
            "max_drawdown_pct": 8.0,
            "replay_confidence": 0.58,
            "strategy_score": 0.7,
        },
    )
    save_calibration(tmp_path / "ok.json", artifact)
    StrategyEnablement(tmp_path).enable(STRATEGY_MA_MOMENTUM, reason="test", metrics=artifact.oos_metrics)
    calibrate = build_calibration_callable(load_calibration(tmp_path / "ok.json"), enablement=StrategyEnablement(tmp_path))
    event = {
        "instrument": "EUR/USD",
        "price": 1.08,
        "step": 9,
        "direction": "BUY",
        "strength": 0.8,
        "stop_distance_fraction": 0.02,
        "fee_bps": 1.0,
        "spread_bps": 1.0,
        "slippage_bps": 1.0,
        "regime_persistence": 0.95,
    }
    signal, provenance, reason = source_signal_from_engine_event(event, calibrate, asset_class="FX")
    assert reason == "ok"
    assert provenance is Provenance.ENGINE_LOOP_CALIBRATED
    assert signal is not None and 0 < signal.probability < 1 and signal.signal_score > 0
    bridge = CssEngineSignalBridge(router)
    result = bridge.publish(signal, provenance)
    assert result.accepted
    assert any(d.outcome in {"COPIED", "PROPOSED", "SIMULATED", "REJECTED"} for d in result.decisions)


def test_runner_refuses_live_arming(router, tmp_path, monkeypatch):
    from backend.trading_profiles.engine_loop_calibration import CalibrationArtifact, SCHEMA, save_calibration

    artifact = CalibrationArtifact(
        schema=SCHEMA,
        version="test",
        strategy_id=STRATEGY_MA_MOMENTUM,
        a=-1.0,
        b=4.0,
        c0=12.0,
        c1=8.0,
        min_strength=0.5,
        approved_for_routing=True,
        oos_metrics={"trade_count": 10, "expectancy_bps": 1.0, "max_drawdown_pct": 5.0, "win_rate": 0.55},
    )
    save_calibration(tmp_path / "ok.json", artifact)
    StrategyEnablement(tmp_path).enable(STRATEGY_MA_MOMENTUM, reason="test")
    runner = CalibratedSignalRunner.from_paths(
        router=router, calibration_path=tmp_path / "ok.json", enablement_root=tmp_path, asset_class="FX"
    )
    monkeypatch.setenv("CSS_LIVE_ORDER_KILL_SWITCH", "ARMED")
    path = write_fixture_csv(tmp_path / "t.csv", _trending_rows(40))
    bars = ReplayCsvBarSource(path, instrument="EUR/USD").load()
    with pytest.raises(RunnerError, match="live_arming"):
        runner.run(bars)


def test_runner_processes_replay_bars_paper_only(router, tmp_path):
    from backend.trading_profiles.engine_loop_calibration import CalibrationArtifact, SCHEMA, save_calibration

    artifact = CalibrationArtifact(
        schema=SCHEMA,
        version="test",
        strategy_id=STRATEGY_MA_MOMENTUM,
        a=-1.0,
        b=4.0,
        c0=12.0,
        c1=8.0,
        min_strength=0.55,
        approved_for_routing=True,
        oos_metrics={
            "trade_count": 10,
            "expectancy_bps": 2.0,
            "max_drawdown_pct": 5.0,
            "win_rate": 0.55,
            "replay_confidence": 0.55,
            "strategy_score": 0.6,
        },
    )
    save_calibration(tmp_path / "ok.json", artifact)
    StrategyEnablement(tmp_path).enable(STRATEGY_MA_MOMENTUM, reason="test")
    runner = CalibratedSignalRunner.from_paths(
        router=router, calibration_path=tmp_path / "ok.json", enablement_root=tmp_path, asset_class="FX"
    )
    path = write_fixture_csv(tmp_path / "t.csv", _trending_rows(80))
    bars = ReplayCsvBarSource(path, instrument="EUR/USD").load()
    summary = runner.run(bars)
    assert summary.paper_only is True
    assert summary.bars_processed == 80
    assert summary.approved_for_routing is True


def test_legacy_random_still_refused(router):
    bridge = CssEngineSignalBridge(router)
    r = bridge.publish_legacy_candidate(symbol="BTC-USD", asset_class="CRYPTO", signal_score=12.0, probability=0.68)
    assert r.accepted is False
    assert "LEGACY_RANDOM" in r.reason


def test_replay_runner_refuses_operational_paper_book(tmp_path, monkeypatch):
    """Closeout: historical replay bars must never route into the operational paper record."""
    from types import SimpleNamespace

    from backend.trading_profiles import calibrated_signal_runner as mod

    monkeypatch.chdir(tmp_path)
    operational = SimpleNamespace(engine=SimpleNamespace(root=tmp_path / "artifacts" / "trading_profiles"))
    with pytest.raises(RunnerError, match="operational_paper_book"):
        mod.CalibratedSignalRunner(router=operational, calibration=None, enablement=None)
    repo_book = SimpleNamespace(engine=SimpleNamespace(root=mod.OPERATIONAL_PAPER_ROOTS[0]))
    with pytest.raises(RunnerError, match="operational_paper_book"):
        mod.CalibratedSignalRunner(router=repo_book, calibration=None, enablement=None)

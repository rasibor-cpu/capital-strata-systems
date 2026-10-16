"""Closeout: governed paper position limits (10 total; crypto 3, FX 3, options 2, futures 2) can only tighten."""
from __future__ import annotations

from backend.governance.css_unified_trade_gate import MAX_POSITIONS_BY_ASSET
from engine.governance.position_limit_policy import MAX_TOTAL_OPEN_POSITIONS, PositionLimitConfig


def test_governed_per_asset_caps_and_total():
    assert MAX_POSITIONS_BY_ASSET == {"crypto": 3, "fx": 3, "futures": 2, "options": 2}
    assert sum(MAX_POSITIONS_BY_ASSET.values()) == MAX_TOTAL_OPEN_POSITIONS == 10


def test_environment_can_tighten_but_never_loosen(monkeypatch):
    monkeypatch.setenv("CSS_MAX_TOTAL_OPEN_POSITIONS", "50")
    monkeypatch.setenv("CSS_MAX_NEW_POSITIONS_PER_CYCLE", "9")
    cfg = PositionLimitConfig.from_env()
    assert cfg.max_total_open_positions == 10 and cfg.max_new_positions_per_cycle == 2
    monkeypatch.setenv("CSS_MAX_TOTAL_OPEN_POSITIONS", "4")
    assert PositionLimitConfig.from_env().max_total_open_positions == 4
    for bad in ("0", "-3", "abc"):
        monkeypatch.setenv("CSS_MAX_TOTAL_OPEN_POSITIONS", bad)
        assert PositionLimitConfig.from_env().max_total_open_positions == 10

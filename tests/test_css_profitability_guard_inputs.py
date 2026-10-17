"""Focused fail-closed input checks for the cost-aware AntiBleedGuard."""

import math

import pytest

from backend.app.risk.anti_bleed_guard import AntiBleedGuard


@pytest.mark.parametrize("field,value", [
    ("trade_size", float("nan")),
    ("expected_move_bps", float("inf")),
    ("fee_bps", float("nan")),
    ("spread_bps", -1.0),
    ("slippage_bps", float("-inf")),
    ("trade_size", 0.0),
    ("fee_bps", -0.1),
    ("trade_size", "not-a-number"),
])
def test_invalid_inputs_never_approve_even_with_dev_override(tmp_path, field, value):
    guard = AntiBleedGuard(dev_force_allow=True, state_file=str(tmp_path / "state.json"))
    kwargs = dict(symbol="TEST", trade_size=100.0, expected_move_bps=100.0,
                  fee_bps=1.0, spread_bps=1.0, slippage_bps=1.0)
    kwargs[field] = value
    result = guard.evaluate(**kwargs)
    assert result["approved"] is False
    assert not (tmp_path / "state.json").exists()


def test_valid_cost_aware_approval_still_works(tmp_path):
    guard = AntiBleedGuard(state_file=str(tmp_path / "state.json"))
    result = guard.evaluate(symbol="TEST", trade_size=100.0,
                            expected_move_bps=100.0, fee_bps=5.0,
                            spread_bps=5.0, slippage_bps=5.0)
    assert result["approved"] is True
    assert result["net_edge_bps"] == 85.0

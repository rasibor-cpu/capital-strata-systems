"""Focused validation of nonfinite inputs in canonical position PnL."""
import math
import pytest
from backend.app.accounting.pnl_engine import (
    ExecutionCost, InstrumentSpec, Position, compute_position_pnl,
)


def position(**changes):
    values = dict(symbol="TEST", side="LONG", entry_price=100.0,
                  current_price=110.0, quantity=2.0,
                  instrument_spec=InstrumentSpec("TEST", "EQUITY"),
                  entry_cost=ExecutionCost(), estimated_exit_cost=ExecutionCost())
    values.update(changes)
    return Position(**values)


@pytest.mark.parametrize("field,value", [
    ("entry_price", float("nan")),
    ("current_price", float("inf")),
    ("quantity", float("nan")),
    ("quantity", -1.0),
])
def test_invalid_pnl_inputs_fail_closed(field, value):
    with pytest.raises(ValueError):
        compute_position_pnl(position(**{field: value}))


@pytest.mark.parametrize("multiplier", [float("nan"), float("inf"), 0.0, -1.0])
def test_invalid_multiplier_rejected(multiplier):
    with pytest.raises(ValueError):
        compute_position_pnl(position(instrument_spec=InstrumentSpec("TEST", "FUTURES", multiplier=multiplier)))


@pytest.mark.parametrize("cost", [ExecutionCost(spread=float("nan")), ExecutionCost(fees=-1.0), ExecutionCost(slippage=float("inf"))])
def test_invalid_exit_cost_rejected(cost):
    with pytest.raises(ValueError):
        compute_position_pnl(position(estimated_exit_cost=cost))


def test_valid_pnl_unchanged():
    result = compute_position_pnl(position(estimated_exit_cost=ExecutionCost(1, 1, 1)))
    assert result.gross_unrealized == 20.0
    assert result.net_unrealized == 17.0

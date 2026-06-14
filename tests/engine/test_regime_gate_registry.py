from __future__ import annotations

from engine.decision_builder import GateInputs
from engine.gates_registry import get_configured_gates


def _inputs(
    *,
    bars_5m: object = 52,
    vol_norm_0_1: float = 0.35,
    spread_bps: float = 1.2,
    high_risk_news: bool = False,
) -> GateInputs:
    snapshot = {
        "price": 1.1,
        "bars_5m": bars_5m,
        "high_risk_news": high_risk_news,
    }
    return GateInputs(
        instrument="EURUSD",
        snapshot=snapshot,
        volatility={"vol_norm_0_1": vol_norm_0_1},
        liquidity={"spread_bps": spread_bps},
        slippage={},
        risk={},
    )


def _regime_gate():
    gates = get_configured_gates()
    assert "regime_gate" in gates
    return gates["regime_gate"]


def test_registry_exposes_regime_gate_entry() -> None:
    gate = _regime_gate()

    assert callable(gate)


def test_registry_regime_gate_allows_safe_inputs() -> None:
    decision = _regime_gate()(_inputs())

    assert set(decision) == {"decision", "reason"}
    assert decision == {"decision": "ALLOW", "reason": "ok"}


def test_registry_regime_gate_blocks_unsafe_inputs() -> None:
    decision = _regime_gate()(_inputs(vol_norm_0_1=0.95))

    assert set(decision) == {"decision", "reason"}
    assert decision["decision"] == "BLOCK"
    assert decision["reason"] == "vol_too_high"


def test_registry_regime_gate_missing_required_inputs_fail_closed() -> None:
    malformed = GateInputs(
        instrument="EURUSD",
        snapshot={"price": 1.1},
        volatility={"vol_norm_0_1": 0.35},
        liquidity={"spread_bps": 1.2},
        slippage={},
        risk={},
    )

    decision = _regime_gate()(malformed)

    assert set(decision) == {"decision", "reason"}
    assert decision["decision"] == "BLOCK"
    assert "MISSING_REQUIRED bars_5m" in decision["reason"]


def test_registry_regime_gate_malformed_inputs_fail_closed() -> None:
    decision = _regime_gate()(_inputs(bars_5m="not-a-number"))

    assert set(decision) == {"decision", "reason"}
    assert decision["decision"] == "BLOCK"
    assert "MISSING_REQUIRED bars_5m" in decision["reason"]


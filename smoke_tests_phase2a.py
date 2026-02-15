"""
Phase 2A Smoke Tests – Capital Strata Systems / REA Capital Trading Engine

Goals:
- Validate adapter-based gates registry runs end-to-end
- Confirm capability gate blocks futures on default FX adapter
- Confirm capability gate ALLOWs futures when futures adapter is mapped
- Confirm futures sizing path is reachable (structural sizing only)

Run:
  python smoke_tests_phase2a.py
"""

from __future__ import annotations

from typing import Any, Dict

from engine.decision_builder import GateInputs, build_trade_execution_decision
from engine.gates_registry import get_configured_gates


def _print_decision(d: Any) -> None:
    # ExecutionDecision is dataclass-like with fields; we also expose as_dict() in some builds
    d_dict = d.as_dict() if hasattr(d, "as_dict") else {}

    final = getattr(d, "final_decision", None) or d_dict.get("final_decision") or "?"
    primary = getattr(d, "primary_reason", None) or d_dict.get("primary_reason") or "?"
    gate_results = getattr(d, "gate_results", None) or d_dict.get("gate_results") or {}

    gates_view: Dict[str, str] = {}
    try:
        for k, v in gate_results.items():
            if isinstance(v, dict):
                gates_view[k] = str(v.get("decision", "?"))
            else:
                gates_view[k] = str(getattr(v, "decision", "?"))
    except Exception:
        gates_view = {"_error": "could_not_render_gate_results"}

    print("FINAL:", final)
    print("PRIMARY:", primary)
    print("GATES:", gates_view)

    # Helpful for debugging structure drift
    fields = list(d_dict.keys()) if isinstance(d_dict, dict) else []
    if fields:
        print("FIELDS:", fields)


def _run_fx_smoke() -> None:
    print("\n=== FX SMOKE ===")

    gates = get_configured_gates()

    state = {
        "adapter_name": "default_fx_adapter",
        "adapter_capabilities": {"fx": True, "futures": False},
        "asset_class": "fx",
    }

    inputs = GateInputs(
        instrument="EUR_USD",
        snapshot={"price": 1.0},
        volatility={"atr": 0.01},
        liquidity={"spread": 0.0001},
        slippage={"expected": 0.0, "max": 0.0002},
        risk={
            "equity": 100000.0,
            "risk_pct": 1.0,
            "drawdown_pct": 2.0,
            "max_drawdown_pct": 15.0,
            "loss_streak": 0,
            "max_loss_streak": 5,
            "daily_loss_pct": 0.5,
            "max_daily_loss_pct": 3.0,
        },
        state=state,
    )

    d = build_trade_execution_decision(
        engine_run_id="smoke-001",
        mode="TEST",
        inputs=inputs,
        gates=gates,
    )
    _print_decision(d)


def _run_futures_smoke_default_fx_adapter_should_block() -> None:
    print("\n=== FUTURES SMOKE (DEFAULT FX ADAPTER SHOULD BLOCK) ===")

    gates = get_configured_gates()

    state = {
        "adapter_name": "default_fx_adapter",
        "adapter_capabilities": {"fx": True, "futures": False},
        "asset_class": "futures",
    }

    inputs = GateInputs(
        instrument="ES",
        snapshot={"price": 5000.0},
        volatility={"atr": 10.0},
        liquidity={"spread": 0.25},
        slippage={"expected": 0.0, "max": 1.0},
        risk={
            "equity": 100000.0,
            "risk_pct": 1.0,
        },
        state=state,
    )

    d = build_trade_execution_decision(
        engine_run_id="smoke-002",
        mode="TEST",
        inputs=inputs,
        gates=gates,
    )
    _print_decision(d)


def _run_futures_smoke_futures_adapter_mapped() -> None:
    print("\n=== FUTURES SMOKE (FUTURES ADAPTER MAPPED) ===")

    gates = get_configured_gates()

    # Futures adapter allowed
    state = {
        "adapter_name": "futures_adapter",
        "adapter_capabilities": {"fx": True, "futures": True},
        "asset_class": "futures",

        # ---- futures sizing inputs (structural-only) ----
        # Use a 25% futures bucket of total equity (policy baseline).
        "futures_capital_bucket": 25000.0,

        # Risk % per trade (percent)
        "risk_pct": 1.0,

        # Stop distance in points
        "stop_distance_points": 10.0,

        # Minimal contract spec - adjust fields to match FuturesContractSpec in your repo
        # If your FuturesContractSpec uses different field names, update here only.
        "futures_contract_spec": {
            "symbol": "ES",
            "point_value": 50.0,          # ES: $50 per point
            "initial_margin": 12000.0,    # placeholder; broker-specific
            "maintenance_margin": 11000.0 # placeholder
        },
    }

    inputs = GateInputs(
        instrument="ES",
        snapshot={"price": 5000.0},
        volatility={"atr": 10.0},
        liquidity={"spread": 0.25},
        slippage={"expected": 0.0, "max": 1.0},
        risk={
            "equity": 100000.0,
            "risk_pct": 1.0,
        },
        state=state,
    )

    d = build_trade_execution_decision(
        engine_run_id="smoke-003",
        mode="TEST",
        inputs=inputs,
        gates=gates,
    )
    _print_decision(d)

    # Also show sizing output directly from RiskGovernor (structural sizing)
    try:
        from engine.risk.risk_governor import RiskGovernor
        rg = RiskGovernor()
        out = rg.compute_caps_and_sizing(
            current_equity=100000.0,
            peak_equity=100000.0,
            current_open_positions=0,
            trades_today=0,
            consecutive_losses=0,
        )
        print("RG CAPS:", out.get("caps"))
        print("RG SIZING:", out.get("sizing"))
    except Exception as e:
        print("RG sizing call failed:", type(e).__name__, str(e))


def main() -> None:
    _run_fx_smoke()
    _run_futures_smoke_default_fx_adapter_should_block()
    _run_futures_smoke_futures_adapter_mapped()


if __name__ == "__main__":
    main()

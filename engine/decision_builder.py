"""
Decision Builder – Gate Aggregation
===================================

Creates a single authoritative ExecutionDecision by:
- Running configured gates
- Normalizing diverse return formats into GateResult
- Building the ExecutionDecision envelope

Design:
- Safe default: any exception in a gate => BLOCK
- Adapter-agnostic: caller supplies snapshots required by gates
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from engine.execution_decision import GateResult, build_execution_decision, ExecutionDecision


# -------------------------
# helpers (normalization)
# -------------------------

def _to_text(x: Any) -> str:
    try:
        return str(x)
    except Exception:
        return "<unprintable>"


def normalize_gate_output(gate_name: str, raw: Any) -> GateResult:
    """
    Normalize a gate's return output into GateResult.

    Supports:
    - dict with keys: decision/reason
    - tuple/list: (decision, reason) or (decision,)
    - object with attrs: decision, reason
    - string: "ALLOW"/"BLOCK"/"WARN"
    """

    # dict
    if isinstance(raw, dict):
        decision = _to_text(raw.get("decision", "BLOCK")).upper()
        reason = _to_text(raw.get("reason", f"{gate_name}_NO_REASON"))
        return GateResult(gate_name=gate_name, decision=decision, reason=reason)

    # tuple / list
    if isinstance(raw, (tuple, list)) and len(raw) >= 1:
        decision = _to_text(raw[0]).upper()
        reason = _to_text(raw[1]) if len(raw) >= 2 else f"{gate_name}_NO_REASON"
        return GateResult(gate_name=gate_name, decision=decision, reason=reason)

    # object with attributes
    if hasattr(raw, "decision"):
        decision = _to_text(getattr(raw, "decision", "BLOCK")).upper()
        reason = _to_text(getattr(raw, "reason", f"{gate_name}_NO_REASON"))
        return GateResult(gate_name=gate_name, decision=decision, reason=reason)

    # plain string / fallback
    s = _to_text(raw).upper().strip()
    if s in ("ALLOW", "BLOCK", "WARN"):
        return GateResult(gate_name=gate_name, decision=s, reason=f"{gate_name}_{s}")

    return GateResult(gate_name=gate_name, decision="BLOCK", reason=f"{gate_name}_UNRECOGNIZED_OUTPUT")


# -------------------------
# decision builder config
# -------------------------

@dataclass
class GateInputs:
    """
    Inputs container. Keep it generic so adapters can feed it.

    You will pass what you have available; missing required data
    should make the specific gate BLOCK safely.

    Phase 2A:
    - state is introduced to carry adapter identity and capability metadata
      (used by BrokerCapabilityGate and future multi-asset routing).
    """
    instrument: str
    snapshot: Dict[str, Any]                          # price/ohlc/vwap/etc
    volatility: Optional[Dict[str, Any]] = None       # atr, stdev, vix_proxy, baseline
    liquidity: Optional[Dict[str, Any]] = None        # spread, depth, volume proxies
    slippage: Optional[Dict[str, Any]] = None         # expected vs max slippage
    risk: Optional[Dict[str, Any]] = None             # equity, risk_pct, limits, streaks
    state: Optional[Dict[str, Any]] = None            # adapter metadata + general context


def _ensure_state_defaults(inputs: GateInputs) -> None:
    """
    Ensure inputs.state exists and has minimum adapter metadata defaults.
    This keeps Phase 1 behavior intact while enabling Phase 2A capability gating.
    """
    if inputs.state is None or not isinstance(inputs.state, dict):
        inputs.state = {}

    # Default identity (until broker adapters set explicit identity)
    inputs.state.setdefault("adapter_name", "default_fx_adapter")
    inputs.state.setdefault("adapter_capabilities", {"fx": True, "futures": False})
    inputs.state.setdefault("asset_class", "fx")


def build_trade_execution_decision(
    *,
    engine_run_id: str,
    mode: str,
    inputs: GateInputs,
    override_used: bool = False,
    override_reason: Optional[str] = None,
    gates: Optional[Dict[str, Any]] = None,
) -> ExecutionDecision:
    """
    Run configured gates and build a single ExecutionDecision.

    `gates` is a mapping:
      gate_name -> callable(inputs)->any gate output

    If gates is None, returns BLOCK (fail-closed).
    """

    # Phase 2A: always ensure state defaults exist before gates execute
    _ensure_state_defaults(inputs)

    if not gates:
        gate_results = {
            "decision_builder": GateResult(
                gate_name="decision_builder",
                decision="BLOCK",
                reason="NO_GATES_CONFIGURED",
            )
        }
        return build_execution_decision(
            engine_run_id=engine_run_id,
            gate_results=gate_results,
            mode=mode,
            override_used=override_used,
            override_reason=override_reason,
        )

    gate_results: Dict[str, GateResult] = {}

    for gate_name, fn in gates.items():
        try:
            raw = fn(inputs)
            gate_results[gate_name] = normalize_gate_output(gate_name, raw)
        except Exception as e:
            gate_results[gate_name] = GateResult(
                gate_name=gate_name,
                decision="BLOCK",
                reason=f"EXCEPTION: {type(e).__name__}: {_to_text(e)}",
            )

    return build_execution_decision(
        engine_run_id=engine_run_id,
        gate_results=gate_results,
        mode=mode,
        override_used=override_used,
        override_reason=override_reason,
    )

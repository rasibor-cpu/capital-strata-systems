"""
Gates Registry – REA Capital Trading Engine
===========================================

Purpose:
- Provide a single place to wire all gates into the Decision Builder.
- Fail-closed: missing gate module or runtime exception => BLOCK.
- Keep signatures adapter-agnostic by using GateInputs.

This file intentionally uses conservative import patterns so we don't
break the engine during refactors or partial module availability.

Integration rule:
- decision_builder calls each gate as: gate_fn(inputs: GateInputs) -> Any
- normalization happens upstream in decision_builder.normalize_gate_output(...)
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from engine.decision_builder import GateInputs


GateFn = Callable[[GateInputs], Any]


# -------------------------
# Safe wrappers
# -------------------------

def _block(gate_name: str, reason: str) -> Dict[str, str]:
    return {"decision": "BLOCK", "reason": f"{gate_name}: {reason}"}


def _allow(gate_name: str, reason: str = "OK") -> Dict[str, str]:
    return {"decision": "ALLOW", "reason": f"{gate_name}: {reason}"}


def _wrap_imported_gate(gate_name: str, fn: Any) -> GateFn:
    """
    Wrap an imported gate function/object into GateFn(inputs)->Any.

    We try common patterns:
    - callable(inputs) directly
    - callable(snapshot=..., instrument=..., volatility=..., liquidity=..., slippage=..., risk=...)
    """
    if not callable(fn):
        def _not_callable(_: GateInputs) -> Dict[str, str]:
            return _block(gate_name, "Imported gate is not callable")
        return _not_callable

    def _gate(inputs: GateInputs) -> Any:
        # Try direct call first
        try:
            return fn(inputs)
        except TypeError:
            # Try keyword-based call (common across our gates)
            try:
                return fn(
                    instrument=inputs.instrument,
                    snapshot=inputs.snapshot,
                    volatility=inputs.volatility,
                    liquidity=inputs.liquidity,
                    slippage=inputs.slippage,
                    risk=inputs.risk,
                )
            except TypeError:
                # Try minimal call variants
                try:
                    return fn(instrument=inputs.instrument, snapshot=inputs.snapshot)
                except TypeError:
                    return _block(
                        gate_name,
                        "Signature mismatch (expected inputs or common kwargs)",
                    )

    return _gate


# -------------------------
# Gate loaders (fail-closed)
# -------------------------

def _load_regime_gate() -> GateFn:
    gate_name = "regime_gate"
    try:
        # Adjust these imports to match your actual module paths if different
        from engine.regime.regime_gate import evaluate_regime as _fn  # type: ignore
        return _wrap_imported_gate(gate_name, _fn)
    except Exception as e:
        def _missing(_: GateInputs) -> Dict[str, str]:
            return _block(gate_name, f"NOT_AVAILABLE: {type(e).__name__}: {e}")
        return _missing


def _load_volatility_gate() -> GateFn:
    gate_name = "volatility_gate"
    try:
        from engine.volatility.volatility_gate import evaluate_volatility as _fn  # type: ignore
        return _wrap_imported_gate(gate_name, _fn)
    except Exception as e:
        def _missing(_: GateInputs) -> Dict[str, str]:
            return _block(gate_name, f"NOT_AVAILABLE: {type(e).__name__}: {e}")
        return _missing


def _load_liquidity_gate() -> GateFn:
    gate_name = "liquidity_gate"
    try:
        from engine.liquidity.liquidity_gate import evaluate_liquidity as _fn  # type: ignore
        return _wrap_imported_gate(gate_name, _fn)
    except Exception as e:
        def _missing(_: GateInputs) -> Dict[str, str]:
            return _block(gate_name, f"NOT_AVAILABLE: {type(e).__name__}: {e}")
        return _missing


def _load_slippage_guard() -> GateFn:
    gate_name = "slippage_guard"
    try:
        from engine.slippage.slippage_guard import evaluate_slippage as _fn  # type: ignore
        return _wrap_imported_gate(gate_name, _fn)
    except Exception as e:
        def _missing(_: GateInputs) -> Dict[str, str]:
            return _block(gate_name, f"NOT_AVAILABLE: {type(e).__name__}: {e}")
        return _missing


def _load_risk_guard() -> GateFn:
    gate_name = "risk_guard"
    try:
        from engine.risk.risk_guard import evaluate_risk as _fn  # type: ignore
        return _wrap_imported_gate(gate_name, _fn)
    except Exception as e:
        def _missing(_: GateInputs) -> Dict[str, str]:
            return _block(gate_name, f"NOT_AVAILABLE: {type(e).__name__}: {e}")
        return _missing


# -------------------------
# Public API
# -------------------------

def get_configured_gates() -> Dict[str, GateFn]:
    """
    Returns the authoritative gates mapping for Decision Builder.

    Order matters for readability (first blocker becomes primary_reason).
    """
    return {
        "regime_gate": _load_regime_gate(),
        "volatility_gate": _load_volatility_gate(),
        "liquidity_gate": _load_liquidity_gate(),
        "slippage_guard": _load_slippage_guard(),
        "risk_guard": _load_risk_guard(),
    }

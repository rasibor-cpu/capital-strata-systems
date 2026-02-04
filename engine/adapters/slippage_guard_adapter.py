"""
Slippage Guard Adapter
=====================

Purpose:
- Prevent execution when expected slippage is too high
- Normalize slippage signals into ALLOW / WARN / BLOCK
- Fail-closed on missing or malformed inputs

Expected slippage inputs (dict):
- expected (price units)
- max_allowed (price units)
- OR expected_bps / max_allowed_bps
"""

from __future__ import annotations

from typing import Dict, Any

from engine.decision_builder import GateInputs


def evaluate_slippage(inputs: GateInputs) -> Dict[str, str]:
    try:
        slip = inputs.slippage
        if not isinstance(slip, dict):
            return _block("slippage_guard: missing slippage dict")

        # ------------------------------------------------------------
        # Preferred: basis points
        # ------------------------------------------------------------
        expected_bps = slip.get("expected_bps")
        max_bps = slip.get("max_allowed_bps")
        if isinstance(expected_bps, (int, float)) and isinstance(max_bps, (int, float)):
            if expected_bps > max_bps:
                return _block(
                    f"slippage_guard: expected {expected_bps:.2f} bps > max {max_bps:.2f} bps"
                )
            if expected_bps > 0.75 * max_bps:
                return _warn(
                    f"slippage_guard: high slippage {expected_bps:.2f} / {max_bps:.2f} bps"
                )
            return _allow("ok")

        # ------------------------------------------------------------
        # Fallback: raw price units
        # ------------------------------------------------------------
        expected = slip.get("expected")
        max_allowed = slip.get("max_allowed")
        if isinstance(expected, (int, float)) and isinstance(max_allowed, (int, float)):
            if expected > max_allowed:
                return _block(
                    f"slippage_guard: expected {expected:.6f} > max {max_allowed:.6f}"
                )
            if expected > 0.75 * max_allowed:
                return _warn(
                    f"slippage_guard: high slippage {expected:.6f} / {max_allowed:.6f}"
                )
            return _allow("ok")

        return _block("slippage_guard: insufficient slippage data")

    except Exception as e:
        return _block(f"slippage_guard: EXCEPTION {type(e).__name__}: {e}")


# -------------------------------------------------------------------
# helpers
# -------------------------------------------------------------------

def _allow(reason: str) -> Dict[str, str]:
    return {"decision": "ALLOW", "reason": reason}


def _warn(reason: str) -> Dict[str, str]:
    return {"decision": "WARN", "reason": reason}


def _block(reason: str) -> Dict[str, str]:
    return {"decision": "BLOCK", "reason": reason}

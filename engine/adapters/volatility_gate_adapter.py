"""
Volatility Gate Adapter
======================

Purpose:
- Enforce volatility-based execution safety
- Normalize volatility signals into ALLOW / WARN / BLOCK
- Fail-closed on missing or malformed data

Accepted volatility inputs (dict):
- Preferred: vol_norm_0_1 (float, 0.0–1.0)
- Alternative: ratio (current / baseline)
- Fallback: current + baseline
"""

from __future__ import annotations

from typing import Dict, Any

from engine.decision_builder import GateInputs


def evaluate_volatility(inputs: GateInputs) -> Dict[str, str]:
    try:
        vol = inputs.volatility
        if not isinstance(vol, dict):
            return _block("volatility_gate: missing volatility dict")

        # ------------------------------------------------------------
        # Preferred: normalized volatility in range 0..1
        # ------------------------------------------------------------
        vnorm = vol.get("vol_norm_0_1")
        if isinstance(vnorm, (int, float)):
            v = float(vnorm)
            if v >= 0.85:
                return _block(f"volatility_gate: extreme volatility (norm={v:.2f})")
            if v >= 0.65:
                return _warn(f"volatility_gate: elevated volatility (norm={v:.2f})")
            return _allow("ok")

        # ------------------------------------------------------------
        # Fallback: explicit ratio
        # ------------------------------------------------------------
        ratio = vol.get("ratio")
        if isinstance(ratio, (int, float)):
            r = float(ratio)
            if r >= 3.0:
                return _block(f"volatility_gate: volatility spike ({r:.2f}x baseline)")
            if r >= 2.0:
                return _warn(f"volatility_gate: elevated volatility ({r:.2f}x baseline)")
            return _allow("ok")

        # ------------------------------------------------------------
        # Fallback: compute ratio from current / baseline
        # ------------------------------------------------------------
        current = vol.get("current")
        baseline = vol.get("baseline")
        if isinstance(current, (int, float)) and isinstance(baseline, (int, float)) and baseline > 0:
            r = float(current) / float(baseline)
            if r >= 3.0:
                return _block(f"volatility_gate: volatility spike ({r:.2f}x baseline)")
            if r >= 2.0:
                return _warn(f"volatility_gate: elevated volatility ({r:.2f}x baseline)")
            return _allow("ok")

        return _block("volatility_gate: insufficient volatility data")

    except Exception as e:
        return _block(f"volatility_gate: EXCEPTION {type(e).__name__}: {e}")


# -------------------------------------------------------------------
# helpers
# -------------------------------------------------------------------

def _allow(reason: str) -> Dict[str, str]:
    return {"decision": "ALLOW", "reason": reason}


def _warn(reason: str) -> Dict[str, str]:
    return {"decision": "WARN", "reason": reason}


def _block(reason: str) -> Dict[str, str]:
    return {"decision": "BLOCK", "reason": reason}

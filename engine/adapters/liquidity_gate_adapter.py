"""
Liquidity Gate Adapter
======================

Purpose:
- Block execution in illiquid or unstable market conditions
- Enforce spread, depth, and book quality constraints
- Normalize liquidity signals into ALLOW / WARN / BLOCK

Expected liquidity inputs (dict):
- spread_bps (preferred)
- OR spread + price / mid_price
- Optional: depth, book_ok, liquidity_score
"""

from __future__ import annotations

from typing import Dict, Any

from engine.decision_builder import GateInputs


def evaluate_liquidity(inputs: GateInputs) -> Dict[str, str]:
    try:
        liq = inputs.liquidity
        if not isinstance(liq, dict):
            return _block("liquidity_gate: missing liquidity dict")

        # ------------------------------------------------------------
        # Spread checks (preferred: basis points)
        # ------------------------------------------------------------
        spread_bps = _extract_spread_bps(liq, inputs.snapshot)
        if spread_bps is not None:
            if spread_bps >= 5.0:
                return _block(f"liquidity_gate: spread too wide ({spread_bps:.2f} bps)")
            if spread_bps >= 3.0:
                return _warn(f"liquidity_gate: elevated spread ({spread_bps:.2f} bps)")

        # ------------------------------------------------------------
        # Depth / book quality checks
        # ------------------------------------------------------------
        depth = liq.get("depth")
        if isinstance(depth, (int, float)):
            if depth <= 0:
                return _block("liquidity_gate: no market depth")
            if depth < 1:
                return _warn("liquidity_gate: shallow market depth")

        book_ok = liq.get("book_ok")
        if isinstance(book_ok, bool) and not book_ok:
            return _block("liquidity_gate: order book unstable")

        score = liq.get("liquidity_score")
        if isinstance(score, (int, float)):
            if score < 0.3:
                return _block(f"liquidity_gate: low liquidity score ({score:.2f})")
            if score < 0.5:
                return _warn(f"liquidity_gate: marginal liquidity ({score:.2f})")

        return _allow("ok")

    except Exception as e:
        return _block(f"liquidity_gate: EXCEPTION {type(e).__name__}: {e}")


# -------------------------------------------------------------------
# helpers
# -------------------------------------------------------------------

def _extract_spread_bps(liq: Dict[str, Any], snapshot: Any) -> float | None:
    # Preferred
    v = liq.get("spread_bps")
    if isinstance(v, (int, float)):
        return float(v)

    # Fallback: compute from price spread
    spread = liq.get("spread")
    if not isinstance(spread, (int, float)):
        return None

    mid = liq.get("mid") or liq.get("price")
    if not isinstance(mid, (int, float)) and isinstance(snapshot, dict):
        mid = snapshot.get("price") or snapshot.get("mid")

    if isinstance(mid, (int, float)) and mid > 0:
        return (float(spread) / float(mid)) * 10000.0

    return None


def _allow(reason: str) -> Dict[str, str]:
    return {"decision": "ALLOW", "reason": reason}


def _warn(reason: str) -> Dict[str, str]:
    return {"decision": "WARN", "reason": reason}


def _block(reason: str) -> Dict[str, str]:
    return {"decision": "BLOCK", "reason": reason}

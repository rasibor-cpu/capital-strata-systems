"""
Risk Guard Adapter
==================

Purpose:
- Enforce portfolio and trade-level risk constraints
- Prevent drawdown blowups and loss spirals
- Normalize risk signals into ALLOW / WARN / BLOCK
- Fail-closed on missing or malformed inputs

Expected risk inputs (dict):
- equity (required)
- risk_pct (required, % of equity per trade)
- drawdown_pct (optional)
- max_drawdown_pct (optional)
- loss_streak (optional)
- max_loss_streak (optional)
- daily_loss_pct (optional)
- max_daily_loss_pct (optional)
"""

from __future__ import annotations

from typing import Dict, Any

from engine.decision_builder import GateInputs


def evaluate_risk(inputs: GateInputs) -> Dict[str, str]:
    try:
        risk = inputs.risk
        if not isinstance(risk, dict):
            return _block("risk_guard: missing risk dict")

        # ------------------------------------------------------------
        # REQUIRED
        # ------------------------------------------------------------
        equity = risk.get("equity")
        risk_pct = risk.get("risk_pct")

        if not isinstance(equity, (int, float)) or equity <= 0:
            return _block("risk_guard: invalid or missing equity")

        if not isinstance(risk_pct, (int, float)) or risk_pct <= 0:
            return _block("risk_guard: invalid or missing risk_pct")

        # Hard cap per-trade risk (institutional sanity)
        if risk_pct > 20:
            return _block(f"risk_guard: per-trade risk too high ({risk_pct:.2f}%)")

        if risk_pct > 10:
            return _warn(f"risk_guard: elevated per-trade risk ({risk_pct:.2f}%)")

        # ------------------------------------------------------------
        # Drawdown protection
        # ------------------------------------------------------------
        drawdown = risk.get("drawdown_pct")
        max_dd = risk.get("max_drawdown_pct")

        if isinstance(drawdown, (int, float)) and isinstance(max_dd, (int, float)):
            if drawdown >= max_dd:
                return _block(
                    f"risk_guard: max drawdown breached ({drawdown:.2f}% / {max_dd:.2f}%)"
                )
            if drawdown >= 0.75 * max_dd:
                return _warn(
                    f"risk_guard: approaching drawdown limit ({drawdown:.2f}% / {max_dd:.2f}%)"
                )

        # ------------------------------------------------------------
        # Loss streak protection
        # ------------------------------------------------------------
        loss_streak = risk.get("loss_streak")
        max_streak = risk.get("max_loss_streak")

        if isinstance(loss_streak, int) and isinstance(max_streak, int):
            if loss_streak >= max_streak:
                return _block(
                    f"risk_guard: loss streak limit reached ({loss_streak}/{max_streak})"
                )
            if loss_streak >= max_streak - 1:
                return _warn(
                    f"risk_guard: near loss streak limit ({loss_streak}/{max_streak})"
                )

        # ------------------------------------------------------------
        # Daily loss cap
        # ------------------------------------------------------------
        daily_loss = risk.get("daily_loss_pct")
        max_daily = risk.get("max_daily_loss_pct")

        if isinstance(daily_loss, (int, float)) and isinstance(max_daily, (int, float)):
            if daily_loss >= max_daily:
                return _block(
                    f"risk_guard: daily loss cap hit ({daily_loss:.2f}% / {max_daily:.2f}%)"
                )
            if daily_loss >= 0.75 * max_daily:
                return _warn(
                    f"risk_guard: approaching daily loss cap ({daily_loss:.2f}% / {max_daily:.2f}%)"
                )

        return _allow("ok")

    except Exception as e:
        return _block(f"risk_guard: EXCEPTION {type(e).__name__}: {e}")


# -------------------------------------------------------------------
# helpers
# -------------------------------------------------------------------

def _allow(reason: str) -> Dict[str, str]:
    return {"decision": "ALLOW", "reason": reason}


def _warn(reason: str) -> Dict[str, str]:
    return {"decision": "WARN", "reason": reason}


def _block(reason: str) -> Dict[str, str]:
    return {"decision": "BLOCK", "reason": reason}

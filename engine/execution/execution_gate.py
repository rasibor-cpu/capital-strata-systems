"""
Execution Gate – Canonical Flat Interface
Capital Strata Systems

Flat interface for EngineLoop compatibility.
Fail-closed with structured debug.

NEW (v): Weekly Rebalance enforcement (dynamic drift):
- If Friday 17:00 ET window AND drift threshold exceeded => BLOCK new trades.
- Does NOT mutate capital mid-session. Enforcement only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from engine.capital.compounding_engine import CompoundingEngine
from engine.risk.drawdown_scaler import DrawdownScaler
from engine.risk.risk_governor import RiskGovernor
from engine.capital.weekly_rebalance_engine import WeeklyRebalanceEngine

HARD_DRAWDOWN_CIRCUIT_BREAKER_PCT = 0.20


def _safe_str(x: Any) -> str:
    try:
        return str(x)
    except Exception:
        return "<unprintable>"


def _call_any(obj: Any, names: list[str], *args: Any, **kwargs: Any) -> Any:
    """
    Try calling obj.<name>(*args, **kwargs) across multiple possible method names.
    Returns (called, value, used_name).
    """
    for n in names:
        fn = getattr(obj, n, None)
        if callable(fn):
            return True, fn(*args, **kwargs), n
    return False, None, ""


class ExecutionGate:
    def __init__(self) -> None:
        self.risk_governor = RiskGovernor()
        self.compounding = CompoundingEngine()
        self.drawdown_scaler = DrawdownScaler()

        # Rebalance engine is instantiated lazily per call because targets
        # may come from session config/context.
        self._rebalance_engine: Optional[WeeklyRebalanceEngine] = None

    def _rebalance_check(
        self,
        *,
        now_utc: datetime,
        current_allocations: Optional[Dict[str, float]],
        target_weights: Optional[Dict[str, float]],
        volatility_state: str,
        regime_state: str,
        debug: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Returns a BLOCK decision dict or None if not blocking.
        """
        if not target_weights:
            debug["rebalance"] = {"skipped": True, "reason": "no_target_weights"}
            return None

        if self._rebalance_engine is None or getattr(self._rebalance_engine, "target_weights", None) != target_weights:
            self._rebalance_engine = WeeklyRebalanceEngine(target_weights=target_weights, base_threshold=0.05)

        res = self._rebalance_engine.evaluate(
            now_utc=now_utc,
            current_allocations=current_allocations or {},
            volatility_state=volatility_state,
            regime_state=regime_state,
        )

        debug["rebalance"] = {
            "should_rebalance": res.should_rebalance,
            "reason": res.reason,
            "effective_threshold": res.effective_threshold,
            "drift": res.drift_snapshot,
            "volatility_state": volatility_state,
            "regime_state": regime_state,
        }

        if res.should_rebalance:
            return {
                "decision": {"final": "BLOCK"},
                "reason": "weekly_rebalance_window_active",
                "debug": debug,
            }

        return None

    def evaluate_trade(
        self,
        *,
        instrument: str,
        side: str,
        notional: float,
        stop_distance_pct: float,
        equity: float,
        equity_peak: float,
        regime_persistence: float,
        policy: str = "core",
        # -----------------------------
        # NEW (optional, default-safe):
        # -----------------------------
        current_allocations: Optional[Dict[str, float]] = None,
        rebalance_target_weights: Optional[Dict[str, float]] = None,
        volatility_state: str = "MEDIUM",
        regime_state: str = "NORMAL",
    ) -> Dict[str, Any]:

        debug: Dict[str, Any] = {
            "instrument": instrument,
            "side": side,
            "policy": policy,
        }

        try:
            # -------------------------
            # Basic validation
            # -------------------------
            if notional <= 0:
                return {"decision": {"final": "BLOCK"}, "reason": "notional_invalid", "debug": debug}

            if stop_distance_pct <= 0:
                return {"decision": {"final": "BLOCK"}, "reason": "stop_distance_invalid", "debug": debug}

            if equity <= 0:
                return {"decision": {"final": "BLOCK"}, "reason": "equity_invalid", "debug": debug}

            # -------------------------
            # Hard circuit breaker (20%)
            # -------------------------
            if equity_peak and equity_peak > 0:
                dd_pct = (equity_peak - equity) / equity_peak
                debug["drawdown_pct"] = dd_pct
                if dd_pct >= HARD_DRAWDOWN_CIRCUIT_BREAKER_PCT:
                    return {
                        "decision": {"final": "BLOCK"},
                        "reason": "hard_drawdown_circuit_breaker",
                        "debug": debug,
                    }

            # -------------------------
            # Weekly rebalance enforcement (BLOCK new trades)
            # -------------------------
            now_utc = datetime.utcnow()
            block = self._rebalance_check(
                now_utc=now_utc,
                current_allocations=current_allocations,
                target_weights=rebalance_target_weights,
                volatility_state=volatility_state,
                regime_state=regime_state,
                debug=debug,
            )
            if block is not None:
                return block

            # -------------------------
            # Compounding (dynamic risk)
            # -------------------------
            called, dyn_risk, used = _call_any(
                self.compounding,
                ["compute_dynamic_risk", "dynamic_risk", "compute_risk_pct"],
                equity=equity,
                regime_persistence=regime_persistence,
                policy=policy,
            )
            if not called:
                # If compounding method changes across builds, fail-closed.
                return {
                    "decision": {"final": "BLOCK"},
                    "reason": "compounding_api_missing",
                    "debug": {**debug, "compounding_error": "no_supported_method"},
                }

            debug["compounding_method"] = used
            debug["dynamic_risk_pct"] = float(dyn_risk)

            # -------------------------
            # Drawdown scaling
            # -------------------------
            scaled_notional = notional
            dd_called, scaled_val, dd_used = _call_any(
                self.drawdown_scaler,
                ["scale_notional", "scale_trade", "scale"],
                notional=notional,
                equity=equity,
                equity_peak=equity_peak,
                policy=policy,
            )
            if dd_called and scaled_val is not None:
                scaled_notional = float(scaled_val)
                debug["drawdown_scale_method"] = dd_used
                debug["scaled_notional"] = scaled_notional
            else:
                # If scaler API differs, we allow pass-through but log it.
                debug["drawdown_scale_method"] = "pass_through"

            # -------------------------
            # RiskGovernor validation (adapter-safe)
            # -------------------------
            trade = {
                "instrument": instrument,
                "side": side,
                "notional": scaled_notional,
                "stop_distance_pct": stop_distance_pct,
                "equity": equity,
                "equity_peak": equity_peak,
                "policy": policy,
                "dynamic_risk_pct": float(dyn_risk),
                "regime_persistence": regime_persistence,
                "regime_state": regime_state,
                "volatility_state": volatility_state,
            }

            rg_called, rg_res, rg_used = _call_any(
                self.risk_governor,
                ["evaluate_trade", "evaluate", "decide", "check"],
                trade=trade,
                policy=policy,
            )
            debug["risk_governor_method"] = rg_used if rg_called else "missing"

            if not rg_called:
                return {
                    "decision": {"final": "BLOCK"},
                    "reason": "risk_governor_api_missing",
                    "debug": {**debug, "risk_governor_error": "no_supported_method"},
                }

            # Normalize RiskGovernor response
            ok = True
            reason = "approved"

            if isinstance(rg_res, dict):
                # common patterns
                if "ok" in rg_res:
                    ok = bool(rg_res.get("ok"))
                    reason = rg_res.get("reason", reason)
                elif "decision" in rg_res and isinstance(rg_res["decision"], dict):
                    # if governor returns a decision envelope
                    final = rg_res["decision"].get("final")
                    ok = (final == "ALLOW")
                    reason = rg_res.get("reason", reason)
                else:
                    # default allow unless explicitly says block
                    ok = bool(rg_res.get("allow", True))
                    reason = rg_res.get("reason", reason)
            else:
                # object w/ attributes
                ok = bool(getattr(rg_res, "ok", True))
                reason = getattr(rg_res, "reason", reason)

            debug["risk_governor_ok"] = ok
            debug["risk_governor_reason"] = _safe_str(reason)

            if not ok:
                return {"decision": {"final": "BLOCK"}, "reason": "risk_governor_block", "debug": debug}

            return {"decision": {"final": "ALLOW"}, "reason": "approved", "debug": debug}

        except Exception as e:
            return {
                "decision": {"final": "BLOCK"},
                "reason": "execution_gate_exception",
                "debug": {**debug, "exception": _safe_str(e)},
            }

"""
Execution Gate – Canonical Flat Interface
Capital Strata Systems

Flat interface for EngineLoop compatibility.
Fail-closed with structured debug.

Weekly Rebalance enforcement (dynamic drift):
- If Friday 17:00 ET window AND drift threshold exceeded => BLOCK new trades.
- Does NOT mutate capital mid-session. Enforcement only.

Compatibility:
- Compounding / scaler / governor APIs may vary across builds.
- We retry on TypeError with reduced kwargs (institution-safe).
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


def _call_any_adaptive(obj: Any, names: list[str], kwargs_variants: list[Dict[str, Any]]) -> tuple[bool, Any, str, str]:
    """
    Try method names, and for each, try multiple kwargs variants.
    Returns (called, value, used_name, used_variant_tag)
    """
    for n in names:
        fn = getattr(obj, n, None)
        if not callable(fn):
            continue
        for variant in kwargs_variants:
            tag = variant.get("_tag", "")
            call_kwargs = {k: v for k, v in variant.items() if k != "_tag"}
            try:
                return True, fn(**call_kwargs), n, tag
            except TypeError:
                continue
    return False, None, "", ""


class ExecutionGate:
    def __init__(self) -> None:
        self.risk_governor = RiskGovernor()
        self.compounding = CompoundingEngine()
        self.drawdown_scaler = DrawdownScaler()
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
            return {"decision": {"final": "BLOCK"}, "reason": "weekly_rebalance_window_active", "debug": debug}

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
        current_allocations: Optional[Dict[str, float]] = None,
        rebalance_target_weights: Optional[Dict[str, float]] = None,
        volatility_state: str = "MEDIUM",
        regime_state: str = "NORMAL",
    ) -> Dict[str, Any]:

        debug: Dict[str, Any] = {"instrument": instrument, "side": side, "policy": policy}

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
                    return {"decision": {"final": "BLOCK"}, "reason": "hard_drawdown_circuit_breaker", "debug": debug}

            # -------------------------
            # Weekly rebalance enforcement
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
            # Compounding (adaptive kwargs)
            # -------------------------
            comp_called, dyn_risk, comp_name, comp_tag = _call_any_adaptive(
                self.compounding,
                ["compute_dynamic_risk", "dynamic_risk", "compute_risk_pct"],
                kwargs_variants=[
                    {"_tag": "full", "equity": equity, "regime_persistence": regime_persistence, "policy": policy},
                    {"_tag": "no_policy", "equity": equity, "regime_persistence": regime_persistence},
                    {"_tag": "equity_only", "equity": equity},
                ],
            )
            if not comp_called:
                return {
                    "decision": {"final": "BLOCK"},
                    "reason": "compounding_api_missing",
                    "debug": {**debug, "compounding_error": "no_supported_signature"},
                }

            debug["compounding_method"] = comp_name
            debug["compounding_sig"] = comp_tag
            debug["dynamic_risk_pct"] = float(dyn_risk)

            # -------------------------
            # Drawdown scaling (best-effort)
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
                debug["drawdown_scale_method"] = "pass_through"

            # -------------------------
            # RiskGovernor validation (adaptive kwargs)
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

            rg_called, rg_res, rg_name, rg_tag = _call_any_adaptive(
                self.risk_governor,
                ["evaluate_trade", "evaluate", "decide", "check"],
                kwargs_variants=[
                    {"_tag": "trade+policy", "trade": trade, "policy": policy},
                    {"_tag": "trade_only", "trade": trade},
                ],
            )
            debug["risk_governor_method"] = rg_name if rg_called else "missing"
            debug["risk_governor_sig"] = rg_tag

            if not rg_called:
                return {
                    "decision": {"final": "BLOCK"},
                    "reason": "risk_governor_api_missing",
                    "debug": {**debug, "risk_governor_error": "no_supported_signature"},
                }

            # Normalize response
            ok = True
            reason = "approved"

            if isinstance(rg_res, dict):
                if "ok" in rg_res:
                    ok = bool(rg_res.get("ok"))
                    reason = rg_res.get("reason", reason)
                elif "decision" in rg_res and isinstance(rg_res["decision"], dict):
                    final = rg_res["decision"].get("final")
                    ok = (final == "ALLOW")
                    reason = rg_res.get("reason", reason)
                else:
                    ok = bool(rg_res.get("allow", True))
                    reason = rg_res.get("reason", reason)
            else:
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

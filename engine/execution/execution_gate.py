from __future__ import annotations

import inspect
import logging
from typing import Any, Dict, Optional


LOGGER = logging.getLogger(__name__)


class ExecutionGate:
    """
    ExecutionGate (institutional-correct, signature-safe)

    Responsibilities:
    - Compute risk_pct from CompoundingEngine
    - Volatility-based notional sizing (VolatilityPositionSizer)  [robust call]
    - Drawdown scaling (DrawdownScaler)
    - Final risk approval via RiskGovernor.validate_trade
    - Return a stable decision dict: {"decision": {"final": "ALLOW/BLOCK"}, "reason": str, "debug": {...}}

    Key fix:
    - VolatilityPositionSizer.size() is called using ONLY kwargs it supports,
      preventing runtime crashes like: unexpected keyword argument 'instrument'
    """

    def __init__(self) -> None:
        # Imports live here to avoid import-order traps during tooling runs
        from engine.capital.compounding_engine import CompoundingEngine
        from engine.risk.drawdown_scaler import DrawdownScaler
        from engine.risk.risk_governor import RiskGovernor
        from engine.risk.volatility_position_sizer import VolatilityPositionSizer

        self.compounding = CompoundingEngine()
        self.drawdown_scaler = DrawdownScaler()
        self.risk_governor = RiskGovernor()
        self.vol_sizer = VolatilityPositionSizer()

    # -----------------------------
    # Safe-call helpers
    # -----------------------------
    @staticmethod
    def _safe_kwargs_call(fn, preferred_kwargs: Dict[str, Any], fallback_args: Optional[list[Any]] = None) -> Any:
        """
        Calls fn with the intersection of preferred_kwargs and fn's signature parameters.
        If that still fails with TypeError, optionally tries positional fallback_args.
        """
        sig = inspect.signature(fn)
        accepted = set(sig.parameters.keys())

        # Build kwargs that function actually accepts
        kw = {k: v for k, v in preferred_kwargs.items() if k in accepted}

        try:
            return fn(**kw)
        except TypeError:
            if fallback_args is not None:
                return fn(*fallback_args)
            raise

    def _vol_size(self, *, instrument: str, base_notional: float, volatility_state: Any, debug: Dict[str, Any]) -> float:
        """
        VolatilityPositionSizer.size() signature differs across iterations.
        We call it in a signature-safe way.

        We intentionally try a rich kwargs set, but only pass what the method accepts.
        """
        fn = self.vol_sizer.size

        preferred = {
            # common names across variants
            "instrument": instrument,
            "inst": instrument,
            "symbol": instrument,

            "base_notional": base_notional,
            "notional": base_notional,

            "volatility_state": volatility_state,
            "vol_state": volatility_state,
            "state": volatility_state,
        }

        # Positional fallback patterns (in decreasing likelihood)
        fallbacks = [
            [instrument, base_notional, volatility_state],
            [instrument, base_notional],
            [base_notional, volatility_state],
            [base_notional],
        ]

        last_err: Optional[Exception] = None
        for fb in fallbacks:
            try:
                sized = self._safe_kwargs_call(fn, preferred, fallback_args=fb)
                return float(sized)
            except Exception as e:
                last_err = e

        debug["vol_size_error"] = str(last_err) if last_err else "unknown"
        LOGGER.warning(
            "ExecutionGate volatility sizing fallback invoked; "
            "instrument=%s base_notional=%s volatility_state=%s error=%s",
            instrument,
            base_notional,
            volatility_state,
            debug["vol_size_error"],
        )
        # If vol sizing fails, be conservative: return base_notional unchanged (don’t crash the engine)
        return float(base_notional)

    def _riskgov_validate(self, *, instrument: str, side: str, requested_notional: float,
                         stop_distance_pct: float, equity: float, risk_pct: float,
                         policy: str, debug: Dict[str, Any]) -> Dict[str, Any]:
        """
        RiskGovernor.validate_trade signature may vary; call safely.
        """
        fn = self.risk_governor.validate_trade

        preferred = {
            "instrument": instrument,
            "side": side,
            "requested_notional": requested_notional,
            "notional": requested_notional,  # some variants use notional
            "stop_distance_pct": stop_distance_pct,
            "equity": equity,
            "risk_pct": risk_pct,
            "policy": policy,
        }

        try:
            out = self._safe_kwargs_call(fn, preferred, fallback_args=None)
            if isinstance(out, dict):
                return out
            # If an object comes back, best-effort normalize
            return {"ok": bool(getattr(out, "ok", False)), "reason": str(getattr(out, "reason", ""))}
        except Exception as e:
            debug["riskgov_error"] = str(e)
            return {"ok": False, "reason": "riskgov_exception"}

    # -----------------------------
    # Public API (matches your signature)
    # -----------------------------
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
        debug: Dict[str, Any] = {}
        try:
            # 1) Compounding layer risk%
            risk_pct = float(
                self.compounding.compute_dynamic_risk(
                    equity=float(equity),
                    equity_peak=float(equity_peak),
                    regime_persistence=float(regime_persistence),
                )
            )
            debug["risk_pct"] = risk_pct

            # 2) Volatility sizing (signature-safe)
            vol_scaled_notional = self._vol_size(
                instrument=instrument,
                base_notional=float(notional),
                volatility_state=volatility_state,
                debug=debug,
            )
            debug["vol_scaled_notional"] = vol_scaled_notional

            # 3) Drawdown scaling
            scaled_notional = float(
                self.drawdown_scaler.scale(
                    notional=float(vol_scaled_notional),
                    equity=float(equity),
                    equity_peak=float(equity_peak),
                    policy=str(policy),
                )
            )
            debug["scaled_notional"] = scaled_notional

            # 4) RiskGovernor final approve/reject
            gov = self._riskgov_validate(
                instrument=instrument,
                side=side,
                requested_notional=scaled_notional,
                stop_distance_pct=float(stop_distance_pct),
                equity=float(equity),
                risk_pct=risk_pct,
                policy=str(policy),
                debug=debug,
            )
            debug["governor_response"] = gov

            if not bool(gov.get("ok", False)):
                return {
                    "decision": {"final": "BLOCK"},
                    "reason": str(gov.get("reason", "governor_reject")),
                    "debug": debug,
                }

            return {
                "decision": {"final": "ALLOW"},
                "reason": "approved",
                "debug": debug,
            }

        except Exception as e:
            return {
                "decision": {"final": "BLOCK"},
                "reason": "execution_gate_exception",
                "debug": {"exception": str(e), **debug},
            }

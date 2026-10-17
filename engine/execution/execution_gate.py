from __future__ import annotations

import inspect
import logging
import math
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

    Volatility sizing:
    - VolatilityPositionSizer.size(notional, price, debug) with the caller's
      `price`, one rolling stream per instrument, reduce-only.
    """

    def __init__(
        self,
        anti_bleed_guard: Optional[Any] = None,
        margin_trade_gate: Optional[Any] = None,
    ) -> None:
        # Imports live here to avoid import-order traps during tooling runs
        from backend.app.risk.anti_bleed_guard import AntiBleedGuard
        from engine.capital.compounding_engine import CompoundingEngine
        from engine.risk.drawdown_scaler import DrawdownScaler
        from engine.risk.margin_trade_gate import MarginTradeGate
        from engine.risk.risk_governor import RiskGovernor
        from engine.risk.volatility_position_sizer import VolatilityPositionSizer

        self.anti_bleed_guard = anti_bleed_guard or AntiBleedGuard()
        self.margin_trade_gate = margin_trade_gate or MarginTradeGate()
        self.compounding = CompoundingEngine()
        self.drawdown_scaler = DrawdownScaler()
        self.risk_governor = RiskGovernor()
        self.vol_sizer = VolatilityPositionSizer()  # policy template; per-instrument state below
        self._vol_sizers: Dict[str, Any] = {}

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

    def _vol_size(self, *, instrument: str, base_notional: float, price: Optional[float], debug: Dict[str, Any]) -> float:
        """
        Volatility sizing via VolatilityPositionSizer.size(notional, price, debug).

        - One sizer (rolling price stream) per instrument, so instruments never mix.
        - Reduce-only: the sizer may return a multiplier above 1.0 in low volatility;
          the gate never applies it (recorded as vol_upsizing_suppressed).
        - Without a usable price the size is left unchanged and the skip is recorded
          explicitly (vol_size_status), never hidden behind a fallback.
        """
        base = float(base_notional)
        try:
            p = float(price) if price is not None else None
        except (TypeError, ValueError):
            p = None
        if p is None or not math.isfinite(p) or p <= 0:
            debug["vol_size_status"] = "skipped:price_unavailable"
            return base
        key = str(instrument or "").strip().upper() or "_UNSPECIFIED"
        sizer = self._vol_sizers.get(key)
        if sizer is None:
            from engine.risk.volatility_position_sizer import VolatilityPositionSizer
            sizer = self._vol_sizers[key] = VolatilityPositionSizer(self.vol_sizer.policy)
        try:
            scaled = float(sizer.size(notional=base, price=p, debug=debug))
        except Exception as exc:  # pragma: no cover - defensive: never enlarge on error
            debug["vol_size_status"] = f"error:{type(exc).__name__}"
            LOGGER.warning("ExecutionGate volatility sizing error; instrument=%s error=%s", instrument, exc)
            return base
        if not math.isfinite(scaled) or scaled < 0:
            debug["vol_size_status"] = "error:non_finite"
            return base
        if scaled > base:
            debug["vol_upsizing_suppressed"] = True
            debug["vol_size_status"] = "applied:capped_at_base"
            return base
        debug["vol_size_status"] = "applied"
        return scaled

    def _riskgov_validate(self, *, instrument: str, side: str, requested_notional: float,
                         stop_distance_pct: float, equity: float, risk_pct: float,
                         policy: str, debug: Dict[str, Any]) -> Dict[str, Any]:
        """
        RiskGovernor.validate_trade signature may vary; call safely.

        This delegates using a precomputed risk_pct after ExecutionGate has
        already applied compounding, volatility sizing, and drawdown scaling.
        """
        fn = self.risk_governor.validate_trade
        debug["riskgov_path"] = "validate_trade_precomputed_risk_pct"

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

    def _evaluate_anti_bleed(
        self,
        *,
        instrument: Any,
        side: Any,
        notional: Any,
        expected_move_bps: Any,
        fee_bps: Any,
        spread_bps: Any,
        slippage_bps: Any,
    ) -> Dict[str, Any]:
        required = {
            "instrument": instrument,
            "side": side,
            "notional": notional,
            "expected_move_bps": expected_move_bps,
            "fee_bps": fee_bps,
            "spread_bps": spread_bps,
            "slippage_bps": slippage_bps,
        }

        for name, value in required.items():
            if value is None:
                return {
                    "approved": False,
                    "reason": f"missing_anti_bleed_input:{name}",
                    "control": "AntiBleedGuard",
                }
            if name in {"instrument", "side"} and not str(value).strip():
                return {
                    "approved": False,
                    "reason": f"missing_anti_bleed_input:{name}",
                    "control": "AntiBleedGuard",
                }

        numeric: Dict[str, float] = {}
        for name in (
            "notional",
            "expected_move_bps",
            "fee_bps",
            "spread_bps",
            "slippage_bps",
        ):
            try:
                number = float(required[name])
            except (TypeError, ValueError):
                return {
                    "approved": False,
                    "reason": f"invalid_anti_bleed_input:{name}",
                    "control": "AntiBleedGuard",
                }

            if not math.isfinite(number):
                return {
                    "approved": False,
                    "reason": f"invalid_anti_bleed_input:{name}",
                    "control": "AntiBleedGuard",
                }

            numeric[name] = number

        if numeric["notional"] <= 0.0:
            return {
                "approved": False,
                "reason": "invalid_anti_bleed_input:notional",
                "control": "AntiBleedGuard",
            }

        for name in ("expected_move_bps", "fee_bps", "spread_bps", "slippage_bps"):
            if numeric[name] < 0.0:
                return {
                    "approved": False,
                    "reason": f"invalid_anti_bleed_input:{name}",
                    "control": "AntiBleedGuard",
                }

        try:
            decision = self.anti_bleed_guard.evaluate(
                symbol=str(instrument),
                side=str(side),
                trade_size=numeric["notional"],
                expected_move_bps=numeric["expected_move_bps"],
                fee_bps=numeric["fee_bps"],
                spread_bps=numeric["spread_bps"],
                slippage_bps=numeric["slippage_bps"],
            )
        except Exception as exc:
            return {
                "approved": False,
                "reason": "anti_bleed_guard_exception",
                "control": "AntiBleedGuard",
                "error": f"{type(exc).__name__}: {exc}",
            }

        if not isinstance(decision, dict):
            return {
                "approved": False,
                "reason": "invalid_anti_bleed_guard_response",
                "control": "AntiBleedGuard",
            }

        decision.setdefault("control", "AntiBleedGuard")
        return decision

    def _evaluate_margin_trade(
        self,
        *,
        margin_snapshot: Any,
        broker_mode: str,
    ) -> Dict[str, Any]:
        if margin_snapshot is None:
            return {
                "allowed": False,
                "decision": "BLOCK",
                "reason": "MARGIN_SNAPSHOT_UNAVAILABLE",
                "control": "MarginTradeGate",
            }

        try:
            decision = self.margin_trade_gate.evaluate(
                margin_snapshot,
                broker_mode=broker_mode,
            )
        except Exception as exc:
            return {
                "allowed": False,
                "decision": "BLOCK",
                "reason": "margin_trade_gate_exception",
                "control": "MarginTradeGate",
                "error": f"{type(exc).__name__}: {exc}",
            }

        return {
            "allowed": bool(getattr(decision, "allowed", False)),
            "decision": str(getattr(decision, "decision", "BLOCK")),
            "reason": str(getattr(decision, "reason", "margin_gate_rejected")),
            "margin_state": str(getattr(decision, "margin_state", "UNKNOWN")),
            "escalation_state": str(getattr(decision, "escalation_state", "UNKNOWN")),
            "margin_utilization_pct": float(getattr(decision, "margin_utilization_pct", 0.0) or 0.0),
            "control": "MarginTradeGate",
        }

    # -----------------------------
    # Public API (matches your signature)
    # -----------------------------
    def evaluate_trade(
        self,
        *,
        instrument: str = "",
        side: Optional[str] = None,
        notional: Optional[float] = None,
        stop_distance_pct: Optional[float] = None,
        equity: Optional[float] = None,
        equity_peak: Optional[float] = None,
        regime_persistence: Optional[float] = None,
        policy: str = "core",
        current_allocations: Optional[Dict[str, float]] = None,
        rebalance_target_weights: Optional[Dict[str, float]] = None,
        volatility_state: str = "MEDIUM",
        regime_state: str = "NORMAL",
        expected_move_bps: Optional[float] = None,
        fee_bps: Optional[float] = None,
        spread_bps: Optional[float] = None,
        slippage_bps: Optional[float] = None,
        margin_snapshot: Optional[Any] = None,
        broker_mode: str = "PAPER",
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        debug: Dict[str, Any] = {}
        try:
            anti_bleed_decision = self._evaluate_anti_bleed(
                instrument=instrument,
                side=side,
                notional=notional,
                expected_move_bps=expected_move_bps,
                fee_bps=fee_bps,
                spread_bps=spread_bps,
                slippage_bps=slippage_bps,
            )
            debug["anti_bleed_guard"] = anti_bleed_decision

            if not bool(anti_bleed_decision.get("approved", False)):
                return {
                    "decision": {"final": "BLOCK"},
                    "reason": f"anti_bleed_guard:{anti_bleed_decision.get('reason', 'rejected')}",
                    "debug": debug,
                }

            margin_decision = self._evaluate_margin_trade(
                margin_snapshot=margin_snapshot,
                broker_mode=broker_mode,
            )
            debug["margin_trade_gate"] = margin_decision

            if not bool(margin_decision.get("allowed", False)):
                return {
                    "decision": {"final": "BLOCK"},
                    "reason": f"margin_trade_gate:{margin_decision.get('decision', 'BLOCK')}:{margin_decision.get('reason', 'rejected')}",
                    "debug": debug,
                }

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
                price=price,
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

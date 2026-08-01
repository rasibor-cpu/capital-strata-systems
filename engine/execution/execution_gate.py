from __future__ import annotations

import inspect
import logging
import math
from typing import Any, Dict, Optional

from engine.risk.canonical_volatility_price import validate_canonical_price_for_volatility
from engine.risk.volatility_position_sizer import VolatilityPriceError


LOGGER = logging.getLogger(__name__)


class ExecutionGate:
    """
    ExecutionGate (institutional-correct, signature-safe)

    Responsibilities:
    - Compute risk_pct from CompoundingEngine
    - Volatility-based notional sizing (VolatilityPositionSizer) with canonical price
    - Drawdown scaling (DrawdownScaler)
    - Final risk approval via RiskGovernor.validate_trade
    - Return a stable decision dict: {"decision": {"final": "ALLOW/BLOCK"}, "reason": str, "debug": {...}}

    MW-003:
    - Volatility sizing requires a validated finite positive canonical price.
    - Missing/invalid/stale/mismatched prices fail closed (no silent base-notional ALLOW).
    """

    def __init__(
        self,
        anti_bleed_guard: Optional[Any] = None,
        margin_trade_gate: Optional[Any] = None,
        anti_bleed_policy_resolver: Optional[Any] = None,
    ) -> None:
        # Imports live here to avoid import-order traps during tooling runs
        from backend.app.risk.anti_bleed_guard import AntiBleedGuard
        from backend.app.risk.anti_bleed_policy import AntiBleedPolicyResolver
        from engine.capital.compounding_engine import CompoundingEngine
        from engine.risk.drawdown_scaler import DrawdownScaler
        from engine.risk.margin_trade_gate import MarginTradeGate
        from engine.risk.risk_governor import RiskGovernor
        from engine.risk.volatility_position_sizer import VolatilityPositionSizer

        self.anti_bleed_guard = anti_bleed_guard or AntiBleedGuard()
        self.anti_bleed_policy_resolver = anti_bleed_policy_resolver or AntiBleedPolicyResolver()
        self.margin_trade_gate = margin_trade_gate or MarginTradeGate()
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

    def _vol_size(
        self,
        *,
        instrument: str,
        base_notional: float,
        price: float,
        volatility_state: Any,
        debug: Dict[str, Any],
    ) -> float:
        """
        Call VolatilityPositionSizer with an already-validated canonical price.

        Missing-price TypeError is not a normal control-flow path: callers must
        validate price before invoking this method.
        """
        del instrument, volatility_state  # retained for call-site compatibility / future variants
        debug["canonical_price"] = float(price)
        sized = self.vol_sizer.size(notional=float(base_notional), price=float(price), debug=debug)
        return float(sized)

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
        price: Optional[Any] = None,
        last_price: Optional[Any] = None,
        reference_price: Optional[Any] = None,
        market_price: Optional[Any] = None,
        mid_price: Optional[Any] = None,
        current_price: Optional[Any] = None,
        price_instrument: Optional[Any] = None,
        price_as_of: Optional[Any] = None,
        price_max_age_seconds: Optional[Any] = None,
        anti_bleed_context: Optional[Any] = None,
        governed_execution_context: Optional[Any] = None,
        market_snapshot: Optional[Any] = None,
        fx_conversion: Optional[Any] = None,
    ) -> Dict[str, Any]:
        debug: Dict[str, Any] = {}
        try:
            # Phase 185A — record market/FX contracts in diagnostics only.
            # Does not reorder gates; missing/unavailable data remains fail-closed.
            debug["market_snapshot"] = self._market_snapshot_debug(market_snapshot)
            debug["fx_conversion"] = self._fx_conversion_debug(fx_conversion)

            # Phase 184A — resolve immutable AntiBleed policy before any evaluation.
            # Selection uses governed execution context only (never broker/account/env).
            context_token = (
                anti_bleed_context
                if anti_bleed_context is not None
                else governed_execution_context
            )
            anti_bleed_policy = self.anti_bleed_policy_resolver.resolve(context_token)
            debug["anti_bleed_policy"] = getattr(anti_bleed_policy, "name", "UNKNOWN")
            debug["policy_id"] = getattr(anti_bleed_policy, "policy_id", "UNKNOWN")
            debug["policy_version"] = getattr(anti_bleed_policy, "policy_version", "UNKNOWN")
            debug["anti_bleed_context"] = context_token

            anti_bleed_decision = self._evaluate_anti_bleed(
                instrument=instrument,
                side=side,
                notional=notional,
                expected_move_bps=expected_move_bps,
                fee_bps=fee_bps,
                spread_bps=spread_bps,
                slippage_bps=slippage_bps,
                anti_bleed_policy=anti_bleed_policy,
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

            canonical_price, price_source, price_reason = validate_canonical_price_for_volatility(
                instrument=str(instrument or ""),
                price=price,
                last_price=last_price,
                reference_price=reference_price,
                market_price=market_price,
                mid_price=mid_price,
                current_price=current_price,
                price_instrument=price_instrument,
                price_as_of=price_as_of,
                price_max_age_seconds=price_max_age_seconds,
            )
            debug["canonical_price_source"] = price_source
            if price_reason is not None or canonical_price is None:
                reason = price_reason or "volatility_price_missing"
                debug["volatility_price_reason"] = reason
                LOGGER.warning(
                    "ExecutionGate volatility price rejected; instrument=%s reason=%s",
                    instrument,
                    reason,
                )
                return {
                    "decision": {"final": "BLOCK"},
                    "reason": reason,
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

            # 2) Volatility sizing with validated canonical price
            try:
                vol_scaled_notional = self._vol_size(
                    instrument=instrument,
                    base_notional=float(notional),
                    price=float(canonical_price),
                    volatility_state=volatility_state,
                    debug=debug,
                )
            except VolatilityPriceError as exc:
                debug["volatility_price_reason"] = str(exc) or "volatility_price_invalid"
                return {
                    "decision": {"final": "BLOCK"},
                    "reason": "volatility_price_invalid",
                    "debug": debug,
                }
            debug["vol_scaled_notional"] = vol_scaled_notional
            debug["base_notional"] = float(notional)

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

        except Exception as exc:
            LOGGER.exception("ExecutionGate.evaluate_trade failed")
            return {
                "decision": {"final": "BLOCK"},
                "reason": f"execution_gate_exception:{type(exc).__name__}",
                "debug": {**debug, "error": f"{type(exc).__name__}: {exc}"},
            }

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
        anti_bleed_policy: Any = None,
    ) -> Dict[str, Any]:
        # Phase 184A: resolved policy is passed into AntiBleedGuard.evaluate.
        # Microstructure completeness remains fail-closed for all profiles.
        resolved_policy = anti_bleed_policy

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
                policy=resolved_policy,
            )
        except TypeError:
            # Recording / legacy test doubles may not accept policy= yet.
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

    @staticmethod
    def _market_snapshot_debug(market_snapshot: Any) -> Dict[str, Any]:
        if market_snapshot is None:
            return {
                "status": "NOT_AVAILABLE",
                "usable": False,
                "source": "absent",
                "schema_id": "LIVE_MARKET_SNAPSHOT",
                "schema_version": "185A.1",
                "provider_name": "UNAVAILABLE_PROVIDER",
                "provider_version": "185A.1",
            }
        identity = getattr(market_snapshot, "identity", None)
        if callable(identity):
            payload = dict(identity())
        else:
            payload = {
                "schema_id": str(getattr(market_snapshot, "schema_id", "LIVE_MARKET_SNAPSHOT")),
                "schema_version": str(getattr(market_snapshot, "schema_version", "185A.1")),
                "provider_name": str(getattr(market_snapshot, "provider", "UNKNOWN")),
                "provider_version": str(getattr(market_snapshot, "provider_version", "UNKNOWN")),
                "provider": str(getattr(market_snapshot, "provider", "UNKNOWN")),
                "quality": str(getattr(market_snapshot, "quality", "UNKNOWN")),
                "freshness": str(getattr(market_snapshot, "freshness", "UNKNOWN")),
                "status": str(getattr(market_snapshot, "status", "UNKNOWN")),
            }
        usable = getattr(market_snapshot, "is_usable", None)
        payload["usable"] = bool(usable()) if callable(usable) else False
        payload["source"] = "provided"
        payload.setdefault("schema_id", "LIVE_MARKET_SNAPSHOT")
        payload.setdefault("schema_version", "185A.1")
        payload.setdefault(
            "provider_name",
            str(payload.get("provider") or getattr(market_snapshot, "provider", "UNKNOWN")),
        )
        payload.setdefault(
            "provider_version",
            str(getattr(market_snapshot, "provider_version", "UNKNOWN")),
        )
        return payload

    @staticmethod
    def _fx_conversion_debug(fx_conversion: Any) -> Dict[str, Any]:
        if fx_conversion is None:
            return {
                "status": "NOT_AVAILABLE",
                "usable": False,
                "source": "absent",
                "schema_id": "FX_CONVERSION",
                "schema_version": "185A.1",
                "provider_name": "UNAVAILABLE_PROVIDER",
                "provider_version": "185A.1",
            }
        identity = getattr(fx_conversion, "identity", None)
        if callable(identity):
            payload = dict(identity())
        else:
            payload = {
                "schema_id": str(getattr(fx_conversion, "schema_id", "FX_CONVERSION")),
                "schema_version": str(getattr(fx_conversion, "schema_version", "185A.1")),
                "base_currency": str(getattr(fx_conversion, "base_currency", "UNKNOWN")),
                "quote_currency": str(getattr(fx_conversion, "quote_currency", "UNKNOWN")),
                "provider_name": str(getattr(fx_conversion, "provider", "UNKNOWN")),
                "provider_version": str(getattr(fx_conversion, "provider_version", "UNKNOWN")),
                "provider": str(getattr(fx_conversion, "provider", "UNKNOWN")),
                "quality": str(getattr(fx_conversion, "quality", "UNKNOWN")),
                "status": str(getattr(fx_conversion, "status", "UNKNOWN")),
            }
        usable = getattr(fx_conversion, "is_usable", None)
        payload["usable"] = bool(usable()) if callable(usable) else False
        payload["source"] = "provided"
        payload.setdefault("schema_id", "FX_CONVERSION")
        payload.setdefault("schema_version", "185A.1")
        payload.setdefault(
            "provider_name",
            str(payload.get("provider") or getattr(fx_conversion, "provider", "UNKNOWN")),
        )
        payload.setdefault(
            "provider_version",
            str(getattr(fx_conversion, "provider_version", "UNKNOWN")),
        )
        # Never include raw rates as authority; rate presence only.
        rate = getattr(fx_conversion, "rate", None)
        payload["rate_present"] = rate is not None
        return payload

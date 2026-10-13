"""Trusted evaluator ownership for governed paper-route simulation (CSS-062).

This module implements the closed allow-list of reviewed gate-evaluator
adapters. Only these named functions may be invoked by the trusted issuer.
Nothing here grants live-execution, broker, or trading authority.

CSS-062 Blocker 4 fixes (fail-closed gate chain):
- Every decision must be an EXPLICIT boolean ``True`` (``is True``), never a
  truthy string/number/None. A truthy non-boolean (e.g. ``"false"``) is a
  DENIAL.
- Kill-switch state is read from the AUTHORITATIVE environment/OS source
  (``os.environ`` / ``CSS_LIVE_ORDER_KILL_SWITCH``), NOT from a
  request-supplied ``env`` mapping. A caller cannot hide an engaged real
  environment kill switch.
- ``TrustedRiskEvaluators`` is a final class; subclass substitution is
  rejected by the trusted authority.

The four evaluated gates (traced to real production code):
- R7                      -> backend/governance/css_unified_trade_gate.CSSUnifiedTradeGate
- AntiBleedGuard           -> backend/app/risk/anti_bleed_guard.AntiBleedGuard
- RiskGovernor             -> engine/risk/risk_governor.RiskGovernor.validate_trade
- Kill switch              -> engine/execution/live_order_kill_switch.evaluate_live_order_kill_switch
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

__all__ = [
    "TrustedRiskEvaluators",
    "TrustedEvaluatorError",
    "TRUSTED_EVALUATOR_IDENTIFIERS",
]


class TrustedEvaluatorError(RuntimeError):
    """Raised when trusted-evaluator construction is invalid. Never a runtime denial."""


TRUSTED_EVALUATOR_IDENTIFIERS: tuple[str, ...] = (
    "r7_unified_trade_gate",
    "antibleed_guard",
    "risk_governor",
    "live_order_kill_switch",
)


def _denial(reason: str) -> dict[str, Any]:
    return {"approved": False, "reason": reason}


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TrustedEvaluatorError(f"order_context must be a Mapping: {name}")
    return value


class TrustedRiskEvaluators:
    """Closed allow-list of four reviewed gate adapters. Mandatory trusted mode.

    This class is FINAL — the trusted authority rejects any subclass that
    overrides ``evaluate_all`` or any evaluate method. Construction happens at
    trusted-application initialization; per-order requests never supply
    evaluators, registry paths, public keys, or the expected candidate SHA.
    """

    __slots__ = ("_r7_gate", "_antibleed_guard", "_risk_governor", "_kill_switch_fn")

    _FINAL = True  # marker checked by the trusted authority

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TrustedEvaluatorError(
            "TrustedRiskEvaluators is final and cannot be subclassed (CSS-062 Blocker 2)"
        )

    def __init__(self) -> None:
        # Import the reviewed adapters once at construction. Any import failure
        # is a hard failure of trusted initialization, NOT a silent denial.
        from backend.app.risk.anti_bleed_guard import AntiBleedGuard
        from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate
        from engine.execution.live_order_kill_switch import (
            evaluate_live_order_kill_switch,
        )
        from engine.risk.risk_governor import RiskGovernor

        self._r7_gate = CSSUnifiedTradeGate()
        self._antibleed_guard = AntiBleedGuard()
        self._risk_governor = RiskGovernor()
        self._kill_switch_fn = evaluate_live_order_kill_switch

    # ---------------------------------------------------------------- R7
    def evaluate_r7(
        self,
        order_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        """R7 PCNRASS Unified Trade Gate. Fail-closed; explicit boolean only."""
        try:
            ctx = _require_mapping(order_context, "r7_order_context")
            candidate = ctx.get("candidate")
            session = ctx.get("session")
            portfolio_state = ctx.get("portfolio_state")
            engine_mode = ctx.get("engine_mode")
            if not isinstance(candidate, Mapping) or not isinstance(session, Mapping):
                return _denial("R7_ORDER_CONTEXT_INCOMPLETE")
            if not isinstance(portfolio_state, Mapping) or not isinstance(engine_mode, str):
                return _denial("R7_ORDER_CONTEXT_INCOMPLETE")
            decision = self._r7_gate.approve_trade(
                candidate=dict(candidate),
                session=dict(session),
                portfolio_state=dict(portfolio_state),
                engine_mode=str(engine_mode),
            )
        except Exception:  # fail closed
            return _denial("R7_EVALUATOR_ERROR")
        approved = getattr(decision, "approved", None)
        reason = getattr(decision, "reason", None)
        # EXPLICIT boolean only. A truthy non-boolean (e.g. "false") is a denial.
        if approved is True:
            return {"approved": True, "reason": str(reason) if reason else "approved"}
        return _denial(str(reason) if reason else "r7_denied")

    # ---------------------------------------------------------- AntiBleed
    def evaluate_antibleed(
        self,
        order_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        """AntiBleedGuard. Fail-closed. Does NOT enable the pilot_min_size_exception."""
        try:
            ctx = _require_mapping(order_context, "antibleed_order_context")
            symbol = ctx.get("symbol")
            trade_size = ctx.get("trade_size")
            expected_move_bps = ctx.get("expected_move_bps")
            fee_bps = ctx.get("fee_bps")
            spread_bps = ctx.get("spread_bps")
            slippage_bps = ctx.get("slippage_bps")
            side = ctx.get("side", "UNKNOWN")
            if not isinstance(symbol, str) or not symbol.strip():
                return _denial("ANTIBLEED_ORDER_CONTEXT_INCOMPLETE")
            for name in ("trade_size", "expected_move_bps", "fee_bps", "spread_bps", "slippage_bps"):
                v = ctx.get(name)
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    return _denial("ANTIBLEED_ORDER_CONTEXT_INCOMPLETE")
                if v != v or v in (float("inf"), float("-inf")):  # NaN / inf check
                    return _denial("ANTIBLEED_NON_FINITE_INPUT")
            # IMPORTANT: pilot_min_size_exception is NEVER set from the request.
            decision = self._antibleed_guard.evaluate(
                symbol=str(symbol),
                trade_size=float(trade_size),
                expected_move_bps=float(expected_move_bps),
                fee_bps=float(fee_bps),
                spread_bps=float(spread_bps),
                slippage_bps=float(slippage_bps),
                side=str(side) if isinstance(side, str) else "UNKNOWN",
                pilot_min_size_exception=None,
            )
        except Exception:
            return _denial("ANTIBLEED_EVALUATOR_ERROR")
        if not isinstance(decision, Mapping):
            return _denial("ANTIBLEED_EVALUATOR_UNEXPECTED_RESULT")
        approved = decision.get("approved", None)
        if approved is True:  # EXPLICIT boolean
            return {"approved": True, "reason": str(decision.get("reason", "approved"))}
        return _denial(str(decision.get("reason", "antibleed_denied")))

    # ------------------------------------------------------- RiskGovernor
    def evaluate_risk_governor(
        self,
        order_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        """RiskGovernor.validate_trade (ExecutionGate compatibility adapter)."""
        try:
            ctx = _require_mapping(order_context, "risk_governor_order_context")
            required = (
                "instrument",
                "side",
                "requested_notional",
                "stop_distance_pct",
                "equity",
                "risk_pct",
            )
            if any(k not in ctx for k in required):
                return _denial("RISK_GOVERNOR_ORDER_CONTEXT_INCOMPLETE")
            for k in ("requested_notional", "stop_distance_pct", "equity", "risk_pct"):
                v = ctx.get(k)
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    return _denial("RISK_GOVERNOR_ORDER_CONTEXT_INCOMPLETE")
                if v != v or v in (float("inf"), float("-inf")):
                    return _denial("RISK_GOVERNOR_NON_FINITE_INPUT")
            decision = self._risk_governor.validate_trade(
                instrument=str(ctx["instrument"]),
                side=str(ctx["side"]),
                requested_notional=float(ctx["requested_notional"]),
                stop_distance_pct=float(ctx["stop_distance_pct"]),
                equity=float(ctx["equity"]),
                risk_pct=float(ctx["risk_pct"]),
            )
        except Exception:
            return _denial("RISK_GOVERNOR_EVALUATOR_ERROR")
        if not isinstance(decision, Mapping):
            return _denial("RISK_GOVERNOR_EVALUATOR_UNEXPECTED_RESULT")
        ok = decision.get("ok", None)
        if ok is True:  # EXPLICIT boolean
            return {"approved": True, "reason": str(decision.get("reason", "approved"))}
        return _denial(str(decision.get("reason", "risk_governor_denied")))

    # --------------------------------------------------------- Kill switch
    def evaluate_kill_switch(
        self,
        order_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Live-order kill switch. Reads the AUTHORITATIVE environment, not request input.

        The kill-switch state comes from ``os.environ`` (the authoritative
        OS environment), NOT from a request-supplied ``env`` mapping. A
        caller cannot hide an engaged real environment kill switch by
        supplying an empty/nonempty ``env``.
        """
        try:
            _require_mapping(order_context, "kill_switch_order_context")
            # Read from the AUTHORITATIVE environment (os.environ).
            decision = self._kill_switch_fn(
                controls=None,
                env=os.environ,  # authoritative, NOT request-supplied
            )
        except Exception:
            return _denial("KILL_SWITCH_EVALUATOR_ERROR")
        blocked = getattr(decision, "blocked", None)
        if blocked is False:  # EXPLICIT boolean
            return {"approved": True, "reason": str(getattr(decision, "reason", "kill_switch_clear"))}
        return _denial(str(getattr(decision, "reason", "kill_switch_engaged")))

    # ---------------------------------------------------- dispatch helper
    def evaluate_gate(
        self,
        identifier: str,
        order_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Dispatch by allow-listed identifier only. Unknown identifier = hard deny."""
        if identifier not in TRUSTED_EVALUATOR_IDENTIFIERS:
            return _denial(f"UNKNOWN_TRUSTED_EVALUATOR:{identifier}")
        method = {
            "r7_unified_trade_gate": self.evaluate_r7,
            "antibleed_guard": self.evaluate_antibleed,
            "risk_governor": self.evaluate_risk_governor,
            "live_order_kill_switch": self.evaluate_kill_switch,
        }[identifier]
        try:
            return method(order_context)
        except Exception:
            # Defensive: no adapter may propagate.
            return _denial(f"TRUSTED_EVALUATOR_ADAPTER_ERROR:{identifier}")

    def evaluate_all(
        self,
        order_context: Mapping[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Evaluate all four gates. Any denial fails the whole chain (fail closed)."""
        results: dict[str, dict[str, Any]] = {}
        for identifier in TRUSTED_EVALUATOR_IDENTIFIERS:
            results[identifier] = self.evaluate_gate(identifier, order_context)
        return results

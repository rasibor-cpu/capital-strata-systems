from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Tuple
import time

from backend.governance.prop_trading_governor import (
    PropTradingGovernor,
    build_default_prop_state,
)
from backend.runtime.capital_state import is_tradeable_capital_state


MAX_POSITIONS_BY_ASSET = {
    "crypto": 3,
    "fx": 3,
    "futures": 2,
    "options": 2,
}

ENGINE_MODE_PROBABILITY_THRESHOLD = {
    "SAFE": 0.65,
    "CONSERVATIVE": 0.60,
    "BALANCED": 0.58,
    "AGGRESSIVE": 0.55,
    "EXPANSION": 0.52,
}

SESSION_TIMEOUT_SECONDS = 3600


def normalize_asset_class(asset_class: Any) -> str:
    return str(asset_class or "").strip().lower()


@dataclass
class GateDecision:
    approved: bool
    reason: str
    engine_mode: str
    timestamp: float
    details: Dict[str, Any]


class CSSUnifiedTradeGate:

    def __init__(self, event_bus: Optional[Any] = None) -> None:
        self.prop_governor = PropTradingGovernor()
        self.event_bus = event_bus

    def _safe_publish_event(
        self,
        event_type: str,
        severity: str,
        category: str,
        payload: Dict[str, Any],
    ) -> None:
        if not self.event_bus:
            return
        try:
            from backend.events.event_models import Event
            event = Event(
                event_type=event_type,
                severity=severity,
                category=category,
                source="css_unified_trade_gate",
                payload=payload,
            )
            self.event_bus.publish(event)
        except Exception:
            pass

    def approve_trade(
        self,
        candidate: Dict[str, Any],
        session: Dict[str, Any],
        portfolio_state: Dict[str, Any],
        engine_mode: str,
    ) -> GateDecision:
        decision = self._approve_trade_internal(candidate, session, portfolio_state, engine_mode)
        
        event_type = "TRADE_APPROVED" if decision.approved else "TRADE_REJECTED"
        severity = "INFO" if decision.approved else "WARNING"
        payload = {
            "approved": decision.approved,
            "reason": decision.reason,
            "engine_mode": decision.engine_mode,
            "timestamp": decision.timestamp,
            "details": decision.details,
            "candidate": candidate,
        }
        self._safe_publish_event(
            event_type=event_type,
            severity=severity,
            category="TRADING",
            payload=payload
        )
        return decision

    def _approve_trade_internal(
        self,
        candidate: Dict[str, Any],
        session: Dict[str, Any],
        portfolio_state: Dict[str, Any],
        engine_mode: str,
    ) -> GateDecision:

        now = time.time()

        capital_state = self._extract_capital_state(candidate, portfolio_state)
        if capital_state is not None and not is_tradeable_capital_state(capital_state):
            return self._reject(
                "CAPITAL_STATE_UNAVAILABLE",
                engine_mode,
                now,
                candidate,
            )

        valid, reason = self._validate_candidate(candidate)
        if not valid:
            return self._reject(
                f"validation failed: {reason}",
                engine_mode,
                now,
                candidate,
            )

        valid, reason = self._validate_session(
            session,
            now,
        )

        if not valid:
            return self._reject(
                reason,
                engine_mode,
                now,
                candidate,
            )

        role = session.get("role")

        if not self._check_role(role):
            return self._reject(
                "unauthorized role",
                engine_mode,
                now,
                candidate,
            )

        if not portfolio_state:
            return self._reject(
                "portfolio state unavailable",
                engine_mode,
                now,
                candidate,
            )

        asset_class = normalize_asset_class(
            candidate.get("asset_class", "")
        )

        if not self._check_position_limits(
            asset_class,
            portfolio_state,
        ):
            return self._reject(
                "position limit reached",
                engine_mode,
                now,
                candidate,
            )

        prop_state = build_default_prop_state()

        prop_result = self.prop_governor.evaluate(
            prop_state
        )

        if prop_result.get("blocked"):
            return self._reject(
                "prop trading governor blocked trade",
                engine_mode,
                now,
                candidate,
            )

        expected_value = float(
            candidate.get("expected_value")
        )

        cost = float(
            candidate.get("cost")
        )

        probability = float(
            candidate.get("probability")
        )

        if cost >= expected_value:
            return self._reject(
                "cost exceeds edge",
                engine_mode,
                now,
                candidate,
            )

        threshold = (
            ENGINE_MODE_PROBABILITY_THRESHOLD.get(
                engine_mode,
                0.58,
            )
        )

        if probability < threshold:
            return self._reject(
                "probability below threshold",
                engine_mode,
                now,
                candidate,
            )

        approval_reason = (
            f"approved: prob={probability:.3f} "
            f">= {threshold:.3f}, "
            f"cost={cost:.4f} "
            f"< ev={expected_value:.4f}"
        )

        return GateDecision(
            approved=True,
            reason=approval_reason,
            engine_mode=engine_mode,
            timestamp=now,
            details={
                "asset_class": asset_class,
                "expected_value": expected_value,
                "cost": cost,
                "probability": probability,
                "threshold": threshold,
                "prop_governor": prop_result,
            },
        )

    def _validate_candidate(
        self,
        candidate: Dict[str, Any],
    ) -> Tuple[bool, str]:

        if not candidate:
            return False, "no candidate"

        required_fields = [
            "asset_class",
            "expected_value",
            "cost",
            "probability",
        ]

        for field in required_fields:
            if field not in candidate:
                return False, f"missing {field}"

        asset_class = normalize_asset_class(
            candidate.get("asset_class", "")
        )

        if asset_class not in MAX_POSITIONS_BY_ASSET:
            return False, "unrecognized asset class"

        for field in [
            "expected_value",
            "cost",
            "probability",
        ]:
            try:
                value = float(
                    candidate.get(field)
                )

            except (
                TypeError,
                ValueError,
            ):
                return False, f"invalid {field}"

            if (
                field == "expected_value"
                and value <= 0
            ):
                return False, (
                    "negative or zero expected value"
                )

            if (
                field == "cost"
                and value < 0
            ):
                return False, (
                    "invalid cost value"
                )

            if (
                field == "probability"
                and not (0.0 <= value <= 1.0)
            ):
                return False, (
                    "invalid probability"
                )

        return True, "ok"

    def _extract_capital_state(
        self,
        candidate: Dict[str, Any],
        portfolio_state: Dict[str, Any],
    ) -> str | None:
        if isinstance(candidate, dict):
            direct = candidate.get("capital_state")
            if direct is not None:
                return str(direct).upper()
        if isinstance(portfolio_state, dict):
            direct = portfolio_state.get("capital_state")
            if direct is not None:
                return str(direct).upper()
            nested = portfolio_state.get("capital")
            if isinstance(nested, dict) and nested.get("capital_state") is not None:
                return str(nested.get("capital_state")).upper()
        return None

    def _validate_session(
        self,
        session: Dict[str, Any],
        now: float,
    ) -> Tuple[bool, str]:

        if not session:
            return False, "no session"

        created = session.get("created")

        if created is None:
            return False, "invalid session"

        if (
            now - created
            > SESSION_TIMEOUT_SECONDS
        ):
            return False, "session expired"

        return True, "ok"

    def _check_role(self, role: str) -> bool:
        return role in {
            "ADMIN",
            "SUPER_USER",
            "TRADER",
        }

    def _check_position_limits(
        self,
        asset_class: str,
        portfolio_state: Dict[str, Any],
    ) -> bool:

        asset_class = normalize_asset_class(asset_class)

        limits = MAX_POSITIONS_BY_ASSET.get(
            asset_class,
            0,
        )

        current = self._current_positions_for_asset_class(
            asset_class,
            portfolio_state,
        )

        return current < limits

    def _current_positions_for_asset_class(
        self,
        asset_class: str,
        portfolio_state: Dict[str, Any],
    ) -> int:

        normalized_asset_class = normalize_asset_class(asset_class)
        current = 0

        for key, value in (portfolio_state or {}).items():
            if normalize_asset_class(key) != normalized_asset_class:
                continue

            current += int(value or 0)

        return current

    def evaluate(
        self,
        *args,
        **kwargs,
    ) -> GateDecision:
        return self.approve_trade(
            *args,
            **kwargs,
        )

    def _reject(
        self,
        reason: str,
        engine_mode: str,
        timestamp: float,
        candidate: Dict[str, Any] = None,
    ) -> GateDecision:

        return GateDecision(
            approved=False,
            reason=f"rejected: {reason}",
            engine_mode=engine_mode,
            timestamp=timestamp,
            details={
                "asset_class": (
                    normalize_asset_class(candidate.get("asset_class"))
                    if candidate
                    else None
                ),
                "symbol": (
                    candidate.get("symbol")
                    if candidate
                    else None
                ),
            },
        )
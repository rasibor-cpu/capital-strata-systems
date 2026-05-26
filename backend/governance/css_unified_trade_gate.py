
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Tuple
import time

from backend.governance.prop_trading_governor import (
    PropTradingGovernor,
    build_default_prop_state,
)


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


@dataclass
class GateDecision:
    approved: bool
    reason: str
    engine_mode: str
    timestamp: float
    details: Dict[str, Any]


class CSSUnifiedTradeGate:

    def __init__(self) -> None:
        self.prop_governor = PropTradingGovernor()

    def approve_trade(
        self,
        candidate: Dict[str, Any],
        session: Dict[str, Any],
        portfolio_state: Dict[str, Any],
        engine_mode: str,
    ) -> GateDecision:

        now = time.time()

        # --------------------------------------------------
        # 0. FAIL-CLOSED CANDIDATE VALIDATION (B1)
        # --------------------------------------------------
        valid, reason = self._validate_candidate(candidate)
        if not valid:
            return self._reject(
                f"validation failed: {reason}",
                engine_mode,
                now,
                candidate,
            )

        # --------------------------------------------------
        # 1. SESSION VALIDATION
        # --------------------------------------------------
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

        # --------------------------------------------------
        # 2. ROLE VALIDATION
        # --------------------------------------------------
        role = session.get("role")

        if not self._check_role(role):
            return self._reject(
                "unauthorized role",
                engine_mode,
                now,
                candidate,
            )

        # --------------------------------------------------
        # 3. PORTFOLIO STATE VALIDATION
        # --------------------------------------------------
        if not portfolio_state:
            return self._reject(
                "portfolio state unavailable",
                engine_mode,
                now,
                candidate,
            )

        asset_class = str(
            candidate.get("asset_class", "")
        ).strip().lower()

        # --------------------------------------------------
        # 4. POSITION LIMIT CHECK
        # --------------------------------------------------
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

        # --------------------------------------------------
        # 4B. PROP TRADING GOVERNANCE
        # --------------------------------------------------
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

        # --------------------------------------------------
        # 5. SAFE EXTRACTION
        # --------------------------------------------------
        expected_value = float(
            candidate.get("expected_value")
        )

        cost = float(
            candidate.get("cost")
        )

        probability = float(
            candidate.get("probability")
        )

        # --------------------------------------------------
        # 6. EDGE VALIDATION
        # --------------------------------------------------
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

        # --------------------------------------------------
        # 7. APPROVAL
        # --------------------------------------------------
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

    # ======================================================
    # INTERNAL HELPERS
    # ======================================================

    def _validate_candidate(
        self,
        candidate: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        FAIL-CLOSED validation
        """

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

        asset_class = str(
            candidate.get("asset_class", "")
        ).strip().lower()

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

        asset_class = str(
            asset_class or ""
        ).strip().lower()

        limits = MAX_POSITIONS_BY_ASSET.get(
            asset_class,
            0,
        )

        current = portfolio_state.get(
            asset_class,
            0,
        )

        return current < limits

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
                    candidate.get("asset_class")
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


from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Tuple
import time


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

    def approve_trade(
        self,
        candidate: Dict[str, Any],
        session: Dict[str, Any],
        portfolio_state: Dict[str, Any],
        engine_mode: str,
    ) -> GateDecision:

        now = time.time()

        # --------------------------------------------------
        # 1. SESSION VALIDATION (FAIL-CLOSED)
        # --------------------------------------------------
        valid, reason = self._validate_session(session, now)
        if not valid:
            return self._reject(reason, engine_mode, now, candidate)

        # --------------------------------------------------
        # 2. ROLE VALIDATION
        # --------------------------------------------------
        role = session.get("role")
        if not self._check_role(role):
            return self._reject("unauthorized role", engine_mode, now, candidate)

        # --------------------------------------------------
        # 3. PORTFOLIO STATE VALIDATION
        # --------------------------------------------------
        if not portfolio_state:
            return self._reject("portfolio state unavailable", engine_mode, now, candidate)

        # --------------------------------------------------
        # 4. ASSET CLASS VALIDATION (FIX C2)
        # --------------------------------------------------
        asset_class = candidate.get("asset_class")
        if asset_class not in MAX_POSITIONS_BY_ASSET:
            return self._reject("unrecognized asset class", engine_mode, now, candidate)

        # --------------------------------------------------
        # 5. POSITION LIMIT CHECK
        # --------------------------------------------------
        if not self._check_position_limits(asset_class, portfolio_state):
            return self._reject("position limit reached", engine_mode, now, candidate)

        # --------------------------------------------------
        # 6. REQUIRED FIELD VALIDATION (FIX C3)
        # --------------------------------------------------
        if "expected_value" not in candidate:
            return self._reject("missing expected_value", engine_mode, now, candidate)

        if "cost" not in candidate:
            return self._reject("missing cost", engine_mode, now, candidate)

        expected_value = float(candidate.get("expected_value"))
        cost = float(candidate.get("cost"))

        if expected_value <= 0:
            return self._reject("negative or zero expected value", engine_mode, now, candidate)

        if cost < 0:
            return self._reject("invalid cost value", engine_mode, now, candidate)

        if cost >= expected_value:
            return self._reject("cost exceeds edge", engine_mode, now, candidate)

        # --------------------------------------------------
        # 7. PROBABILITY VALIDATION (FIX E1)
        # --------------------------------------------------
        probability = float(candidate.get("probability", 0.0))

        if not (0.0 <= probability <= 1.0):
            return self._reject("invalid probability", engine_mode, now, candidate)

        threshold = ENGINE_MODE_PROBABILITY_THRESHOLD.get(engine_mode, 0.58)

        if probability < threshold:
            return self._reject("probability below threshold", engine_mode, now, candidate)

        # --------------------------------------------------
        # 8. APPROVE
        # --------------------------------------------------
        return GateDecision(
            approved=True,
            reason="approved",
            engine_mode=engine_mode,
            timestamp=now,
            details={
                "asset_class": asset_class,
                "expected_value": expected_value,
                "cost": cost,
                "probability": probability,
                "threshold": threshold,
            },
        )

    # ======================================================
    # INTERNAL HELPERS
    # ======================================================

    def _validate_session(self, session: Dict[str, Any], now: float) -> Tuple[bool, str]:
        if not session:
            return False, "no session"

        created = session.get("created")
        if created is None:
            return False, "invalid session"

        if now - created > SESSION_TIMEOUT_SECONDS:
            return False, "session expired"

        return True, "ok"

    def _check_role(self, role: str) -> bool:
        return role in {"ADMIN", "SUPER_USER", "TRADER"}

    def _check_position_limits(self, asset_class: str, portfolio_state: Dict[str, Any]) -> bool:
        limits = MAX_POSITIONS_BY_ASSET.get(asset_class, 0)
        current = portfolio_state.get(asset_class, 0)
        return current < limits

    def _reject(
        self,
        reason: str,
        engine_mode: str,
        timestamp: float,
        candidate: Dict[str, Any] = None,
    ) -> GateDecision:
        return GateDecision(
            approved=False,
            reason=reason,
            engine_mode=engine_mode,
            timestamp=timestamp,
            details={
                "asset_class": candidate.get("asset_class") if candidate else None,
                "symbol": candidate.get("symbol") if candidate else None,
            },
        )

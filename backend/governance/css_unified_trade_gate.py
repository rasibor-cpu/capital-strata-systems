from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Any, Tuple


# ==============================
# CONFIGURATION
# ==============================

MODE_THRESHOLDS = {
    "SAFE": 0.65,
    "CONSERVATIVE": 0.62,
    "BALANCED": 0.58,
    "AGGRESSIVE": 0.55,
    "EXPANSION": 0.52,
}

MAX_POSITIONS_BY_ASSET = {
    "crypto": 3,
    "fx": 3,
    "futures": 2,
    "options": 2,
}

SESSION_TIMEOUT_SECONDS = 3600  # 1 hour


# ==============================
# DATA STRUCTURES
# ==============================

@dataclass
class GateDecision:
    approved: bool
    reason: str
    mode: str
    probability: float
    expected_value: float
    cost: float
    timestamp: float
    details: Dict[str, Any]


# ==============================
# MAIN GATE CLASS
# ==============================

class CSSUnifiedTradeGate:
    """
    Central Governance Gate for all trade approvals in CSS.

    This enforces:
    - Session validity
    - Role authorization
    - Engine mode thresholds
    - Probability gating
    - Expected value gating
    - Cost control
    - Position limits
    - Audit payload generation
    """

    def __init__(self):
        pass

    # ==============================
    # PUBLIC ENTRY POINT
    # ==============================

    def approve_trade(
        self,
        candidate: Dict[str, Any],
        session: Dict[str, Any],
        engine_mode: str,
        portfolio_state: Dict[str, Any],
    ) -> GateDecision:

        now = time.time()

        # ------------------------------
        # 1. SESSION VALIDATION
        # ------------------------------
        valid, reason = self._validate_session(session, now)
        if not valid:
            return self._reject(reason, engine_mode, now)

        # ------------------------------
        # 2. ROLE VALIDATION
        # ------------------------------
        if not self._validate_role(session):
            return self._reject("unauthorized role", engine_mode, now)

        # ------------------------------
        # 3. ENGINE MODE VALIDATION
        # ------------------------------
        threshold = MODE_THRESHOLDS.get(engine_mode)
        if threshold is None:
            return self._reject("invalid engine mode", engine_mode, now)

        # ------------------------------
        # 4. POSITION LIMIT CHECK
        # ------------------------------
        asset_class = candidate.get("asset_class", "unknown")
        if not self._check_position_limits(asset_class, portfolio_state):
            return self._reject("position limit reached", engine_mode, now)

        # ------------------------------
        # 5. PROBABILITY CHECK
        # ------------------------------
        probability = float(candidate.get("probability", 0.0))
        if probability < threshold:
            return self._reject(
                f"probability too low ({probability:.2f} < {threshold:.2f})",
                engine_mode,
                now,
                probability=probability,
            )

        # ------------------------------
        # 6. EXPECTED VALUE CHECK
        # ------------------------------
        expected_value = float(candidate.get("expected_value", 0.0))
        if expected_value <= 0:
            return self._reject(
                "negative or zero expected value",
                engine_mode,
                now,
                probability=probability,
                expected_value=expected_value,
            )

        # ------------------------------
        # 7. COST CHECK
        # ------------------------------
        cost = float(candidate.get("cost", 0.0))
        edge = expected_value

        if cost >= edge:
            return self._reject(
                "cost exceeds edge",
                engine_mode,
                now,
                probability=probability,
                expected_value=expected_value,
                cost=cost,
            )

        # ------------------------------
        # APPROVED
        # ------------------------------
        return GateDecision(
            approved=True,
            reason="approved",
            mode=engine_mode,
            probability=probability,
            expected_value=expected_value,
            cost=cost,
            timestamp=now,
            details={
                "asset_class": asset_class,
                "symbol": candidate.get("symbol"),
                "threshold": threshold,
            },
        )

    # ==============================
    # INTERNAL METHODS
    # ==============================

    def _validate_session(self, session: Dict[str, Any], now: float) -> Tuple[bool, str]:
        if not session:
            return False, "no session"

        created = session.get("created")
        if created is None:
            return False, "invalid session"

        if now - created > SESSION_TIMEOUT_SECONDS:
            return False, "session expired"

        return True, "ok"

    def _validate_role(self, session: Dict[str, Any]) -> bool:
        role = session.get("role")
        return role in {"ADMIN", "SUPER_USER", "TRADER"}

    def _check_position_limits(self, asset_class: str, portfolio_state: Dict[str, Any]) -> bool:
        limits = MAX_POSITIONS_BY_ASSET.get(asset_class, 0)
        current = portfolio_state.get(asset_class, 0)
        return current < limits

    def _reject(
        self,
        reason: str,
        mode: str,
        timestamp: float,
        probability: float = 0.0,
        expected_value: float = 0.0,
        cost: float = 0.0,
    ) -> GateDecision:
        return GateDecision(
            approved=False,
            reason=reason,
            mode=mode,
            probability=probability,
            expected_value=expected_value,
            cost=cost,
            timestamp=timestamp,
            details={},
        )

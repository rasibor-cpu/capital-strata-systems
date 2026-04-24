from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Any, Tuple


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

MAX_TOTAL_POSITIONS = 10
BLEED_RATIO_THRESHOLD = 0.25

SESSION_TIMEOUT_SECONDS = 3600


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


class CSSUnifiedTradeGate:

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
        # 3. ENGINE MODE
        # ------------------------------
        threshold = MODE_THRESHOLDS.get(engine_mode)
        if threshold is None:
            return self._reject("invalid engine mode", engine_mode, now)

        # ------------------------------
        # 4. TOTAL EXPOSURE LIMIT
        # ------------------------------
        total_positions = portfolio_state.get("open_positions_total", 0)
        if total_positions >= MAX_TOTAL_POSITIONS:
            return self._reject("total exposure limit reached", engine_mode, now)

        # ------------------------------
        # 5. ASSET POSITION LIMIT
        # ------------------------------
        asset_class = candidate.get("asset_class", "unknown")
        if not self._check_position_limits(asset_class, portfolio_state):
            return self._reject("position limit reached", engine_mode, now)

        # ------------------------------
        # 6. PROBABILITY
        # ------------------------------
        probability = float(candidate.get("probability", 0.0))
        if probability < threshold:
            return self._reject(
                "probability too low",
                engine_mode,
                now,
                probability,
            )

        # ------------------------------
        # 7. EXPECTED VALUE
        # ------------------------------
        expected_value = float(candidate.get("expected_value", 0.0))
        if expected_value <= 0:
            return self._reject(
                "negative expected value",
                engine_mode,
                now,
                probability,
                expected_value,
            )

        # ------------------------------
        # 8. COST CHECK
        # ------------------------------
        cost = float(candidate.get("cost", 0.0))
        if cost >= expected_value:
            return self._reject(
                "cost exceeds edge",
                engine_mode,
                now,
                probability,
                expected_value,
                cost,
            )

        # ------------------------------
        # 9. BLEED PROTECTION
        # ------------------------------
        if self._bleed_detected(asset_class, portfolio_state):
            return self._reject(
                "bleed protection triggered",
                engine_mode,
                now,
                probability,
                expected_value,
                cost,
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
                "portfolio_state": portfolio_state,
            },
        )

    # ==============================

    def _bleed_detected(self, asset_class: str, state: Dict[str, Any]) -> bool:
        pnl = state.get("pnl_by_asset", {})
        asset_pnl = float(pnl.get(asset_class, 0.0))

        if asset_pnl >= 0:
            return False

        positive_total = sum(v for v in pnl.values() if v > 0)

        if positive_total <= 0:
            return False

        loss_ratio = abs(asset_pnl) / positive_total
        return loss_ratio > BLEED_RATIO_THRESHOLD

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
        return session.get("role") in {"ADMIN", "SUPER_USER", "TRADER"}

    def _check_position_limits(self, asset_class: str, portfolio_state: Dict[str, Any]) -> bool:
        limit = MAX_POSITIONS_BY_ASSET.get(asset_class, 0)
        current = portfolio_state.get(f"{asset_class}_open", 0)
        return current < limit

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
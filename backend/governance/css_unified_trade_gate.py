from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Tuple


MODE_THRESHOLDS = {
    "SAFE": 0.68,
    "CONSERVATIVE": 0.64,
    "BALANCED": 0.56,
    "AGGRESSIVE": 0.51,
    "EXPANSION": 0.48,
}

MIN_EV_BY_MODE = {
    "SAFE": 0.035,
    "CONSERVATIVE": 0.025,
    "BALANCED": 0.010,
    "AGGRESSIVE": 0.000,
    "EXPANSION": -0.005,
}

MIN_ELASTICITY_BY_MODE = {
    "SAFE": 0.35,
    "CONSERVATIVE": 0.30,
    "BALANCED": 0.22,
    "AGGRESSIVE": 0.15,
    "EXPANSION": 0.10,
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
        engine_mode = str(engine_mode or "BALANCED").upper()

        valid, reason = self._validate_session(session, now)
        if not valid:
            return self._reject(reason, engine_mode, now)

        if not self._validate_role(session):
            return self._reject("unauthorized role", engine_mode, now)

        threshold = MODE_THRESHOLDS.get(engine_mode)
        if threshold is None:
            return self._reject("invalid engine mode", engine_mode, now)

        min_ev = MIN_EV_BY_MODE.get(engine_mode, 0.01)
        min_elasticity = MIN_ELASTICITY_BY_MODE.get(engine_mode, 0.22)

        total_positions = int(portfolio_state.get("open_positions_total", 0))
        if total_positions >= MAX_TOTAL_POSITIONS:
            return self._reject("total exposure limit reached", engine_mode, now)

        asset_class = str(candidate.get("asset_class", "unknown")).lower()
        if not self._check_position_limits(asset_class, portfolio_state):
            return self._reject("position limit reached", engine_mode, now)

        probability = float(candidate.get("probability", 0.0))
        expected_value = float(candidate.get("expected_value", 0.0))
        cost = float(candidate.get("cost", 0.0))
        elasticity = float(candidate.get("vwap_elasticity", candidate.get("elasticity_score", 0.0)))

        if probability < threshold:
            return self._reject(
                f"probability too low ({probability:.4f} < {threshold:.4f})",
                engine_mode,
                now,
                probability=probability,
                expected_value=expected_value,
                cost=cost,
            )

        if expected_value <= min_ev:
            return self._reject(
                f"expected value too low ({expected_value:.4f} <= {min_ev:.4f})",
                engine_mode,
                now,
                probability=probability,
                expected_value=expected_value,
                cost=cost,
            )

        if cost >= expected_value:
            return self._reject(
                "cost exceeds edge",
                engine_mode,
                now,
                probability=probability,
                expected_value=expected_value,
                cost=cost,
            )

        if elasticity < min_elasticity:
            return self._reject(
                f"vwap elasticity too low ({elasticity:.4f} < {min_elasticity:.4f})",
                engine_mode,
                now,
                probability=probability,
                expected_value=expected_value,
                cost=cost,
            )

        if self._bleed_detected(asset_class, portfolio_state):
            return self._reject(
                "bleed protection triggered",
                engine_mode,
                now,
                probability=probability,
                expected_value=expected_value,
                cost=cost,
            )

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
                "min_ev": min_ev,
                "vwap_elasticity": elasticity,
                "min_elasticity": min_elasticity,
                "portfolio_state": portfolio_state,
            },
        )

    def _validate_session(self, session: Dict[str, Any], now: float) -> Tuple[bool, str]:
        if not session:
            return False, "no session"

        created = session.get("created")
        if created is None:
            return False, "invalid session"

        if now - float(created) > SESSION_TIMEOUT_SECONDS:
            return False, "session expired"

        return True, "ok"

    def _validate_role(self, session: Dict[str, Any]) -> bool:
        role = str(session.get("role", "")).upper()
        return role in {"ADMIN", "SUPER_USER", "TRADER"}

    def _check_position_limits(self, asset_class: str, portfolio_state: Dict[str, Any]) -> bool:
        limit = int(MAX_POSITIONS_BY_ASSET.get(asset_class, 0))
        current = int(portfolio_state.get(f"{asset_class}_open", 0))
        return current < limit

    def _bleed_detected(self, asset_class: str, state: Dict[str, Any]) -> bool:
        pnl = state.get("pnl_by_asset", {})
        if not isinstance(pnl, dict):
            return False

        asset_pnl = float(pnl.get(asset_class, 0.0))

        if asset_pnl >= 0:
            return False

        positive_total = sum(float(v) for v in pnl.values() if float(v) > 0)

        if positive_total <= 0:
            return False

        loss_ratio = abs(asset_pnl) / positive_total
        return loss_ratio > BLEED_RATIO_THRESHOLD

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
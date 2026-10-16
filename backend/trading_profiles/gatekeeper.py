"""Server-side onboarding enforcement for every new risk-taking workflow.

`risk_taking_status()` is the single check used at sign-in and by risk-taking routes:
a user may start new risk only with a valid, current acceptance of the CSS User
Operating Manual for their active settings, and only while not paused.

Risk-reducing actions (kill switch on, lower trading mode or engine mode, pause,
disarm, mandate revocation, protective exits) are never blocked by this check.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from backend.trading_profiles.service import TradingProfileService

ONBOARDING_PATH = "/trading-profiles/onboarding"
MOBILE_MODE_RANK = {"MOBILE_READ_ONLY": 0, "MOBILE_PAPER_TRADING": 1, "MOBILE_LIVE_TRADING_ARMED": 2}
ENGINE_MODE_RANK = {"SAFE": 0, "CONSERVATIVE": 1, "BALANCED": 2, "AGGRESSIVE": 3, "EXPANSION": 4}


@dataclass(frozen=True)
class RiskTakingStatus:
    allowed: bool
    reason: str
    onboarding_path: str = ONBOARDING_PATH


def risk_taking_status(service: TradingProfileService, user_id: str | None) -> RiskTakingStatus:
    if not user_id:
        return RiskTakingStatus(False, "authentication_required")
    try:
        state = service.preferences.get(str(user_id))
        ok, reason = service.consent.verify_active(str(user_id), state)
    except Exception as exc:  # unreadable stores etc. -> fail closed
        return RiskTakingStatus(False, f"acceptance_unverifiable:{type(exc).__name__}")
    if not ok:
        return RiskTakingStatus(False, reason)
    if state.paused:
        return RiskTakingStatus(False, "trading_paused_by_user")
    return RiskTakingStatus(True, "acceptance_valid")


def controls_change_increases_risk(current: Mapping[str, Any], requested: Mapping[str, Any]) -> bool:
    """True if any part of a mobile-controls change adds risk. Unknown values count as increases."""
    def rank(table: Mapping[str, int], value: Any) -> int:
        return table.get(str(value or "").strip().upper(), len(table))

    if rank(MOBILE_MODE_RANK, requested.get("mobile_trading_mode")) > rank(MOBILE_MODE_RANK, current.get("mobile_trading_mode")):
        return True
    if rank(ENGINE_MODE_RANK, requested.get("engine_mode")) > rank(ENGINE_MODE_RANK, current.get("engine_mode")):
        return True
    if bool(current.get("live_order_kill_switch")) and not bool(requested.get("live_order_kill_switch")):
        return True
    return False

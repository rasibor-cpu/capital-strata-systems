"""CSS startup operating modes (issue #118, owner decision 2026-10-16: exactly four).

Selecting a mode never authorizes live trading: every mode's permissions keep live
broker order paths closed. A mode only becomes active after the user accepts the
CSS User Operating Manual, Trading Assumptions and Risk Disclosure Agreement for the
exact settings (see consent.py). Live activation stays under the separate release
governance (CSS-062/063/064, kill switch, pilot ceilings).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OperatingMode(str, Enum):
    SIMULATED_TRADING = "Simulated Trading"
    CSS_ASSISTED_TRADING = "CSS-Assisted Trading"
    COPY_CSS_TRADER = "Copy a CSS Trader"
    CSS_AUTONOMOUS_TRADING = "CSS Autonomous Trading"

    @classmethod
    def parse(cls, value: object) -> "OperatingMode":
        """Exact display name or enum name only; anything else is rejected."""
        text = str(value or "").strip()
        for mode in cls:
            if text == mode.value or text == mode.name:
                return mode
        raise ValueError(f"unknown operating mode: {text!r}")


@dataclass(frozen=True)
class ModePermissions:
    mode: OperatingMode
    # Orders are evaluated through the governed paper pipeline (validation only).
    governed_paper_pipeline: bool
    # Fills are produced by the deterministic simulator, never by a broker.
    simulated_fills_only: bool
    requires_risk_personality: bool
    requires_trader_mandate: bool
    # CSS proposes; the user must individually approve every order.
    requires_per_order_approval: bool
    decision_authority: str
    # Invariant for every mode: selection is not live-trading authorization.
    live_broker_orders_permitted: bool = False
    # No mode may reach any broker order path, paper or live.
    broker_order_path_reachable: bool = False


_PERMISSIONS = {
    OperatingMode.SIMULATED_TRADING: ModePermissions(
        mode=OperatingMode.SIMULATED_TRADING, governed_paper_pipeline=False, simulated_fills_only=True,
        requires_risk_personality=False, requires_trader_mandate=False, requires_per_order_approval=False,
        decision_authority="practice only; no broker path of any kind",
    ),
    OperatingMode.CSS_ASSISTED_TRADING: ModePermissions(
        mode=OperatingMode.CSS_ASSISTED_TRADING, governed_paper_pipeline=True, simulated_fills_only=True,
        requires_risk_personality=True, requires_trader_mandate=False, requires_per_order_approval=True,
        decision_authority="CSS proposes; the user approves or rejects every order",
    ),
    OperatingMode.COPY_CSS_TRADER: ModePermissions(
        mode=OperatingMode.COPY_CSS_TRADER, governed_paper_pipeline=True, simulated_fills_only=True,
        requires_risk_personality=True, requires_trader_mandate=True, requires_per_order_approval=False,
        decision_authority="the chosen trader's signals, filtered and sized by the follower's personality and limits within a signed mandate",
    ),
    OperatingMode.CSS_AUTONOMOUS_TRADING: ModePermissions(
        mode=OperatingMode.CSS_AUTONOMOUS_TRADING, governed_paper_pipeline=True, simulated_fills_only=True,
        requires_risk_personality=True, requires_trader_mandate=False, requires_per_order_approval=False,
        decision_authority="CSS decides only within the settings and limits the user accepted",
    ),
}


def permissions_for(mode: OperatingMode) -> ModePermissions:
    permissions = _PERMISSIONS[OperatingMode(mode)]
    # Defensive invariant: no mode may ever open a live path from this layer.
    if permissions.live_broker_orders_permitted or permissions.broker_order_path_reachable:
        raise RuntimeError("operating mode permissions must not open a broker order path")
    return permissions

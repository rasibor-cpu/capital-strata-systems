from __future__ import annotations

from typing import Any, Dict

from dashboard.runtime.dashboard_state import (
    DashboardState,
    GovernanceState,
)


class GovernanceStateBuilder:
    """
    Build GovernanceState payloads for DashboardState.

    PURPOSE
    -------
    Normalize governance/runtime protection outputs into
    structured dashboard-safe governance state.

    RULES
    -----
    - builder must not override governance truth
    - builder must not execute trades
    - builder must not mutate runtime authority
    """

    def build(
        self,
        *,
        governance_payload: Dict[str, Any],
        state: DashboardState,
    ) -> DashboardState:

        governance_state = GovernanceState(
            governance_enabled=bool(
                governance_payload.get(
                    "governance_enabled",
                    True,
                )
            ),

            session_locked=bool(
                governance_payload.get(
                    "session_locked",
                    False,
                )
            ),

            defensive_mode_active=bool(
                governance_payload.get(
                    "defensive_mode_active",
                    False,
                )
            ),

            unified_trade_gate_active=bool(
                governance_payload.get(
                    "unified_trade_gate_active",
                    True,
                )
            ),

            audit_enabled=bool(
                governance_payload.get(
                    "audit_enabled",
                    True,
                )
            ),

            last_governance_event=str(
                governance_payload.get(
                    "last_governance_event",
                    "",
                )
            ),
        )

        state.governance_state = governance_state

        return state
from __future__ import annotations

from dataclasses import dataclass

from dashboard.runtime.dashboard_state import GovernanceState


@dataclass(frozen=True)
class GovernanceRenderContract:
    """
    PCNRASS-safe immutable render contract for governance display.

    Rules:
    - Renderer consumes this contract only.
    - Renderer performs no governance decisions.
    - Governance values must come from normalized governance state.
    """

    governance_enabled: bool
    session_locked: bool
    defensive_mode_active: bool
    unified_trade_gate_active: bool
    audit_enabled: bool
    last_governance_event: str

    @classmethod
    def from_governance_state(
        cls,
        governance_state: GovernanceState,
    ) -> "GovernanceRenderContract":
        return cls(
            governance_enabled=bool(governance_state.governance_enabled),
            session_locked=bool(governance_state.session_locked),
            defensive_mode_active=bool(governance_state.defensive_mode_active),
            unified_trade_gate_active=bool(
                governance_state.unified_trade_gate_active
            ),
            audit_enabled=bool(governance_state.audit_enabled),
            last_governance_event=str(governance_state.last_governance_event),
        )

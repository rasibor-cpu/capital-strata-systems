from __future__ import annotations

from dashboard.runtime.render_contracts.governance_render_contract import (
    GovernanceRenderContract,
)


class GovernanceRenderer:
    """
    PCNRASS-safe pure governance renderer.

    Rules:
    - Consume only GovernanceRenderContract.
    - Perform no governance calculations or decisions.
    - Do not access trade gates, engines, brokers, or audit internals directly.
    """

    def render(self, contract: GovernanceRenderContract) -> str:
        lines = [
            "==============================",
            " GOVERNANCE STATE",
            "==============================",
            f"Governance Enabled:      {self._format_bool(contract.governance_enabled)}",
            f"Session Locked:          {self._format_bool(contract.session_locked)}",
            f"Defensive Mode Active:   {self._format_bool(contract.defensive_mode_active)}",
            f"Unified Trade Gate:      {self._format_bool(contract.unified_trade_gate_active)}",
            f"Audit Enabled:           {self._format_bool(contract.audit_enabled)}",
            f"Last Governance Event:   {contract.last_governance_event or 'NONE'}",
            "==============================",
        ]

        return "\n".join(lines)

    @staticmethod
    def _format_bool(value: bool) -> str:
        if value:
            return "YES"

        return "NO"

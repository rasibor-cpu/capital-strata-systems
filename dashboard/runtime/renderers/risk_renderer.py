from __future__ import annotations

from dashboard.runtime.render_contracts.risk_render_contract import RiskRenderContract


class RiskRenderer:
    """
    PCNRASS-safe pure risk renderer.
    """

    def render(self, contract: RiskRenderContract) -> str:
        lines = [
            "==============================",
            " RISK SUMMARY",
            "==============================",
            f"Risk State:              {contract.risk_state}",
            f"Gate Status:             {contract.gate_status}",
            f"Total Exposure:          {contract.total_exposure:,.2f}",
            f"Exposure Utilization:    {contract.exposure_utilization_pct:,.2f}%",
            "",
            f"Current Drawdown:        {contract.current_drawdown_pct:,.2f}%",
            f"Max Drawdown:            {contract.max_drawdown_pct:,.2f}%",
            f"Daily Loss Limit:        {contract.daily_loss_limit:,.2f}",
            f"Position Limit:          {contract.position_limit}",
            f"Exposure Limit:          {contract.exposure_limit:,.2f}",
            "",
            "Risk Limit Breaches:",
        ]

        if contract.risk_limits_breached:
            for breach in contract.risk_limits_breached:
                lines.append(f"  {breach}")
        else:
            lines.append("  NONE")

        lines.append("==============================")

        return "\n".join(lines)

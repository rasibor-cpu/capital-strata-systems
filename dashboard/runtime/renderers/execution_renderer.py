from __future__ import annotations

from dashboard.runtime.render_contracts.execution_render_contract import (
    ExecutionRenderContract,
)


class ExecutionRenderer:
    """
    PCNRASS-safe pure execution renderer.
    """

    def render(self, contract: ExecutionRenderContract) -> str:
        lines = [
            "==============================",
            " EXECUTION SUMMARY",
            "==============================",
            f"Execution State:         {contract.execution_state}",
            f"Accepted Trades:         {contract.accepted_trade_count}",
            f"Rejected Trades:         {contract.rejected_trade_count}",
            f"Pending Trades:          {contract.pending_trade_count}",
            "",
            f"Total Execution Cost:    {contract.total_execution_cost:,.2f}",
            f"Slippage Cost:           {contract.slippage_cost:,.2f}",
            f"Spread Cost:             {contract.spread_cost:,.2f}",
            f"Fee Cost:                {contract.fee_cost:,.2f}",
            f"Avg Slippage:            {contract.avg_slippage_bps:,.2f} bps",
            f"Avg Spread:              {contract.avg_spread_bps:,.2f} bps",
            f"Execution Cost State:    {contract.execution_cost_state}",
            f"Last Execution Event:    {contract.last_execution_event or 'NONE'}",
            "==============================",
        ]

        return "\n".join(lines)

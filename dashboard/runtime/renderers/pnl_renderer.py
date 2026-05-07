from __future__ import annotations

from dashboard.runtime.render_contracts.pnl_render_contract import PnLRenderContract


class PnLRenderer:
    """
    PCNRASS-safe pure PnL renderer.

    Rules:
    - Consume only PnLRenderContract.
    - Perform no business calculations.
    - Do not access engine, broker, account, or position internals.
    """

    def render(self, contract: PnLRenderContract) -> str:
        lines = [
            "==============================",
            " PnL SUMMARY",
            "==============================",
            f"Realized PnL:            {contract.realized_pnl:,.2f}",
            f"Unrealized PnL:          {contract.unrealized_pnl:,.2f}",
            f"Net PnL:                 {contract.net_pnl:,.2f}",
            "",
            f"Total Exposure:          {contract.total_exposure:,.2f}",
            f"Exposure Utilization:    {contract.exposure_utilization_pct:,.2f}%",
            f"Account Equity:          {contract.account_equity:,.2f}",
            "",
            f"Winners:                 {contract.winner_count}",
            f"Losers:                  {contract.loser_count}",
            f"Win Rate:                {contract.win_rate_pct:,.2f}%",
            "",
            "Asset Realized PnL:",
        ]

        if contract.asset_realized_pnl:
            for asset_class, value in contract.asset_realized_pnl.items():
                lines.append(f"  {asset_class}: {value:,.2f}")
        else:
            lines.append("  NONE: 0.00")

        lines.append("")
        lines.append("Asset Unrealized PnL:")

        if contract.asset_unrealized_pnl:
            for asset_class, value in contract.asset_unrealized_pnl.items():
                lines.append(f"  {asset_class}: {value:,.2f}")
        else:
            lines.append("  NONE: 0.00")

        lines.append("==============================")

        return "\n".join(lines)
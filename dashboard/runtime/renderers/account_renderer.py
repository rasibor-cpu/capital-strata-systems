from __future__ import annotations

from dashboard.runtime.render_contracts.account_render_contract import AccountRenderContract


class AccountRenderer:
    """
    PCNRASS-safe pure account renderer.

    Rules:
    - Consume only AccountRenderContract.
    - Perform no account calculations.
    - Do not access broker, engine, or account internals directly.
    """

    def render(self, contract: AccountRenderContract) -> str:
        lines = [
            "==============================",
            " ACCOUNT SUMMARY",
            "==============================",
            f"Broker:                  {contract.broker}",
            f"Mode:                    {contract.account_mode}",
            f"Currency:                {contract.currency}",
            "",
            f"Cash Balance:            {contract.cash_balance:,.2f}",
            f"Total Equity:            {contract.total_equity:,.2f}",
            f"Buying Power:            {contract.buying_power:,.2f}",
            f"Margin Used:             {contract.margin_used:,.2f}",
            f"Available Margin:        {contract.available_margin:,.2f}",
            "==============================",
        ]

        return "\n".join(lines)
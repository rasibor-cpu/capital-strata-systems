from __future__ import annotations

from dashboard.runtime.render_contracts.market_render_contract import MarketRenderContract


class MarketRenderer:
    """
    PCNRASS-safe pure market renderer.

    Rules:
    - Consume only MarketRenderContract.
    - Perform no business calculations.
    - Do not access engine, broker, account, or market internals directly.
    """

    def render(self, contract: MarketRenderContract) -> str:
        lines = [
            "==============================",
            " MARKET INTELLIGENCE",
            "==============================",
            f"Trend State:             {contract.trend_state}",
            f"Volatility State:        {contract.volatility_state}",
            f"Liquidity State:         {contract.liquidity_state}",
            f"Mean Reversion State:    {contract.mean_reversion_state}",
            f"Probability State:       {contract.probability_state}",
            f"Velocity State:          {contract.velocity_state}",
            "",
            f"VWAP State:              {contract.vwap_state}",
            f"VWAP Distance:           {contract.vwap_distance:,.4f}",
            f"VWAP Elasticity:         {contract.vwap_elasticity:,.4f}",
            "",
            f"Momentum State:          {contract.momentum_state}",
            f"Pressure State:          {contract.pressure_state}",
            f"Acceleration State:      {contract.acceleration_state}",
            "",
            f"Regime State:            {contract.regime_state}",
            f"Spread State:            {contract.spread_state}",
            f"Execution Cost State:    {contract.execution_cost_state}",
            f"Signal Confluence State: {contract.signal_confluence_state}",
            "==============================",
        ]

        return "\n".join(lines)

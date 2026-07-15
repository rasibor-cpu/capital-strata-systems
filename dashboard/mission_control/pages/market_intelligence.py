from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels


def render(state: dict) -> str:
    market = section(state, "market_intelligence")
    return (
        page_header("Market Intelligence", "Read-only regime, trend, volatility, liquidity, signal, rankings, watchlist, and freshness view.")
        + metric_grid(
            (
                ("Regime", market.get("market_regime"), market.get("market_regime")),
                ("Trend", market.get("trend"), market.get("trend")),
                ("Volatility", market.get("volatility"), market.get("volatility")),
                ("Liquidity", market.get("liquidity"), market.get("liquidity")),
                ("Momentum", market.get("momentum"), market.get("momentum")),
                ("Signal Confluence", market.get("signal_confluence"), market.get("signal_confluence")),
            )
        )
        + split_panels(
            detail_table("Signal Surface", {
                "pressure": market.get("pressure"),
                "probability": market.get("probability"),
                "velocity": market.get("velocity"),
                "vwap_state": market.get("vwap_state"),
                "spread_quality": market.get("spread_quality"),
                "execution_cost_state": market.get("execution_cost_state"),
            }),
            detail_table("Rankings And Watchlists", {
                "asset_class_rankings": market.get("asset_class_rankings"),
                "watchlists": market.get("watchlists"),
                "market_data_freshness": market.get("market_data_freshness"),
            }),
        )
    )

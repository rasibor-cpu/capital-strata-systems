from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels


def render(state: dict) -> str:
    portfolio = section(state, "portfolio")
    return (
        page_header("Portfolio", "Read-only equity, cash, capital, exposure, allocation, PnL, collateral, drawdown, and attribution view.")
        + metric_grid(
            (
                ("Equity", portfolio.get("equity"), "neutral"),
                ("Cash", portfolio.get("cash"), "neutral"),
                ("Buying Power", portfolio.get("buying_power"), "neutral"),
                ("Total Exposure", portfolio.get("total_exposure"), "neutral"),
                ("Capital Available", portfolio.get("capital_available"), "neutral"),
                ("Drawdown", portfolio.get("drawdown"), "neutral"),
            )
        )
        + split_panels(
            detail_table("Allocation", {
                "asset_allocation": portfolio.get("asset_allocation"),
                "sector_allocation": portfolio.get("sector_allocation"),
                "currency_exposure": portfolio.get("currency_exposure"),
                "concentration": portfolio.get("concentration", "UNAVAILABLE"),
            }),
            detail_table("Performance Attribution", {
                "pnl_by_asset_class": portfolio.get("pnl_by_asset_class"),
                "pnl_by_strategy": portfolio.get("pnl_by_strategy"),
                "capital_efficiency": portfolio.get("capital_efficiency"),
                "performance_attribution": portfolio.get("performance_attribution"),
            }),
        )
    )

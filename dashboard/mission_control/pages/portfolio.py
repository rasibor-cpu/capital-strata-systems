from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels


def render(state: dict) -> str:
    portfolio = section(state, "portfolio")
    command = section(state, "portfolio_command")
    capital = section(state, "capital_allocation_center")
    attribution = section(state, "performance_attribution")
    committee = section(state, "capital_committee")
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
            detail_table("Portfolio Command View", {
                "available_capital": command.get("available_capital"),
                "deployed_capital": command.get("deployed_capital"),
                "capital_utilization": command.get("capital_utilization"),
                "collateral": command.get("collateral"),
                "drawdown": command.get("drawdown"),
                "source": command.get("source"),
                "freshness": command.get("freshness"),
                "state_hash": command.get("state_hash"),
            }),
            detail_table("Capital Allocation Center", {
                "capital_deployed": capital.get("capital_deployed"),
                "available_capital": capital.get("available_capital"),
                "reserved_capital": capital.get("reserved_capital"),
                "utilization": capital.get("utilization"),
                "strategy_allocation": capital.get("strategy_allocation"),
                "asset_allocation": capital.get("asset_allocation"),
                "links": capital.get("links"),
                "state_hash": capital.get("state_hash"),
            }),
            detail_table("Capital Committee", {
                "capital_efficiency": committee.get("capital_efficiency"),
                "unused_capital": committee.get("unused_capital"),
                "deployment_efficiency": committee.get("deployment_efficiency"),
                "cash_utilization": committee.get("cash_utilization"),
                "margin_utilization": committee.get("margin_utilization"),
                "portfolio_leverage": committee.get("portfolio_leverage"),
            }),
            detail_table("Performance Attribution", {
                "pnl_attribution": attribution.get("pnl_attribution"),
                "strategy_attribution": attribution.get("strategy_attribution"),
                "broker_attribution": attribution.get("broker_attribution"),
                "timing_attribution": attribution.get("timing_attribution"),
                "execution_attribution": attribution.get("execution_attribution"),
                "risk_attribution": attribution.get("risk_attribution"),
            }),
        )
    )

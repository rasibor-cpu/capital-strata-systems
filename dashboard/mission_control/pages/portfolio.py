from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section


def _anchor_panel(anchor: str, content: str) -> str:
    return f'<div class="mc-section-anchor" id="{anchor}">{content}</div>'


def _evidence_panel(anchor: str, title: str, content: str) -> str:
    return (
        f'<div class="mc-section-anchor mc-evidence-disclosure" id="{anchor}">'
        f'<details><summary>{title}</summary>{content}</details>'
        '</div>'
    )


def _metric_status(value: object) -> object:
    return "UNAVAILABLE" if value in (None, "") else value


def _capital_snapshot(portfolio: dict, command: dict) -> dict:
    return {
        "equity": portfolio.get("equity"),
        "cash": portfolio.get("cash"),
        "buying_power": portfolio.get("buying_power"),
        "capital_available": portfolio.get("capital_available"),
        "available_capital": command.get("available_capital"),
        "deployed_capital": command.get("deployed_capital"),
        "capital_utilization": command.get("capital_utilization"),
        "collateral": command.get("collateral"),
    }


def render(state: dict) -> str:
    portfolio = section(state, "portfolio")
    command = section(state, "portfolio_command")
    capital = section(state, "capital_allocation_center")
    attribution = section(state, "performance_attribution")
    committee = section(state, "capital_committee")
    return (
        page_header("Portfolio", "Read-only equity, cash, capital, exposure, allocation, PnL, collateral, drawdown, and attribution view.")
        + '<nav class="mc-page-jump" aria-label="Portfolio sections">'
          '<a href="#mc-portfolio-capital">Capital</a>'
          '<a href="#mc-portfolio-allocation">Allocation</a>'
          '<a href="#mc-portfolio-committee">Committee</a>'
          '<a href="#mc-portfolio-attribution">Attribution</a>'
          '</nav>'
        + metric_grid(
            (
                ("Equity", portfolio.get("equity"), _metric_status(portfolio.get("equity"))),
                ("Cash", portfolio.get("cash"), _metric_status(portfolio.get("cash"))),
                ("Total Exposure", portfolio.get("total_exposure"), _metric_status(portfolio.get("total_exposure"))),
                ("Drawdown", portfolio.get("drawdown"), _metric_status(portfolio.get("drawdown"))),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-portfolio-priority",
            aria_label="Portfolio priority",
        )
        + metric_grid(
            (
                ("Buying Power", portfolio.get("buying_power"), _metric_status(portfolio.get("buying_power"))),
                ("Capital Available", portfolio.get("capital_available"), _metric_status(portfolio.get("capital_available"))),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Portfolio secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-portfolio-capital", detail_table("Capital Snapshot", _capital_snapshot(portfolio, command)))
        + _anchor_panel("mc-portfolio-allocation", detail_table("Allocation Snapshot", {
            "asset_allocation": portfolio.get("asset_allocation"),
            "sector_allocation": portfolio.get("sector_allocation"),
            "currency_exposure": portfolio.get("currency_exposure"),
            "concentration": portfolio.get("concentration", "UNAVAILABLE"),
        }))
        + _anchor_panel("mc-portfolio-committee", detail_table("Capital Committee Snapshot", {
            "capital_efficiency": committee.get("capital_efficiency"),
            "unused_capital": committee.get("unused_capital"),
            "deployment_efficiency": committee.get("deployment_efficiency"),
            "cash_utilization": committee.get("cash_utilization"),
            "margin_utilization": committee.get("margin_utilization"),
            "portfolio_leverage": committee.get("portfolio_leverage"),
        }))
        + _anchor_panel("mc-portfolio-attribution", detail_table("Performance Attribution Snapshot", {
            "pnl_attribution": attribution.get("pnl_attribution"),
            "strategy_attribution": attribution.get("strategy_attribution"),
            "broker_attribution": attribution.get("broker_attribution"),
            "timing_attribution": attribution.get("timing_attribution"),
            "execution_attribution": attribution.get("execution_attribution"),
            "risk_attribution": attribution.get("risk_attribution"),
        }))
        + _evidence_panel("mc-portfolio-command-evidence", "Show full portfolio command evidence", detail_table("Portfolio Command Evidence (Full)", {
            "available_capital": command.get("available_capital"),
            "deployed_capital": command.get("deployed_capital"),
            "capital_utilization": command.get("capital_utilization"),
            "collateral": command.get("collateral"),
            "drawdown": command.get("drawdown"),
            "source": command.get("source"),
            "freshness": command.get("freshness"),
            "state_hash": command.get("state_hash"),
        }))
        + _evidence_panel("mc-portfolio-allocation-evidence", "Show full capital-allocation evidence", detail_table("Capital Allocation Center Evidence (Full)", {
            "capital_deployed": capital.get("capital_deployed"),
            "available_capital": capital.get("available_capital"),
            "reserved_capital": capital.get("reserved_capital"),
            "utilization": capital.get("utilization"),
            "strategy_allocation": capital.get("strategy_allocation"),
            "asset_allocation": capital.get("asset_allocation"),
            "links": capital.get("links"),
            "state_hash": capital.get("state_hash"),
        }))
        + '</div>'
    )

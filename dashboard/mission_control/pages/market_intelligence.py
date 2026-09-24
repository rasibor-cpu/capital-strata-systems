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


def _opportunity_summary_rows(opportunities: dict) -> list[dict]:
    rows = opportunities.get("opportunities")
    if not isinstance(rows, list):
        return []
    summary = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        summary.append({
            "symbol": row.get("symbol"),
            "asset_class": row.get("asset_class"),
            "confidence": row.get("confidence"),
            "expected_quality": row.get("expected_quality"),
            "risk": row.get("risk"),
            "blocking_reason": row.get("blocking_reason"),
            "committee_outcome": row.get("committee_outcome"),
            "ranking": row.get("ranking"),
            "freshness": row.get("freshness"),
        })
    return summary


def render(state: dict) -> str:
    market = section(state, "market_intelligence")
    opportunities = section(state, "opportunity_ranking")
    return (
        page_header("Market Intelligence", "Read-only regime, trend, volatility, liquidity, signal, rankings, watchlist, and freshness view.")
        + '<nav class="mc-page-jump" aria-label="Market Intelligence sections">'
          '<a href="#mc-market-snapshot">Snapshot</a>'
          '<a href="#mc-market-rankings">Rankings</a>'
          '<a href="#mc-market-opportunities">Opportunities</a>'
          '</nav>'
        + metric_grid(
            (
                ("Regime", market.get("market_regime"), _metric_status(market.get("market_regime"))),
                ("Trend", market.get("trend"), _metric_status(market.get("trend"))),
                ("Volatility", market.get("volatility"), _metric_status(market.get("volatility"))),
                ("Liquidity", market.get("liquidity"), _metric_status(market.get("liquidity"))),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-market-priority",
            aria_label="Market Intelligence priority",
        )
        + metric_grid(
            (
                ("Momentum", market.get("momentum"), _metric_status(market.get("momentum"))),
                ("Signal Confluence", market.get("signal_confluence"), _metric_status(market.get("signal_confluence"))),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Market Intelligence secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-market-snapshot", detail_table("Market Snapshot", {
            "pressure": market.get("pressure"),
            "probability": market.get("probability"),
            "velocity": market.get("velocity"),
            "vwap_state": market.get("vwap_state"),
            "spread_quality": market.get("spread_quality"),
            "execution_cost_state": market.get("execution_cost_state"),
            "market_data_freshness": market.get("market_data_freshness"),
        }))
        + _anchor_panel("mc-market-rankings", detail_table("Rankings & Watchlists", {
            "asset_class_rankings": market.get("asset_class_rankings"),
            "watchlists": market.get("watchlists"),
            "market_data_freshness": market.get("market_data_freshness"),
        }))
        + _anchor_panel("mc-market-opportunities", detail_table("Opportunity Snapshot", _opportunity_summary_rows(opportunities)))
        + _evidence_panel("mc-market-opportunity-evidence", "Show full opportunity evidence", detail_table("Opportunity Evidence (Full)", opportunities.get("opportunities", [])))
        + _evidence_panel("mc-market-signal-evidence", "Show full signal-surface evidence", detail_table("Signal Surface Evidence (Full)", {
            "pressure": market.get("pressure"),
            "probability": market.get("probability"),
            "velocity": market.get("velocity"),
            "vwap_state": market.get("vwap_state"),
            "spread_quality": market.get("spread_quality"),
            "execution_cost_state": market.get("execution_cost_state"),
        }))
        + '</div>'
    )

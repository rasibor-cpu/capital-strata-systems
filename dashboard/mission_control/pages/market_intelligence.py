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


def _top_opportunity_snapshot(opportunities: dict) -> dict:
    rows = opportunities.get("opportunities")
    if not isinstance(rows, list) or not rows:
        return {
            "opportunity_count": 0,
            "symbol": "UNAVAILABLE",
            "asset_class": "UNAVAILABLE",
            "confidence": "UNAVAILABLE",
            "expected_quality": "UNAVAILABLE",
            "risk": "UNAVAILABLE",
            "blocking_reason": "UNAVAILABLE",
            "committee_outcome": "UNAVAILABLE",
            "ranking": "UNAVAILABLE",
            "freshness": "UNAVAILABLE",
        }
    ranked = [row for row in rows if isinstance(row, dict)]
    if not ranked:
        return {"opportunity_count": 0}
    top = sorted(ranked, key=lambda row: row.get("ranking") if isinstance(row.get("ranking"), (int, float)) else 10**9)[0]
    return {
        "opportunity_count": len(ranked),
        "symbol": top.get("symbol"),
        "asset_class": top.get("asset_class"),
        "confidence": top.get("confidence"),
        "expected_quality": top.get("expected_quality"),
        "risk": top.get("risk"),
        "blocking_reason": top.get("blocking_reason"),
        "committee_outcome": top.get("committee_outcome"),
        "ranking": top.get("ranking"),
        "freshness": top.get("freshness"),
    }


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
        + _anchor_panel("mc-market-opportunities", detail_table("Top Opportunity Snapshot", _top_opportunity_snapshot(opportunities)))
        + _anchor_panel("mc-market-opportunity-ranking", detail_table("Opportunity Ranking", opportunities))
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

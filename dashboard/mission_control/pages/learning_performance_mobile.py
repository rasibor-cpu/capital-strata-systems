from __future__ import annotations

from dashboard.mission_control.pages._components import (
    detail_table,
    metric_grid,
    page_header,
    section,
    warning_banner,
)


def _anchor_panel(anchor: str, content: str) -> str:
    return f'<div class="mc-section-anchor" id="{anchor}">{content}</div>'


def _evidence_panel(anchor: str, title: str, content: str) -> str:
    return (
        f'<div class="mc-section-anchor mc-evidence-disclosure" id="{anchor}">'
        f'<details><summary>{title}</summary>{content}</details>'
        '</div>'
    )


def _count(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def _first_text(value: object, *keys: str) -> str:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            for key in keys:
                candidate = first.get(key)
                if candidate not in (None, ""):
                    return str(candidate)
        if first not in (None, ""):
            return str(first)
    return "NONE RECORDED"


def render(state: dict) -> str:
    learning = section(state, "learning")
    performance = section(state, "performance_panel")
    recommendations = section(state, "recommendation_panel")
    war_room = section(state, "strategy_war_room")
    committee = section(state, "investment_committee")

    return (
        page_header(
            "Learning and Performance",
            "Read-only performance, reliability, attribution, and advisory recommendation summaries.",
        )
        + warning_banner(
            "Historical and simulated results are advisory and not guaranteed live performance.",
            status="warn",
        )
        + '<nav class="mc-page-jump" aria-label="Learning and Performance sections">'
          '<a href="#mc-learning-status">Performance</a>'
          '<a href="#mc-learning-guidance">Guidance</a>'
          '<a href="#mc-learning-committee">Committee</a>'
          '<a href="#mc-learning-evidence">Evidence</a>'
          '</nav>'
        + metric_grid(
            (
                ("Win Rate", learning.get("win_rate"), "neutral"),
                ("Expectancy", learning.get("expectancy"), "neutral"),
                ("Profit Factor", learning.get("profit_factor"), "neutral"),
                ("Drawdown", learning.get("drawdown"), "neutral"),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-learning-priority",
            aria_label="Learning and Performance priority",
        )
        + metric_grid(
            (
                ("Reliability", learning.get("rolling_reliability"), "neutral"),
                ("Decision", recommendations.get("decision"), recommendations.get("decision")),
                ("Blocked Ideas", _count(committee.get("blocked_ideas")), "neutral"),
                ("Execution Controls", recommendations.get("execution_controls"), recommendations.get("execution_controls")),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Learning and Performance secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-learning-status", detail_table("Performance Snapshot", {
            "win_rate": learning.get("win_rate"),
            "expectancy": learning.get("expectancy"),
            "profit_factor": learning.get("profit_factor"),
            "drawdown": learning.get("drawdown"),
            "rolling_reliability": learning.get("rolling_reliability"),
            "historical_results_label": learning.get("historical_results_label"),
        }))
        + _anchor_panel("mc-learning-guidance", detail_table("Guidance Snapshot", {
            "decision": recommendations.get("decision"),
            "recommendation_count": _count(recommendations.get("recommendations")),
            "top_recommendation": _first_text(recommendations.get("recommendations"), "action", "reason"),
            "execution_controls": recommendations.get("execution_controls"),
        }))
        + _anchor_panel("mc-learning-committee", detail_table("Committee Snapshot", {
            "current_decision_count": _count(committee.get("current_decisions")),
            "decision_quality": committee.get("decision_quality"),
            "highest_ranked_idea": _first_text(committee.get("highest_ranked_ideas"), "symbol", "asset_class"),
            "blocked_idea_count": _count(committee.get("blocked_ideas")),
            "capital_recommendation_count": _count(committee.get("capital_recommendations")),
        }))
        + _evidence_panel("mc-learning-evidence", "Show rankings and attribution evidence", detail_table("Rankings", {
            "strategy_rankings": learning.get("strategy_rankings"),
            "asset_class_rankings": learning.get("asset_class_rankings"),
            "symbol_rankings": learning.get("symbol_rankings"),
            "outcome_attribution": learning.get("outcome_attribution"),
        }))
        + _evidence_panel("mc-learning-war-room", "Show strategy war-room evidence", detail_table("Strategy War Room", war_room.get("strategies", [])))
        + _evidence_panel("mc-learning-performance-evidence", "Show performance evidence", detail_table("Performance Panel", {
            "expectancy": performance.get("expectancy"),
            "win_rate": performance.get("win_rate"),
            "average_gain": performance.get("average_gain"),
            "average_loss": performance.get("average_loss"),
            "profit_factor": performance.get("profit_factor"),
            "sharpe": performance.get("sharpe"),
            "capital_efficiency": performance.get("capital_efficiency"),
            "strategy_ranking": performance.get("strategy_ranking"),
            "source": performance.get("source"),
        }))
        + '</div>'
    )


__all__ = ["render"]

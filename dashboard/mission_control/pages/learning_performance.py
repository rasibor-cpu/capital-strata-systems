from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels, warning_banner


def render(state: dict) -> str:
    learning = section(state, "learning")
    performance = section(state, "performance_panel")
    return (
        page_header("Learning and Performance", "Read-only strategy, asset, symbol, attribution, reliability, expectancy, drawdown, and recommendation intelligence.")
        + warning_banner("Historical and simulated results are advisory and not guaranteed live performance.", status="warn")
        + metric_grid(
            (
                ("Win Rate", learning.get("win_rate"), "neutral"),
                ("Expectancy", learning.get("expectancy"), "neutral"),
                ("Profit Factor", learning.get("profit_factor"), "neutral"),
                ("Drawdown", learning.get("drawdown"), "neutral"),
                ("Reliability", learning.get("rolling_reliability"), "neutral"),
            )
        )
        + split_panels(
            detail_table("Rankings", {
                "strategy_rankings": learning.get("strategy_rankings"),
                "asset_class_rankings": learning.get("asset_class_rankings"),
                "symbol_rankings": learning.get("symbol_rankings"),
                "outcome_attribution": learning.get("outcome_attribution"),
            }),
            detail_table("Learning Observations", {
                "premium_capture": learning.get("premium_capture"),
                "capital_efficiency": learning.get("capital_efficiency"),
                "observations": learning.get("learning_observations"),
                "recommendations": learning.get("recommendations"),
                "historical_results_label": learning.get("historical_results_label"),
            }),
            detail_table("Performance Panel", {
                "expectancy": performance.get("expectancy"),
                "win_rate": performance.get("win_rate"),
                "average_gain": performance.get("average_gain"),
                "average_loss": performance.get("average_loss"),
                "profit_factor": performance.get("profit_factor"),
                "sharpe": performance.get("sharpe"),
                "capital_efficiency": performance.get("capital_efficiency"),
                "strategy_ranking": performance.get("strategy_ranking"),
                "source": performance.get("source"),
                "state_hash": performance.get("state_hash"),
            }),
        )
    )

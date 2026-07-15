from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels, warning_banner


def render(state: dict) -> str:
    trading = section(state, "trading")
    return (
        page_header("Trade Operations", "Read-only trade decision, gate, paper position, order, fill, rejection, slippage, and fee visibility.")
        + warning_banner("MC-001 exposes no executable trade tickets and cannot submit or cancel orders.", status="bad")
        + metric_grid(
            (
                ("Execution Status", trading.get("execution_status"), trading.get("execution_status")),
                ("Accepted Decisions", trading.get("accepted_decisions"), "neutral"),
                ("Rejected Decisions", trading.get("rejected_decisions"), "neutral"),
                ("Open Positions", len(trading.get("open_positions", []) or []), "neutral"),
                ("Orders", len(trading.get("orders", []) or []), "neutral"),
                ("Fills", len(trading.get("fills", []) or []), "neutral"),
            )
        )
        + split_panels(
            detail_table("Execution Quality", {
                "slippage": trading.get("slippage"),
                "fees": trading.get("fees"),
                "execution_quality": trading.get("execution_quality"),
                "read_only": trading.get("read_only"),
            }),
            detail_table("Recent Rejections", trading.get("rejections", [])),
        )
    )

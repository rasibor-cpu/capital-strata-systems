from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels, warning_banner


def render(state: dict) -> str:
    trading = section(state, "trading")
    lifecycle = section(state, "trade_lifecycle")
    decision = section(state, "decision_panel")
    trace = section(state, "decision_trace")
    committee = section(state, "execution_committee")
    return (
        page_header("Trade Operations", "Read-only trade decision, gate, paper position, order, fill, rejection, slippage, and fee visibility.")
        + warning_banner("MC-001 exposes no executable trade tickets and cannot submit or cancel orders.", status="bad")
        + metric_grid(
            (
                ("Execution Status", trading.get("execution_status"), trading.get("execution_status")),
                ("Decision Status", decision.get("status"), decision.get("status")),
                ("Accepted Decisions", trading.get("accepted_decisions"), "neutral"),
                ("Rejected Decisions", trading.get("rejected_decisions"), "neutral"),
                ("Open Positions", len(trading.get("open_positions", []) or []), "neutral"),
                ("Orders", len(trading.get("orders", []) or []), "neutral"),
                ("Fills", len(trading.get("fills", []) or []), "neutral"),
            )
        )
        + split_panels(
            detail_table("Decision Panel", {
                "status": decision.get("status"),
                "reason": decision.get("reason"),
                "decisions": decision.get("decisions"),
                "read_only": decision.get("read_only"),
            }),
            detail_table("Decision Trace", trace.get("stages", [])),
            detail_table("Execution Committee", {
                "execution_quality": committee.get("execution_quality"),
                "latency": committee.get("latency"),
                "slippage": committee.get("slippage"),
                "fills": committee.get("fills"),
                "rejects": committee.get("rejects"),
                "broker_quality": committee.get("broker_quality"),
                "routing_quality": committee.get("routing_quality"),
                "controls": committee.get("controls"),
                "links": committee.get("links"),
            }),
            detail_table("Execution Quality", {
                "slippage": trading.get("slippage"),
                "fees": trading.get("fees"),
                "execution_quality": trading.get("execution_quality"),
                "read_only": trading.get("read_only"),
                "source": lifecycle.get("source"),
                "state_hash": lifecycle.get("state_hash"),
            }),
            detail_table("Trade Lifecycle", lifecycle.get("stages", [])),
            detail_table("Lifecycle Events", lifecycle.get("events", [])),
            detail_table("Recent Rejections", trading.get("rejections", [])),
        )
    )

from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, warning_banner


def _anchor_panel(anchor: str, content: str) -> str:
    return f'<div class="mc-section-anchor" id="{anchor}">{content}</div>'


def _metric_status(value: object) -> object:
    return "UNAVAILABLE" if value in (None, "") else value


def render(state: dict) -> str:
    trading = section(state, "trading")
    lifecycle = section(state, "trade_lifecycle")
    decision = section(state, "decision_panel")
    trace = section(state, "decision_trace")
    committee = section(state, "execution_committee")
    balances = section(state, "broker_balance_summary")
    account_values = balances.get("account_summary") if isinstance(balances.get("account_summary"), dict) else {}
    account_context = balances.get("account_context") if isinstance(balances.get("account_context"), dict) else {}
    return (
        page_header("Trade Operations", "Read-only trade decision, gate, paper position, order, fill, rejection, slippage, and fee visibility.")
        + warning_banner("MC-001 exposes no executable trade tickets and cannot submit or cancel orders.", status="bad")
        + '<nav class="mc-page-jump" aria-label="Trade Operations sections">'
          '<a href="#mc-trade-account">Account</a>'
          '<a href="#mc-trade-decisions">Decisions</a>'
          '<a href="#mc-trade-execution">Execution</a>'
          '<a href="#mc-trade-lifecycle">Lifecycle</a>'
          '</nav>'
        + metric_grid(
            (
                ("Execution Status", trading.get("execution_status"), trading.get("execution_status")),
                ("Decision Status", decision.get("status"), decision.get("status")),
                ("Available to Trade", _display_value(account_values.get("available_to_trade")), _metric_status(_display_value(account_values.get("available_to_trade")))),
                ("Open Positions", len(trading.get("open_positions", []) or []), "neutral"),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-trade-priority",
            aria_label="Trade Operations priority",
        )
        + metric_grid(
            (
                ("Account Value", _display_value(account_values.get("total_account_value")), _metric_status(_display_value(account_values.get("total_account_value")))),
                ("Buying Power", _display_value(account_values.get("buying_power")), _metric_status(_display_value(account_values.get("buying_power")))),
                ("Margin Available", _display_value(account_values.get("margin_available")), _metric_status(_display_value(account_values.get("margin_available")))),
                ("Accepted Decisions", trading.get("accepted_decisions"), "neutral"),
                ("Rejected Decisions", trading.get("rejected_decisions"), "neutral"),
                ("Orders", len(trading.get("orders", []) or []), "neutral"),
                ("Fills", len(trading.get("fills", []) or []), "neutral"),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Trade Operations secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-trade-account", detail_table("Account Summary", account_values))
        + _anchor_panel("mc-trade-assets", detail_table("Asset Breakdown", balances.get("asset_breakdown", [])))
        + _anchor_panel("mc-trade-position-value", detail_table("Position Value", balances.get("position_value", {})))
        + _anchor_panel("mc-trade-collateral", detail_table("Collateral / Margin", balances.get("collateral_margin", {})))
        + _anchor_panel("mc-trade-context", detail_table("Account Context", account_context))
        + _anchor_panel("mc-trade-decisions", detail_table("Decision Panel", {
            "status": decision.get("status"),
            "reason": decision.get("reason"),
            "decisions": decision.get("decisions"),
            "read_only": decision.get("read_only"),
        }))
        + _anchor_panel("mc-trade-trace", detail_table("Decision Trace", trace.get("stages", [])))
        + _anchor_panel("mc-trade-execution", detail_table("Execution Committee", {
            "execution_quality": committee.get("execution_quality"),
            "latency": committee.get("latency"),
            "slippage": committee.get("slippage"),
            "fills": committee.get("fills"),
            "rejects": committee.get("rejects"),
            "broker_quality": committee.get("broker_quality"),
            "routing_quality": committee.get("routing_quality"),
            "controls": committee.get("controls"),
            "links": committee.get("links"),
        }))
        + _anchor_panel("mc-trade-quality", detail_table("Execution Quality", {
            "slippage": trading.get("slippage"),
            "fees": trading.get("fees"),
            "execution_quality": trading.get("execution_quality"),
            "read_only": trading.get("read_only"),
            "source": lifecycle.get("source"),
            "state_hash": lifecycle.get("state_hash"),
        }))
        + _anchor_panel("mc-trade-lifecycle", detail_table("Trade Lifecycle", lifecycle.get("stages", [])))
        + _anchor_panel("mc-trade-events", detail_table("Lifecycle Events", lifecycle.get("events", [])))
        + _anchor_panel("mc-trade-rejections", detail_table("Recent Rejections", trading.get("rejections", [])))
        + '</div>'
    )


def _display_value(value: object) -> str:
    row = value if isinstance(value, dict) else {}
    if row.get("availability_state") != "AVAILABLE":
        return "UNAVAILABLE"
    return f"{row.get('value')} {row.get('currency')}"

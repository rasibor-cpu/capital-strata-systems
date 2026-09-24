from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, warning_banner


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


def _decision_snapshot(decision: dict) -> dict:
    decisions = decision.get("decisions")
    latest = decisions[0] if isinstance(decisions, list) and decisions and isinstance(decisions[0], dict) else {}
    return {
        "status": decision.get("status"),
        "reason": decision.get("reason"),
        "symbol": latest.get("symbol"),
        "asset_class": latest.get("asset_class"),
        "decision": latest.get("decision"),
        "quality_score": latest.get("quality_score"),
        "confidence": latest.get("confidence"),
        "generated_at": latest.get("generated_at") or latest.get("generated_timestamp"),
        "freshness": latest.get("freshness"),
        "read_only": decision.get("read_only"),
    }


def _trace_summary_rows(trace: dict) -> list[dict]:
    stages = trace.get("stages")
    if not isinstance(stages, list):
        return []
    rows = []
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        rows.append({
            "stage": stage.get("stage"),
            "status": stage.get("status"),
            "reason": stage.get("reason"),
            "freshness": stage.get("freshness"),
        })
    return rows


def _account_snapshot(account_values: dict) -> dict:
    return {
        "account_value": _display_value(account_values.get("total_account_value")),
        "cash": _display_value(account_values.get("cash")),
        "available_to_trade": _display_value(account_values.get("available_to_trade")),
        "buying_power": _display_value(account_values.get("buying_power")),
        "margin_available": _display_value(account_values.get("margin_available")),
        "unrealized_pnl": _display_value(account_values.get("unrealized_pnl")),
        "realized_pnl": _display_value(account_values.get("realized_pnl")),
        "total_pnl": _display_value(account_values.get("total_pnl")),
    }


def _margin_snapshot(collateral_margin: object) -> dict:
    margin = collateral_margin if isinstance(collateral_margin, dict) else {}
    return {
        "margin_state": margin.get("margin_state"),
        "available_collateral": _display_value(margin.get("available_collateral")),
        "free_margin": _display_value(margin.get("free_margin")),
        "required_collateral": _display_value(margin.get("required_collateral")),
        "used_margin": _display_value(margin.get("used_margin")),
        "utilization_pct": _display_value(margin.get("utilization_pct")),
        "closeout_percentage": _display_value(margin.get("closeout_percentage")),
    }


def _position_snapshot(position_value: object) -> dict:
    positions = position_value if isinstance(position_value, dict) else {}
    preferred = ("EQUITIES", "CRYPTO", "FX", "OPTIONS", "FUTURES", "TOTAL_INVESTED_VALUE")
    return {key.lower(): _display_value(positions.get(key)) for key in preferred}


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
                ("Available to Trade", _display_value(account_values.get("available_to_trade")), _display_status(account_values.get("available_to_trade"))),
                ("Open Positions", len(trading.get("open_positions", []) or []), "neutral"),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-trade-priority",
            aria_label="Trade Operations priority",
        )
        + metric_grid(
            (
                ("Account Value", _display_value(account_values.get("total_account_value")), _display_status(account_values.get("total_account_value"))),
                ("Buying Power", _display_value(account_values.get("buying_power")), _display_status(account_values.get("buying_power"))),
                ("Margin Available", _display_value(account_values.get("margin_available")), _display_status(account_values.get("margin_available"))),
                ("Accepted Decisions", trading.get("accepted_decisions"), "neutral"),
                ("Rejected Decisions", trading.get("rejected_decisions"), "neutral"),
                ("Orders", len(trading.get("orders", []) or []), "neutral"),
                ("Fills", len(trading.get("fills", []) or []), "neutral"),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Trade Operations secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-trade-account", detail_table("Account Snapshot", _account_snapshot(account_values)))
        + _anchor_panel("mc-trade-margin-summary", detail_table("Margin Snapshot", _margin_snapshot(balances.get("collateral_margin", {}))))
        + _anchor_panel("mc-trade-context", detail_table("Account Context", account_context))
        + _anchor_panel("mc-trade-position-summary", detail_table("Position Snapshot", _position_snapshot(balances.get("position_value", {}))))
        + _evidence_panel("mc-trade-account-evidence", "Show full account evidence", detail_table("Account Evidence (Full)", account_values))
        + _evidence_panel("mc-trade-assets", "Show full asset-breakdown evidence", detail_table("Asset Breakdown Evidence (Full)", balances.get("asset_breakdown", [])))
        + _evidence_panel("mc-trade-position-value", "Show full position-value evidence", detail_table("Position Value Evidence (Full)", balances.get("position_value", {})))
        + _evidence_panel("mc-trade-collateral", "Show full collateral / margin evidence", detail_table("Collateral / Margin Evidence (Full)", balances.get("collateral_margin", {})))
        + _anchor_panel("mc-trade-decisions", detail_table("Decision Snapshot", _decision_snapshot(decision)))
        + _anchor_panel("mc-trade-trace-summary", detail_table("Decision Trace Summary", _trace_summary_rows(trace)))
        + _evidence_panel("mc-trade-trace", "Show full decision trace evidence", detail_table("Decision Trace Evidence (Full)", trace.get("stages", [])))
        + _evidence_panel("mc-trade-decision-evidence", "Show full decision evidence", detail_table("Decision Evidence (Full)", {
            "decisions": decision.get("decisions"),
            "read_only": decision.get("read_only"),
        }))
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
    amount = row.get("value")
    currency = str(row.get("currency") or "").strip()
    if currency and currency.upper() != "UNAVAILABLE":
        return f"{amount} {currency}"
    return str(amount) if amount not in (None, "") else "UNAVAILABLE"


def _display_status(value: object) -> str:
    row = value if isinstance(value, dict) else {}
    if row.get("availability_state") != "AVAILABLE":
        return "UNAVAILABLE"
    currency = str(row.get("currency") or "").strip().upper()
    freshness = str(row.get("freshness") or "").strip().upper()
    if currency in {"", "UNAVAILABLE"} or freshness in {"", "UNAVAILABLE", "STALE"}:
        return "WARNING"
    return "AVAILABLE"

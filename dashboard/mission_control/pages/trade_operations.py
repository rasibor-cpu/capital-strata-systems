from __future__ import annotations

from html import escape

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


def _execution_snapshot(trading: dict, committee: dict) -> dict:
    routing = committee.get("routing_quality")
    routing_quality = routing.get("quality") if isinstance(routing, dict) else routing
    return {
        "execution_status": trading.get("execution_status"),
        "execution_quality": committee.get("execution_quality") or trading.get("execution_quality"),
        "latency": committee.get("latency"),
        "slippage": committee.get("slippage") or trading.get("slippage"),
        "fees": trading.get("fees"),
        "routing_quality": routing_quality,
        "controls": committee.get("controls"),
        "fills": len(trading.get("fills", []) or []),
        "rejections": len(trading.get("rejections", []) or []),
    }


def _lifecycle_summary_rows(lifecycle: dict) -> list[dict]:
    stages = lifecycle.get("stages")
    if not isinstance(stages, list):
        return []
    rows = []
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        rows.append({
            "stage": stage.get("stage"),
            "count": stage.get("count"),
            "freshness": stage.get("freshness"),
        })
    return rows



def _trade_ticket(state: dict) -> str:
    brokers = section(state, "brokers")
    selection = brokers.get("operator_selection") if isinstance(brokers.get("operator_selection"), dict) else {}
    active = brokers.get("active_broker") if isinstance(brokers.get("active_broker"), dict) else {}
    broker = str(selection.get("selected_broker") or active.get("selected_broker") or "").strip().upper()
    confirmed = bool(selection.get("confirmed"))
    broker_label = escape(broker or "NO CONFIRMED BROKER")
    disabled = "" if broker and confirmed else " disabled"
    broker_warning = (
        ""
        if broker and confirmed
        else '<p class="mc-warning bad">Select and confirm an available broker in Broker Management before submitting a trade request.</p>'
    )
    return (
        '<section class="mc-panel mc-section-anchor" id="mc-trade-ticket">'
        '<h2>Transaction / Trade Ticket</h2>'
        '<p class="mc-muted">Complete the transaction fields below. Until CSS production execution is separately certified, this submits a controlled paper/preview trade request only.</p>'
        + broker_warning
        + '<form id="mc-trade-ticket-form" class="mc-filter-form">'
        '<label>Broker<input name="broker" value="' + broker_label + '" readonly></label>'
        '<label>Asset class<select name="asset_class" required>'
        '<option value="">Select</option><option value="EQUITIES">Equities / ETFs</option>'
        '<option value="CRYPTO">Crypto</option><option value="FX">FX</option>'
        '<option value="FUTURES">Futures</option><option value="OPTIONS">Options</option>'
        '<option value="DERIVATIVES">Other derivatives</option></select></label>'
        '<label>Instrument<input name="instrument" placeholder="e.g. AAPL, EURUSD, BTC-USD" required></label>'
        '<label>Side<select name="side" required><option value="">Select</option><option value="BUY">Buy</option><option value="SELL">Sell</option></select></label>'
        '<label>Amount<input name="amount" inputmode="decimal" placeholder="Transaction amount"></label>'
        '<label>Quantity<input name="quantity" inputmode="decimal" value="1" required></label>'
        '<label>Currency<input name="currency" value="USD" maxlength="8"></label>'
        '<label>Tenor<input name="tenor" placeholder="e.g. Spot, 1M, Dec-26"></label>'
        '<label>Rate / Price<input name="rate" inputmode="decimal" placeholder="Optional for market order"></label>'
        '<label>Order type<select name="order_type"><option value="MARKET">Market</option><option value="LIMIT">Limit</option><option value="STOP">Stop</option></select></label>'
        '<label>Value date<input name="value_date" type="date"></label>'
        '<label>Settlement date<input name="settlement_date" type="date"></label>'
        '<label>Time in force<select name="time_in_force"><option value="DAY">Day</option><option value="GTC">Good till cancelled</option><option value="IOC">Immediate or cancel</option></select></label>'
        '<label>Notes<input name="notes" maxlength="500" placeholder="Optional transaction notes"></label>'
        '<input type="hidden" name="paper_only" value="true">'
        '<input type="hidden" name="broker_execution_allowed" value="false">'
        '<label class="mc-confirm-choice"><input type="checkbox" name="confirm_trade" value="YES" required> '
        'I confirm the broker and transaction details shown above.</label>'
        '<button type="submit"' + disabled + '>Submit Trade Request</button>'
        '</form>'
        '<p id="mc-trade-ticket-result" class="mc-muted" aria-live="polite"></p>'
        '<p class="mc-muted"><a href="/mission-control/broker-management">Change / confirm broker</a> · '
        '<a href="/mission-control/transaction-history">Transaction history &amp; receipts</a></p>'
        '<script>'
        "document.getElementById('mc-trade-ticket-form')?.addEventListener('submit', async (ev) => {"
        "ev.preventDefault(); const out=document.getElementById('mc-trade-ticket-result');"
        "const body=new URLSearchParams(new FormData(ev.currentTarget));"
        "try { const response=await fetch('/operator-trade/request',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest'},body});"
        "const data=await response.json(); if(!response.ok) throw new Error(data.detail||data.error||'Trade request failed');"
        "out.textContent='Trade request recorded. Current CSS execution remains paper/preview only.';"
        "} catch(err){out.textContent=String(err.message||err);} });"
        '</script></section>'
    )



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
        page_header("Trade / Transaction", "Transaction entry plus trade decision, gate, position, order, fill, rejection, slippage, and fee visibility.")
        + warning_banner("Trade ticket entry is enabled for controlled paper/preview requests. Live broker execution remains blocked until separately certified.", status="warn")
        + '<nav class="mc-page-jump" aria-label="Trade Operations sections">'
          '<a href="#mc-trade-ticket">Trade Ticket</a>'
          '<a href="#mc-trade-account">Account</a>'
          '<a href="#mc-trade-decisions">Decisions</a>'
          '<a href="#mc-trade-execution">Execution</a>'
          '<a href="#mc-trade-lifecycle">Lifecycle</a>'
          '</nav>'
        + _trade_ticket(state)
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
        + _anchor_panel("mc-trade-decision-panel", detail_table("Decision Panel", decision))
        + _anchor_panel("mc-trade-decisions", detail_table("Decision Snapshot", _decision_snapshot(decision)))
        + _anchor_panel("mc-trade-decision-trace", detail_table("Decision Trace", trace))
        + _anchor_panel("mc-trade-trace-summary", detail_table("Decision Trace Summary", _trace_summary_rows(trace)))
        + _evidence_panel("mc-trade-trace", "Show full decision trace evidence", detail_table("Decision Trace Evidence (Full)", trace.get("stages", [])))
        + _evidence_panel("mc-trade-decision-evidence", "Show full decision evidence", detail_table("Decision Evidence (Full)", {
            "decisions": decision.get("decisions"),
            "read_only": decision.get("read_only"),
        }))
        + _anchor_panel("mc-trade-execution", detail_table("Execution Snapshot", _execution_snapshot(trading, committee)))
        + _anchor_panel("mc-trade-lifecycle", detail_table("Lifecycle Summary", _lifecycle_summary_rows(lifecycle)))
        + _evidence_panel("mc-trade-execution-evidence", "Show full execution committee evidence", detail_table("Execution Committee Evidence (Full)", {
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
        + _evidence_panel("mc-trade-quality", "Show full execution-quality evidence", detail_table("Execution Quality Evidence (Full)", {
            "slippage": trading.get("slippage"),
            "fees": trading.get("fees"),
            "execution_quality": trading.get("execution_quality"),
            "read_only": trading.get("read_only"),
            "source": lifecycle.get("source"),
            "state_hash": lifecycle.get("state_hash"),
        }))
        + _evidence_panel("mc-trade-lifecycle-evidence", "Show full lifecycle evidence", detail_table("Trade Lifecycle Evidence (Full)", lifecycle.get("stages", [])))
        + _evidence_panel("mc-trade-events", "Show lifecycle events", detail_table("Lifecycle Events", lifecycle.get("events", [])))
        + _evidence_panel("mc-trade-rejections", "Show recent rejections", detail_table("Recent Rejections", trading.get("rejections", [])))
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

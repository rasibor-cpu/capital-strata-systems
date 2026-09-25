from __future__ import annotations

from html import escape

from dashboard.mission_control.pages._components import (
    metric_grid,
    page_header,
    warning_banner,
)


def _value(row: dict, key: str, fallback: str = "—") -> str:
    value = row.get(key)
    return fallback if value in (None, "") else str(value)


def _history_table(rows: object) -> str:
    if not isinstance(rows, list) or not rows:
        return '<section class="mc-panel"><h2>Transactions</h2><p class="mc-muted">No persisted transaction history is currently available.</p></section>'

    rendered: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        trade_id = _value(row, "trade_id", "UNAVAILABLE")
        receipt_href = f"/mission-control/transaction-receipt/{escape(trade_id, quote=True)}"
        rendered.append(
            "<tr>"
            f"<td>{escape(_value(row, 'opened_at'))}</td>"
            f"<td>{escape(_value(row, 'symbol'))}</td>"
            f"<td>{escape(_value(row, 'direction'))}</td>"
            f"<td>{escape(_value(row, 'quantity'))}</td>"
            f"<td>{escape(_value(row, 'broker_name'))}</td>"
            f"<td>{escape(_value(row, 'broker_mode'))}</td>"
            f"<td>{escape(_value(row, 'status'))}</td>"
            f"<td>{escape(_value(row, 'realized_pnl'))}</td>"
            f'<td><a class="mc-inline-action" href="{receipt_href}">View / Print</a></td>'
            "</tr>"
        )
    return (
        '<section class="mc-panel mc-section-anchor" id="mc-transaction-history">'
        "<h2>Transaction History</h2>"
        '<div class="mc-table-wrap"><table>'
        "<thead><tr><th>Opened</th><th>Symbol</th><th>Side</th><th>Qty</th>"
        "<th>Broker</th><th>Mode</th><th>Status</th><th>Realized P&amp;L</th><th>Receipt</th></tr></thead>"
        f"<tbody>{''.join(rendered)}</tbody></table></div></section>"
    )


def render(state: dict) -> str:
    history = state.get("transaction_history") if isinstance(state.get("transaction_history"), dict) else {}
    rows = history.get("transactions") if isinstance(history.get("transactions"), list) else []
    closed = sum(1 for row in rows if isinstance(row, dict) and str(row.get("status", "")).lower() == "closed")
    open_count = sum(
        1
        for row in rows
        if isinstance(row, dict)
        and str(row.get("status", "")).lower() in {"open", "pending", "partially_filled"}
    )

    return (
        page_header(
            "Transaction History",
            "Read-only persisted trade history with printable transaction receipts and snapshots.",
        )
        + warning_banner(
            "History is evidence/reporting only. Viewing or printing a transaction does not submit, modify, cancel, or repeat an order.",
            status="warn",
        )
        + '<nav class="mc-page-jump" aria-label="Transaction History sections">'
          '<a href="#mc-transaction-history">History</a>'
          '<button class="mc-inline-button" type="button" onclick="window.print()">Print History</button>'
          '</nav>'
        + metric_grid(
            (
                ("Visible Transactions", len(rows), "neutral"),
                ("Closed", closed, "neutral"),
                ("Open / Pending", open_count, "neutral"),
                ("Execution", "BLOCKED", "blocked"),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority",
            aria_label="Transaction history summary",
        )
        + _history_table(rows)
    )


__all__ = ["render"]

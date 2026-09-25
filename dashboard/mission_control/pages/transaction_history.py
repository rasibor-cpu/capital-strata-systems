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


def _filter_form(history: dict) -> str:
    period = escape(str(history.get("period") or "all"), quote=True)
    entry_type = escape(str(history.get("entry_type") or "ALL"), quote=True)
    date_basis = escape(str(history.get("date_basis") or "transaction"), quote=True)
    date_from = escape(str(history.get("date_from") or ""), quote=True)
    date_to = escape(str(history.get("date_to") or ""), quote=True)
    return f"""
<section class="mc-panel">
  <h2>Statement Filters</h2>
  <form class="mc-filter-form" method="get" action="/mission-control/transaction-history">
    <label>Period
      <select name="period">
        <option value="all"{" selected" if period == "all" else ""}>All</option>
        <option value="daily"{" selected" if period == "daily" else ""}>Daily</option>
        <option value="weekly"{" selected" if period == "weekly" else ""}>Weekly</option>
        <option value="monthly"{" selected" if period == "monthly" else ""}>Monthly</option>
        <option value="annual"{" selected" if period == "annual" else ""}>Annual</option>
        <option value="custom"{" selected" if period == "custom" else ""}>Defined period</option>
      </select>
    </label>
    <label>Entry type
      <select name="entry_type">
        <option value="ALL"{" selected" if entry_type == "ALL" else ""}>All</option>
        <option value="DEBIT"{" selected" if entry_type == "DEBIT" else ""}>Debits</option>
        <option value="CREDIT"{" selected" if entry_type == "CREDIT" else ""}>Credits</option>
      </select>
    </label>
    <label>Date basis
      <select name="date_basis">
        <option value="transaction"{" selected" if date_basis == "transaction" else ""}>Transaction date</option>
        <option value="value"{" selected" if date_basis == "value" else ""}>Value date</option>
        <option value="settlement"{" selected" if date_basis == "settlement" else ""}>Settlement date</option>
      </select>
    </label>
    <label>From <input type="date" name="date_from" value="{date_from}"></label>
    <label>To <input type="date" name="date_to" value="{date_to}"></label>
    <button type="submit">Generate Statement</button>
  </form>
  <p class="mc-muted">Defined periods use the selected date basis. Daily, weekly, monthly and annual periods are generated to the current date.</p>
</section>
"""


def _history_table(rows: object) -> str:
    if not isinstance(rows, list) or not rows:
        return '<section class="mc-panel"><h2>Transactions</h2><p class="mc-muted">No account ledger entries match the selected period and filters.</p></section>'

    rendered: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ledger_id = _value(row, "ledger_id", _value(row, "trade_id", "UNAVAILABLE"))
        receipt_href = f"/mission-control/transaction-receipt/{escape(ledger_id, quote=True)}"
        rendered.append(
            "<tr>"
            f"<td>{escape(_value(row, 'transaction_date', _value(row, 'opened_at')))}</td>"
            f"<td>{escape(_value(row, 'value_date'))}</td>"
            f"<td>{escape(_value(row, 'settlement_date'))}</td>"
            f"<td>{escape(_value(row, 'entry_type', _value(row, 'direction')))}</td>"
            f"<td>{escape(_value(row, 'amount', _value(row, 'realized_pnl')))}</td>"
            f"<td>{escape(_value(row, 'currency'))}</td>"
            f"<td>{escape(_value(row, 'description', _value(row, 'symbol')))}</td>"
            f"<td>{escape(_value(row, 'reference', ledger_id))}</td>"
            f'<td><a class="mc-inline-action" href="{receipt_href}">Generate Receipt</a></td>'
            "</tr>"
        )
    return (
        '<section class="mc-panel mc-section-anchor" id="mc-transaction-history">'
        "<h2>Transaction History</h2>"
        '<div class="mc-table-wrap"><table>'
        "<thead><tr><th>Transaction Date</th><th>Value Date</th><th>Settlement Date</th>"
        "<th>Debit / Credit</th><th>Amount</th><th>Currency</th><th>Description</th><th>Reference</th><th>Receipt</th></tr></thead>"
        f"<tbody>{''.join(rendered)}</tbody></table></div></section>"
    )


def render(state: dict) -> str:
    history = state.get("transaction_history") if isinstance(state.get("transaction_history"), dict) else {}
    rows = history.get("transactions") if isinstance(history.get("transactions"), list) else []
    return (
        page_header(
            "Transaction History",
            "User account statement and transaction history by period, debit/credit classification, value date, or settlement date.",
        )
        + warning_banner(
            "Statements and receipts are reporting evidence only. Viewing, filtering, exporting, or printing does not submit, modify, cancel, or repeat an order.",
            status="warn",
        )
        + '<nav class="mc-page-jump" aria-label="Transaction History sections">'
          '<a href="#mc-transaction-history">History</a>'
          '<button class="mc-inline-button" type="button" onclick="window.print()">Print Statement</button>'
          '<a class="mc-inline-action" href="/mission-control/transaction-history.csv">Download CSV</a>'
          '</nav>'
        + metric_grid(
            (
                ("Transactions", history.get("transaction_count", len(rows)), "neutral"),
                ("Debits", history.get("debit_total", "0"), "neutral"),
                ("Credits", history.get("credit_total", "0"), "neutral"),
                ("Net Movement", history.get("net_movement", "0"), "neutral"),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority",
            aria_label="Transaction history summary",
        )
        + _filter_form(history)
        + _history_table(rows)
    )


__all__ = ["render"]

from engine.domain.executions import ExecutionReport


def _safe(v) -> str:
    return "" if v is None else str(v)


def format_trade_ticket(r: ExecutionReport) -> str:
    """
    Printer-friendly single trade ticket.
    """
    sort_or_routing = _safe(r.settlement_sort_code) or _safe(r.settlement_routing_code)
    swift_or_iban = _safe(r.settlement_swift_bic) or _safe(r.settlement_iban)

    lines = [
        "TRADE TICKET",
        "=" * 60,
        f"Execution ID        : {_safe(r.execution_id)}",
        f"Order ID            : {_safe(r.order_id)}",
        f"Status              : {_safe(r.status)}",
        f"Broker              : {_safe(r.broker_name)}",
        f"Paper Trade         : {_safe(r.is_paper)}",
        "-" * 60,
        f"User                : {_safe(r.user_id)}",
        f"Company / Branch     : {_safe(r.company_id)} / {_safe(r.branch_id)}",
        f"Department          : {_safe(r.department_id)}",
        "-" * 60,
        f"Instrument          : {_safe(r.symbol)}",
        f"Side                : {_safe(r.side)}",
        f"Quantity (filled)   : {_safe(r.filled_qty)}",
        f"Fill Price          : {_safe(r.fill_price)}",
        f"Gross Amount        : {r.gross_amount:.2f} {_safe(r.currency)}",
        "-" * 60,
        f"Commission Rate (%) : {r.commission_rate_pct:.6f}",
        f"Brokerage Commission: {r.brokerage_commission:.2f}",
        f"Tax Rate (%)        : {r.tax_rate_pct:.6f}",
        f"Tax Amount          : {r.tax_amount:.2f}",
        f"Total Fees & Taxes  : {r.total_fees_and_taxes:.2f}",
        f"Net Amount          : {r.net_amount:.2f} {_safe(r.currency)}",
        "-" * 60,
        f"Order Date          : {_safe(r.order_date)}",
        f"Requested Exec Date : {_safe(r.requested_exec_date)}",
        f"Execution Date      : {_safe(r.execution_date)}",
        f"Settlement Date     : {_safe(r.settlement_date)}",
        "-" * 60,
        "COUNTERPARTY",
        "-" * 60,
        f"Counterparty Name   : {_safe(r.counterparty_name)}",
        f"Counterparty ID     : {_safe(r.counterparty_id)}",
        f"Counterparty Account: {_safe(r.counterparty_account)}",
        "-" * 60,
        "SETTLEMENT DETAILS",
        "-" * 60,
        f"Financial Inst (FI) : {_safe(r.fi_name)}",
        f"FI ID               : {_safe(r.fi_id)}",
        f"FI Branch           : {_safe(r.fi_branch_name)}",
        f"FI Branch ID        : {_safe(r.fi_branch_id)}",
        f"Settlement Currency : {_safe(r.settlement_currency) or _safe(r.currency)}",
        f"Account Name        : {_safe(r.settlement_account_name)}",
        f"Account Number      : {_safe(r.settlement_account_number)}",
        f"Sort / Routing Code : {sort_or_routing}",
        f"SWIFT / IBAN        : {swift_or_iban}",
        f"Settlement Ref      : {_safe(r.settlement_reference)}",
        "-" * 60,
        f"Fee Schedule        : {_safe(r.fee_schedule_id)} v{_safe(r.fee_schedule_version)}",
        "=" * 60,
        "",
    ]

    return "\n".join(lines)


from engine.domain.executions import ExecutionReport


def _safe(v) -> str:
    return "" if v is None else str(v)


def format_trade_ticket(r: ExecutionReport) -> str:
    """
    Printer-friendly single trade ticket.
    """
    sort_or_routing = _safe(r.settlement_sort_code) or _safe(r.settlement_routing_code)
    swift_or_iban = _safe(r.settlement_swift_bic) or _safe(r.settlement_iban)

    lines = [
        "TRADE TICKET",
        "=" * 60,
        f"Execution ID        : {_safe(r.execution_id)}",
        f"Order ID            : {_safe(r.order_id)}",
        f"Status              : {_safe(r.status)}",
        f"Broker              : {_safe(r.broker_name)}",
        f"Paper Trade         : {_safe(r.is_paper)}",
        "-" * 60,
        f"User                : {_safe(r.user_id)}",
        f"Company / Branch     : {_safe(r.company_id)} / {_safe(r.branch_id)}",
        f"Department          : {_safe(r.department_id)}",
        "-" * 60,
        f"Instrument          : {_safe(r.symbol)}",
        f"Side                : {_safe(r.side)}",
        f"Quantity (filled)   : {_safe(r.filled_qty)}",
        f"Fill Price          : {_safe(r.fill_price)}",
        f"Gross Amount        : {r.gross_amount:.2f} {_safe(r.currency)}",
        "-" * 60,
        f"Commission Rate (%) : {r.commission_rate_pct:.6f}",
        f"Brokerage Commission: {r.brokerage_commission:.2f}",
        f"Tax Rate (%)        : {r.tax_rate_pct:.6f}",
        f"Tax Amount          : {r.tax_amount:.2f}",
        f"Total Fees & Taxes  : {r.total_fees_and_taxes:.2f}",
        f"Net Amount          : {r.net_amount:.2f} {_safe(r.currency)}",
        "-" * 60,
        f"Order Date          : {_safe(r.order_date)}",
        f"Requested Exec Date : {_safe(r.requested_exec_date)}",
        f"Execution Date      : {_safe(r.execution_date)}",
        f"Settlement Date     : {_safe(r.settlement_date)}",
        "-" * 60,
        "COUNTERPARTY",
        "-" * 60,
        f"Counterparty Name   : {_safe(r.counterparty_name)}",
        f"Counterparty ID     : {_safe(r.counterparty_id)}",
        f"Counterparty Account: {_safe(r.counterparty_account)}",
        "-" * 60,
        "SETTLEMENT DETAILS",
        "-" * 60,
        f"Financial Inst (FI) : {_safe(r.fi_name)}",
        f"FI ID               : {_safe(r.fi_id)}",
        f"FI Branch           : {_safe(r.fi_branch_name)}",
        f"FI Branch ID        : {_safe(r.fi_branch_id)}",
        f"Settlement Currency : {_safe(r.settlement_currency) or _safe(r.currency)}",
        f"Account Name        : {_safe(r.settlement_account_name)}",
        f"Account Number      : {_safe(r.settlement_account_number)}",
        f"Sort / Routing Code : {sort_or_routing}",
        f"SWIFT / IBAN        : {swift_or_iban}",
        f"Settlement Ref      : {_safe(r.settlement_reference)}",
        "-" * 60,
        f"Fee Schedule        : {_safe(r.fee_schedule_id)} v{_safe(r.fee_schedule_version)}",
        "=" * 60,
        "",
    ]

    return "\n".join(lines)

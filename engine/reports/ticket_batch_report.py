from typing import List, Dict, Tuple
from engine.domain.executions import ExecutionReport
from engine.reports.ticket_formatter import format_trade_ticket


GroupKey = Tuple[str, str, str, str]  # fi_id, fi_branch_id, settlement_account_number, currency


def _safe(v) -> str:
    return "" if v is None else str(v)


def _group_key(r: ExecutionReport) -> GroupKey:
    currency = _safe(r.settlement_currency) or _safe(r.currency)
    return (
        _safe(r.fi_id),
        _safe(r.fi_branch_id),
        _safe(r.settlement_account_number),
        currency
    )


def generate_settlement_packs(reports: List[ExecutionReport]) -> Dict[GroupKey, str]:
    """
    Aggregates trade tickets into settlement packs by:
      FI → FI Branch → Settlement Account → Currency
    Returns dict[group_key] = printable text pack.
    """
    grouped: Dict[GroupKey, List[ExecutionReport]] = {}

    for r in reports:
        key = _group_key(r)
        grouped.setdefault(key, []).append(r)

    packs: Dict[GroupKey, str] = {}

    for key, items in grouped.items():
        fi_id, fi_branch_id, acct_no, currency = key

        fi_name = _safe(items[0].fi_name)
        fi_branch_name = _safe(items[0].fi_branch_name)
        acct_name = _safe(items[0].settlement_account_name)

        total_gross = 0.0
        total_comm = 0.0
        total_tax = 0.0
        total_net = 0.0

        header = []
        header.append("EOD SETTLEMENT PACK")
        header.append("=" * 80)
        header.append(f"FI               : {fi_name} (ID: {fi_id})")
        header.append(f"FI Branch        : {fi_branch_name} (ID: {fi_branch_id})")
        header.append(f"Settlement Acct  : {acct_name} / {acct_no}")
        header.append(f"Currency         : {currency}")
        header.append(f"Trades in pack   : {len(items)}")
        header.append("-" * 80)
        header.append("")

        body = []
        for r in items:
            total_gross += float(r.gross_amount or 0.0)
            total_comm += float(r.brokerage_commission or 0.0)
            total_tax += float(r.tax_amount or 0.0)
            total_net += float(r.net_amount or 0.0)

            body.append(format_trade_ticket(r))
            body.append("-" * 80)

        footer = []
        footer.append("")
        footer.append("PACK TOTALS")
        footer.append("-" * 80)
        footer.append(f"Total Gross      : {total_gross:.2f} {currency}")
        footer.append(f"Total Commission : {total_comm:.2f} {currency}")
        footer.append(f"Total Tax        : {total_tax:.2f} {currency}")
        footer.append(f"Total Net        : {total_net:.2f} {currency}")
        footer.append("=" * 80)
        footer.append("")

        packs[key] = "\n".join(header + body + footer)

    return packs
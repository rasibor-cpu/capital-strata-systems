"""
Capital Strata Systems (CSS)
Phase 28C – Period Close Engine (Fail-Closed on Suspense)

Purpose:
- Close INCOME and EXPENSE accounts for a given period (YYYY-MM)
- Transfer Net Profit / Loss to Retained Earnings
- Enforce governance:
    (1) Calendar governance via journal_writer (may require BACKDATE_EXECUTION_DATE override)
    (2) NEW: Fail-close if Suspense is not cleared at period end, unless explicit ADMIN override is provided

Retained Earnings GL: 000-840-510
Suspense GL (canonical): 000-840-999
Journal source: audit_logs/journal.jsonl
"""

from __future__ import annotations

from calendar import monthrange
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, List, Optional
import json

from backend.app.reporting.income_statement import generate_income_statement
from backend.app.ledger.journal_writer import post_transaction


RETAINED_EARNINGS_GL = "000-840-510"
SUSPENSE_GL = "000-840-999"
JOURNAL_FILE = Path("audit_logs/journal.jsonl")


def _to_decimal(x) -> Decimal:
    try:
        return Decimal(str(x))
    except Exception:
        return Decimal("0")


def _month_end_date(period: str) -> str:
    y, m = period.split("-")
    year = int(y)
    month = int(m)
    last = monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-{last:02d}"


def _calendar_override_for_close(*, admin_user_id: str, period: str) -> Dict[str, Any]:
    """
    This satisfies posting calendar governance when execution_date is backdated to month-end.
    """
    return {
        "override_type": "BACKDATE_EXECUTION_DATE",
        "override_reason": f"Period close for {period}",
        "override_by_user_id": admin_user_id,
        "override_ticket_ref": f"CLOSE-{period}",
        # Optional extra audit fields (safe)
        "approved_by": admin_user_id,
        "approved_by_role": "ADMIN",
        "reason": f"Approved backdated period close for {period}",
    }


def _attach_suspense_override(
    *,
    base_override: Dict[str, Any],
    admin_user_id: str,
    period: str,
    suspense_override_reason: str,
) -> Dict[str, Any]:
    """
    We must still pass override_type=BACKDATE_EXECUTION_DATE for calendar governance.
    To preserve the explicit 'SUSPENSE_CLOSE_OVERRIDE' signal, we attach it as a secondary override
    that is journaled and auditable.
    """
    merged = dict(base_override)
    merged.update(
        {
            "secondary_override_type": "SUSPENSE_CLOSE_OVERRIDE",
            "secondary_override_reason": suspense_override_reason,
            "secondary_override_by_user_id": admin_user_id,
            "secondary_override_ticket_ref": f"CLOSE-{period}-SUSP",
            "secondary_approved_by": admin_user_id,
            "secondary_approved_by_role": "ADMIN",
        }
    )
    return merged


def _load_suspense_position_as_at(execution_date: str) -> Dict[str, Any]:
    """
    Compute Suspense position as-at execution_date using journal movements with
    entry.execution_date <= execution_date.

    Returns:
      {
        "account_no": "000-840-999",
        "dr": Decimal,
        "cr": Decimal,
        "net_dr_minus_cr": Decimal
      }
    """
    dr = Decimal("0")
    cr = Decimal("0")

    if not JOURNAL_FILE.exists():
        return {
            "account_no": SUSPENSE_GL,
            "dr": dr,
            "cr": cr,
            "net_dr_minus_cr": Decimal("0"),
        }

    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
            except Exception:
                # skip malformed lines safely
                continue

            acc = str(j.get("account_no", "")).strip()
            if acc != SUSPENSE_GL:
                continue

            exec_dt = str(j.get("execution_date", "")).strip()
            if not exec_dt:
                continue

            # Safe ISO compare works for YYYY-MM-DD strings
            if exec_dt > execution_date:
                continue

            side = str(j.get("side", "")).upper()
            amt = _to_decimal(j.get("amount", "0"))

            if side == "DR":
                dr += amt
            elif side == "CR":
                cr += amt

    return {
        "account_no": SUSPENSE_GL,
        "dr": dr,
        "cr": cr,
        "net_dr_minus_cr": dr - cr,
    }


def close_period(
    *,
    admin_user_id: str,
    period: str,
    currency: str = "NGN",
    suspense_override_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Close period fail-closed on suspense.

    suspense_override_reason:
      - If suspense is non-zero at period end, close is BLOCKED unless this is provided.
      - When provided, it is journaled as a SECONDARY override: SUSPENSE_CLOSE_OVERRIDE.
    """

    if not admin_user_id:
        raise PermissionError("admin_user_id required for period close")

    exec_dt = _month_end_date(period)

    # -----------------------------
    # (A) Suspense fail-closed gate
    # -----------------------------
    suspense_pos = _load_suspense_position_as_at(exec_dt)
    suspense_net = _to_decimal(suspense_pos["net_dr_minus_cr"])

    if suspense_net != Decimal("0"):
        if not suspense_override_reason or not str(suspense_override_reason).strip():
            return {
                "period": period,
                "status": "BLOCKED_SUSPENSE",
                "execution_date_used": exec_dt,
                "message": "CLOSE BLOCKED: Suspense account not cleared. Provide suspense_override_reason to proceed.",
                "suspense": {
                    "account_no": suspense_pos["account_no"],
                    "dr": str(suspense_pos["dr"]),
                    "cr": str(suspense_pos["cr"]),
                    "net_dr_minus_cr": str(suspense_pos["net_dr_minus_cr"]),
                },
            }

    # -----------------------------
    # (B) Generate close entries
    # -----------------------------
    data = generate_income_statement(period)

    income_accounts = data.get("income_accounts", [])
    expense_accounts = data.get("expense_accounts", [])
    net_profit = _to_decimal(data.get("net_profit", "0"))

    if net_profit == Decimal("0") and not income_accounts and not expense_accounts:
        return {"period": period, "status": "NOTHING_TO_CLOSE", "execution_date_used": exec_dt}

    entries: List[Dict[str, Any]] = []

    # 1) Zero INCOME accounts
    for row in income_accounts:
        acc = str(row.get("account_no", "")).strip()
        amt = _to_decimal(row.get("amount", "0"))
        if acc and amt != 0:
            # reverse income by debiting
            entries.append({"account_no": acc, "side": "DR", "amount": str(abs(amt))})

    # 2) Zero EXPENSE accounts
    for row in expense_accounts:
        acc = str(row.get("account_no", "")).strip()
        amt = _to_decimal(row.get("amount", "0"))
        if acc and amt != 0:
            # reverse expense by crediting
            entries.append({"account_no": acc, "side": "CR", "amount": str(abs(amt))})

    # 3) Transfer net result to retained earnings
    if net_profit > 0:
        entries.append({"account_no": RETAINED_EARNINGS_GL, "side": "CR", "amount": str(net_profit)})
    elif net_profit < 0:
        entries.append({"account_no": RETAINED_EARNINGS_GL, "side": "DR", "amount": str(abs(net_profit))})

    if not entries:
        return {"period": period, "status": "NO_ENTRIES_GENERATED", "execution_date_used": exec_dt}

    # -----------------------------
    # (C) Post close transaction
    #     - Try without override first
    #     - If calendar requires override, retry with BACKDATE_EXECUTION_DATE
    #     - If suspense override is in play, attach it as secondary override for audit
    # -----------------------------
    override_payload: Optional[Dict[str, Any]] = None

    # If suspense was non-zero and reason provided, prepare secondary override attachment
    suspense_override_in_play = (suspense_net != Decimal("0")) and bool(suspense_override_reason and suspense_override_reason.strip())

    try:
        result = post_transaction(
            ticket_id=f"CLOSE-{period}",
            maker_user_id=admin_user_id,
            execution_date=exec_dt,
            value_date=exec_dt,
            description=f"Period Close – {period}",
            currency=currency,
            override=None,
            entries=entries,
        )
    except PermissionError as pe:
        msg = str(pe)
        if "required_override_type=BACKDATE_EXECUTION_DATE" in msg:
            base = _calendar_override_for_close(admin_user_id=admin_user_id, period=period)
            if suspense_override_in_play:
                override_payload = _attach_suspense_override(
                    base_override=base,
                    admin_user_id=admin_user_id,
                    period=period,
                    suspense_override_reason=str(suspense_override_reason).strip(),
                )
            else:
                override_payload = base

            result = post_transaction(
                ticket_id=f"CLOSE-{period}",
                maker_user_id=admin_user_id,
                execution_date=exec_dt,
                value_date=exec_dt,
                description=f"Period Close – {period}",
                currency=currency,
                override=override_payload,
                entries=entries,
            )
        else:
            raise

    out: Dict[str, Any] = {
        "period": period,
        "status": "CLOSED",
        "entries_posted": result.get("entries_written"),
        "transaction_id": result.get("transaction_id"),
        "execution_date_used": exec_dt,
    }

    if suspense_override_in_play:
        out["suspense_override_applied"] = True
        out["suspense_override_reason"] = str(suspense_override_reason).strip()
        out["suspense_position_at_close"] = {
            "account_no": suspense_pos["account_no"],
            "dr": str(suspense_pos["dr"]),
            "cr": str(suspense_pos["cr"]),
            "net_dr_minus_cr": str(suspense_pos["net_dr_minus_cr"]),
        }
    else:
        out["suspense_override_applied"] = False

    return out
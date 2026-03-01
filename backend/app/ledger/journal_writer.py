"""
Capital Strata Systems (CSS)
Phase 24A – Journal Writer (Calendar Governance Wired)

Enhancements:
- PostingCalendarEngine enforcement (execution/value date regime)
- No backdating without override
- No closed period posting without override
- No pre-go-live posting without override
- Fail-closed design
- Calendar decision logged per journal entry

All prior Phase 23E guarantees preserved.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from decimal import Decimal
from datetime import datetime, date
from typing import List, Dict, Optional, Any

# === NEW: Calendar Engine ===
from backend.app.posting_calendar import (
    PostingCalendarEngine,
    default_posting_calendar_policy,
    CalendarOverride,
)

JOURNAL_FILE = Path("audit_logs/journal.jsonl")
COA_FILE = Path("backend/app/config/chart_of_accounts.json")
ACCOUNT_REGISTRY_FILE = Path("backend/app/ledger/account_registry.json")


# =============================
# Utility Helpers
# =============================

def _to_decimal(val) -> Decimal:
    return Decimal(str(val))


def _ensure_file_exists(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")


def _ensure_journal_exists() -> None:
    _ensure_file_exists(JOURNAL_FILE)


def _parse_date_string(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def _normalize_override_for_calendar(override: Optional[Dict[str, Any]]) -> Optional[CalendarOverride]:
    if not override:
        return None
    return CalendarOverride(
        override_type=str(override.get("override_type", "")).strip(),
        override_reason=str(override.get("reason", "")).strip(),
        override_by_user_id=str(override.get("approved_by", "")).strip(),
        override_ticket_ref=str(override.get("override_ticket_ref", "")).strip() or "N/A",
    )


# =============================
# COA / Registry Loaders
# =============================

def _load_coa() -> Dict[str, Any]:
    if not COA_FILE.exists():
        raise FileNotFoundError(f"Chart of Accounts file missing: {COA_FILE}")
    with COA_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    out = {}
    for a in data.get("accounts", []):
        acc_no = str(a.get("account_no", "")).strip()
        if acc_no:
            out[acc_no] = a
    return out


def _load_account_registry() -> Dict[str, Any]:
    if ACCOUNT_REGISTRY_FILE.exists():
        txt = ACCOUNT_REGISTRY_FILE.read_text(encoding="utf-8").strip()
        if not txt:
            return {}
        return json.loads(txt)
    return {}


def _save_account_registry(reg: Dict[str, Any]) -> None:
    ACCOUNT_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNT_REGISTRY_FILE.write_text(
        json.dumps(reg, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


# =============================
# Core Validations
# =============================

def _validate_transaction(entries: List[Dict[str, Any]]) -> None:
    total_dr = Decimal("0")
    total_cr = Decimal("0")
    for e in entries:
        amt = _to_decimal(e["amount"])
        if str(e["side"]).upper() == "DR":
            total_dr += amt
        elif str(e["side"]).upper() == "CR":
            total_cr += amt
        else:
            raise ValueError(f"Invalid side: {e['side']}")
    if total_dr != total_cr:
        raise ValueError(f"Unbalanced transaction: DR={total_dr}, CR={total_cr}")


def _validate_global_balance() -> None:
    dr = Decimal("0")
    cr = Decimal("0")
    if not JOURNAL_FILE.exists():
        return
    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            j = json.loads(line)
            amt = _to_decimal(j["amount"])
            if j["side"] == "DR":
                dr += amt
            else:
                cr += amt
    if dr != cr:
        raise RuntimeError(f"Journal globally unbalanced. DR={dr}, CR={cr}")


# =============================
# MAIN ENTRY
# =============================

def post_transaction(
    ticket_id: str,
    entries: List[Dict[str, Any]],
    *,
    maker_user_id: str = "UNKNOWN",
    execution_date: Optional[str] = None,
    value_date: Optional[str] = None,
    description: str = "",
    currency: str = "NGN",
    override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    _ensure_journal_exists()
    _validate_global_balance()
    _validate_transaction(entries)

    exec_dt = execution_date or datetime.utcnow().strftime("%Y-%m-%d")
    val_dt = value_date or exec_dt
    created_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    exec_date_obj = _parse_date_string(exec_dt)
    val_date_obj = _parse_date_string(val_dt)
    today_obj = datetime.utcnow().date()

    # === CALENDAR ENGINE VALIDATION ===
    calendar_policy = default_posting_calendar_policy()
    cal_override = _normalize_override_for_calendar(override)

    decision = calendar_engine.validate_posting_window(
        execution_date=exec_date_obj,
        value_date=val_date_obj,
        today=today_obj,
        override=cal_override,
    )

    if decision.status != "ALLOW":
        raise PermissionError(
            f"Posting blocked by calendar engine: {decision.reason_code} | {decision.message}"
        )

    coa = _load_coa()
    reg = _load_account_registry()

    transaction_id = f"TXN-{uuid.uuid4().hex.upper()}"
    records: List[str] = []

    for e in entries:
        entry_id = f"ENT-{uuid.uuid4().hex.upper()}"

        record = {
            "journal_id": entry_id,
            "ticket_id": ticket_id,
            "execution_date": exec_dt,
            "account_no": str(e["account_no"]),
            "side": str(e["side"]).upper(),
            "amount": str(e["amount"]),
            "created_at": created_at,

            "transaction_id": transaction_id,
            "entry_id": entry_id,
            "maker_user_id": maker_user_id,
            "transaction_date": exec_dt,
            "value_date": val_dt,
            "description": description,
            "currency": currency.upper(),
            "override": override,

            # === NEW: Calendar Decision Snapshot ===
            "calendar_decision": {
                "status": decision.status,
                "reason_code": decision.reason_code,
                "meta": decision.meta,
            },
        }

        records.append(json.dumps(record, ensure_ascii=False))

    with JOURNAL_FILE.open("a", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(records) + "\n")

    _validate_global_balance()

    return {
        "transaction_id": transaction_id,
        "entries_written": len(entries),
        "calendar_enforced": True,
    }
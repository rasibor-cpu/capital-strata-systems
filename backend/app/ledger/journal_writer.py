"""
Capital Strata Systems (CSS)
Phase 23E – Journal Writer (GL COA Authority + Customer Runtime Registry)

Guarantees:
- Per-transaction DR = CR validation
- Atomic append of all legs
- Global journal balance verification
- Fail-closed on corruption
- UTF-8 enforced

Authorities:
- Structural COA (GL only): backend/app/config/chart_of_accounts.json
- Runtime registry (GL states + CUSTOMER accounts): backend/app/ledger/account_registry.json

Dormancy policy (your spec):
- For CUSTOMER accounts:
    * If DORMANT:
        - SYSTEM entries allowed
        - CUSTOMER-origin entries require override approval metadata
    * Successful CUSTOMER-origin posting auto-reactivates dormant CUSTOMER account

Note:
- GL accounts MUST exist in COA.
- CUSTOMER accounts MUST exist in runtime registry with category="CUSTOMER".
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional, Any


JOURNAL_FILE = Path("audit_logs/journal.jsonl")
COA_FILE = Path("backend/app/config/chart_of_accounts.json")
ACCOUNT_REGISTRY_FILE = Path("backend/app/ledger/account_registry.json")


def _to_decimal(val) -> Decimal:
    return Decimal(str(val))


def _ensure_file_exists(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")


def _ensure_journal_exists() -> None:
    _ensure_file_exists(JOURNAL_FILE)


def _load_coa() -> Dict[str, Any]:
    if not COA_FILE.exists():
        raise FileNotFoundError(f"Chart of Accounts file missing: {COA_FILE}")

    with COA_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    accounts = data.get("accounts", [])
    if not isinstance(accounts, list):
        raise ValueError("chart_of_accounts.json must contain key 'accounts' as a list")

    out: Dict[str, Any] = {}
    for a in accounts:
        if not isinstance(a, dict):
            continue
        acc_no = str(a.get("account_no", "")).strip()
        if acc_no:
            out[acc_no] = a
    return out


def _load_account_registry() -> Dict[str, Any]:
    if ACCOUNT_REGISTRY_FILE.exists():
        txt = ACCOUNT_REGISTRY_FILE.read_text(encoding="utf-8").strip()
        if not txt:
            return {}
        data = json.loads(txt)
        if not isinstance(data, dict):
            raise ValueError("account_registry.json must be a JSON object keyed by account_no")
        return data
    return {}


def _save_account_registry(reg: Dict[str, Any]) -> None:
    ACCOUNT_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNT_REGISTRY_FILE.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def _validate_transaction(entries: List[Dict[str, Any]]) -> None:
    total_dr = Decimal("0")
    total_cr = Decimal("0")

    for e in entries:
        amt = _to_decimal(e["amount"])
        side = str(e["side"]).upper()
        if side == "DR":
            total_dr += amt
        elif side == "CR":
            total_cr += amt
        else:
            raise ValueError(f"Invalid side: {e['side']}")

    if total_dr != total_cr:
        raise ValueError(f"Unbalanced transaction: DR={total_dr}, CR={total_cr}")


def _validate_global_balance() -> None:
    dr = Decimal("0")
    cr = Decimal("0")

    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            j = json.loads(line)
            amt = _to_decimal(j["amount"])
            side = str(j["side"]).upper()
            if side == "DR":
                dr += amt
            elif side == "CR":
                cr += amt

    if dr != cr:
        raise RuntimeError(f"Journal globally unbalanced. DR={dr}, CR={cr}")


def _is_system_origin(maker_user_id: str) -> bool:
    u = (maker_user_id or "").strip().upper()
    return u in {"SYSTEM", "BATCH", "EOD", "MONTHEND", "YEAR_END", "AUTO"}


def _validate_override(override: Optional[Dict[str, Any]]) -> None:
    if not override or not isinstance(override, dict):
        raise PermissionError("Dormant account posting requires an override object (approved by authority).")
    required = ["approved_by", "approved_by_role", "reason"]
    missing = [k for k in required if not override.get(k)]
    if missing:
        raise PermissionError(f"Override missing required fields: {missing}")


def _ensure_runtime_state_initialized(reg: Dict[str, Any], account_no: str) -> None:
    # For GL accounts, runtime state is optional; initialize on first touch.
    if account_no not in reg:
        reg[account_no] = {
            "category": "GL",
            "status": "ACTIVE",
            "last_customer_activity_date": None,
        }


def _classify_account(*, coa: Dict[str, Any], reg: Dict[str, Any], account_no: str) -> str:
    """
    Returns "GL" or "CUSTOMER".
    """
    if account_no in coa:
        return "GL"
    meta = reg.get(account_no)
    if isinstance(meta, dict) and str(meta.get("category", "")).upper() == "CUSTOMER":
        return "CUSTOMER"
    raise ValueError(f"Unknown account_no: {account_no} (not in COA and not a CUSTOMER runtime account)")


def _enforce_account_rules(
    *,
    coa: Dict[str, Any],
    reg: Dict[str, Any],
    account_no: str,
    maker_user_id: str,
    override: Optional[Dict[str, Any]],
) -> None:
    acct_kind = _classify_account(coa=coa, reg=reg, account_no=account_no)

    if acct_kind == "GL":
        # GL must exist in COA (already ensured by classifier)
        _ensure_runtime_state_initialized(reg, account_no)
        status = str(reg.get(account_no, {}).get("status", "ACTIVE")).upper()
        if status in {"CLOSED", "FROZEN"}:
            raise PermissionError(f"Posting blocked: GL account {account_no} status={status}")
        return

    # CUSTOMER account
    state = reg.get(account_no, {})
    status = str(state.get("status", "ACTIVE")).upper()

    if status in {"CLOSED", "FROZEN"}:
        raise PermissionError(f"Posting blocked: CUSTOMER account {account_no} status={status}")

    if status == "DORMANT":
        if _is_system_origin(maker_user_id):
            return
        _validate_override(override)


def _reactivate_dormant_customers(
    *,
    reg: Dict[str, Any],
    touched_accounts: List[str],
    maker_user_id: str,
    transaction_date: str,
) -> bool:
    if _is_system_origin(maker_user_id):
        return False

    changed = False
    for acc in touched_accounts:
        meta = reg.get(acc)
        if not isinstance(meta, dict):
            continue
        if str(meta.get("category", "")).upper() != "CUSTOMER":
            continue
        if str(meta.get("status", "ACTIVE")).upper() == "DORMANT":
            meta["status"] = "ACTIVE"
            meta["last_customer_activity_date"] = transaction_date
            meta.pop("dormancy", None)
            reg[acc] = meta
            changed = True
    return changed


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

    # Fail if journal already corrupted
    _validate_global_balance()

    # Validate transaction legs
    _validate_transaction(entries)

    # Normalize dates
    exec_dt = execution_date or datetime.utcnow().strftime("%Y-%m-%d")
    val_dt = value_date or exec_dt
    created_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    coa = _load_coa()
    reg = _load_account_registry()

    touched_accounts: List[str] = []
    for e in entries:
        acc = str(e["account_no"]).strip()
        touched_accounts.append(acc)
        _enforce_account_rules(
            coa=coa,
            reg=reg,
            account_no=acc,
            maker_user_id=maker_user_id,
            override=override,
        )

    transaction_id = f"TXN-{uuid.uuid4().hex.upper()}"
    records: List[str] = []

    for e in entries:
        entry_id = f"ENT-{uuid.uuid4().hex.upper()}"
        journal_id = entry_id

        record = {
            "journal_id": journal_id,
            "ticket_id": ticket_id,
            "execution_date": exec_dt,
            "account_no": str(e["account_no"]),
            "side": str(e["side"]).upper(),
            "amount": str(e["amount"]),
            "created_at": created_at,

            "transaction_id": transaction_id,
            "entry_id": entry_id,
            "maker_user_id": str(maker_user_id).strip() or "UNKNOWN",
            "transaction_date": exec_dt,
            "value_date": val_dt,
            "description": str(description or ""),
            "currency": str(currency or "NGN").upper(),
            "override": override,
        }

        records.append(json.dumps(record, ensure_ascii=False))

    with JOURNAL_FILE.open("a", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(records) + "\n")

    _validate_global_balance()

    reactivated = _reactivate_dormant_customers(
        reg=reg,
        touched_accounts=touched_accounts,
        maker_user_id=maker_user_id,
        transaction_date=exec_dt,
    )

    # Persist runtime state (GL init records + customer updates)
    if touched_accounts or reactivated:
        _save_account_registry(reg)

    return {
        "transaction_id": transaction_id,
        "entries_written": len(entries),
        "reactivated_accounts": bool(reactivated),
    }
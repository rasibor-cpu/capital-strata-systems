"""
backend/app/ledger/account_create.py
Capital Strata Systems (CSS)

Phase 23D — Account Creation Governance + System-Generated Customer Accounts

Governance (locked):
- Only Customer Service user IDs/department can create NEW customer accounts.
- Only Super User / FinCon user IDs/department can create NEW GL ledger accounts.

Design:
- Structural COA (GL only): backend/app/config/chart_of_accounts.json
- Runtime account registry (GL states + CUSTOMER accounts): backend/app/ledger/account_registry.json

Customer accounts:
- System-generated account numbers (no manual entry)
- Persisted in runtime registry with category="CUSTOMER"
- Linked to a control GL account (e.g., Customer Deposits – Demand control GL)
- Dormancy defaults: ACTIVE
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


COA_FILE = Path("backend/app/config/chart_of_accounts.json")
RUNTIME_REGISTRY_FILE = Path("backend/app/ledger/account_registry.json")
SEQUENCE_FILE = Path("audit_logs/account_sequences.json")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _utc_ymd() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    txt = path.read_text(encoding="utf-8").strip()
    if not txt:
        return default
    return json.loads(txt)


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_coa_accounts_by_no() -> Dict[str, Dict[str, Any]]:
    data = _load_json(COA_FILE, {})
    accounts = data.get("accounts", [])
    out: Dict[str, Dict[str, Any]] = {}
    for a in accounts:
        if not isinstance(a, dict):
            continue
        acc_no = str(a.get("account_no", "")).strip()
        if acc_no:
            out[acc_no] = a
    return out


def _load_runtime_registry() -> Dict[str, Any]:
    return _load_json(RUNTIME_REGISTRY_FILE, {})


def _save_runtime_registry(reg: Dict[str, Any]) -> None:
    _save_json(RUNTIME_REGISTRY_FILE, reg)


def _next_seq(key: str) -> int:
    seq = _load_json(SEQUENCE_FILE, {})
    if not isinstance(seq, dict):
        seq = {}
    seq[key] = int(seq.get(key, 0)) + 1
    _save_json(SEQUENCE_FILE, seq)
    return int(seq[key])


def _require_dept(department: str, allowed: set[str], action: str) -> None:
    dept = (department or "").strip().upper()
    if dept not in allowed:
        raise PermissionError(f"{action} blocked: department '{department}' not authorized.")


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------

def create_customer_account(
    *,
    maker_user_id: str,
    maker_department: str,
    currency_num: str = "840",
    product: str = "DEMAND_DEPOSIT",
    customer_name: str = "",
    control_gl_account_no: str = "000-840-300",
) -> Dict[str, Any]:
    """
    Creates a NEW customer account (system-generated account number).

    Authorization:
      - maker_department must be CUSTOMER_SERVICE

    Output:
      - {"account_no": "...", "category":"CUSTOMER", ...}
    """

    _require_dept(maker_department, {"CUSTOMER_SERVICE"}, "Create customer account")

    # Validate control GL exists in COA (structural integrity)
    coa = _load_coa_accounts_by_no()
    if control_gl_account_no not in coa:
        raise ValueError(f"Control GL account not found in COA: {control_gl_account_no}")

    # Generate account number (system only)
    # Format: CUST-<currency_num>-<8digit seq>
    seq = _next_seq(f"CUST-{currency_num}")
    account_no = f"CUST-{currency_num}-{seq:08d}"

    reg = _load_runtime_registry()
    if account_no in reg:
        # Extremely unlikely; but fail-closed.
        raise RuntimeError(f"Generated customer account already exists: {account_no}")

    reg[account_no] = {
        "category": "CUSTOMER",
        "status": "ACTIVE",
        "currency_num": str(currency_num),
        "product": str(product).upper(),
        "customer_name": str(customer_name or "").strip(),
        "control_gl_account_no": str(control_gl_account_no),
        "created_by": str(maker_user_id or "UNKNOWN"),
        "created_department": str(maker_department or "").strip().upper(),
        "created_date": _utc_ymd(),
        "last_customer_activity_date": None,
        # optional dormancy fields may be added later
    }

    _save_runtime_registry(reg)

    return {"ok": True, "account_no": account_no, "record": reg[account_no]}


def create_gl_account(
    *,
    maker_user_id: str,
    maker_department: str,
    account_no: str,
    name: str,
    acc_type: str,
    group: str,
) -> Dict[str, Any]:
    """
    Creates a NEW GL account by adding it to the structural COA file.

    Authorization:
      - maker_department must be SUPER_USER or FINCON

    NOTE:
    - This function updates backend/app/config/chart_of_accounts.json
    - It does NOT create customer accounts.
    """
    _require_dept(maker_department, {"SUPER_USER", "FINCON"}, "Create GL account")

    account_no = str(account_no).strip()
    if not account_no:
        raise ValueError("account_no is required")

    # Load COA
    data = _load_json(COA_FILE, {})
    accounts = data.get("accounts", [])
    if not isinstance(accounts, list):
        raise ValueError("chart_of_accounts.json invalid: 'accounts' must be a list")

    # Ensure no duplicates
    for a in accounts:
        if isinstance(a, dict) and str(a.get("account_no", "")).strip() == account_no:
            raise ValueError(f"GL account already exists in COA: {account_no}")

    new_acc = {
        "account_no": account_no,
        "name": str(name).strip(),
        "type": str(acc_type).strip().upper(),
        "group": str(group).strip().upper(),
    }

    accounts.append(new_acc)
    data["accounts"] = accounts

    _save_json(COA_FILE, data)

    return {"ok": True, "account_no": account_no, "added": new_acc, "created_by": maker_user_id}
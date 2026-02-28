"""
Capital Strata Systems (CSS)
Phase 23B – Journal Writer (COA-Authoritative + Dormancy Governance)

Guarantees:
- Per-transaction DR = CR validation
- Atomic append of all legs
- Global journal balance verification
- Fail-closed on corruption
- UTF-8 enforced

Backwards compatibility:
- Keeps legacy keys: journal_id, ticket_id, execution_date, account_no, side, amount, created_at
- Adds governance keys:
  transaction_id, entry_id, maker_user_id, transaction_date, value_date, description, currency, override

Institutional split (authoritative sources):
- Structural COA authority: backend/app/config/chart_of_accounts.json
- Runtime state (status/dormancy/flags): backend/app/ledger/account_registry.json

Dormancy policy (your spec):
- Applies to CUSTOMER accounts only (deposit liabilities group=DEPOSITS)
- If DORMANT:
    * SYSTEM entries allowed
    * CUSTOMER-origin entries require override
    * Successful CUSTOMER-origin posting auto-reactivates (status -> ACTIVE)
- Any posting into dormant customer accounts must be approved by override (authority-logged)
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional, Any


JOURNAL_FILE = Path("audit_logs/journal.jsonl")

# Authoritative structural COA
COA_FILE = Path("backend/app/config/chart_of_accounts.json")

# Runtime state registry (status/dormancy/flags)
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
    """
    Loads structural COA and returns dict keyed by account_no.
    """
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
        if not acc_no:
            continue
        out[acc_no] = a
    return out


def _load_account_registry() -> Dict[str, Any]:
    """
    Loads runtime account state registry keyed by account_no.
    If it doesn't exist yet, returns empty dict.
    """
    if ACCOUNT_REGISTRY_FILE.exists():
        with ACCOUNT_REGISTRY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("account_registry.json must be a JSON object keyed by account_no")
        return data
    return {}


def _save_account_registry(reg: Dict[str, Any]) -> None:
    ACCOUNT_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ACCOUNT_REGISTRY_FILE.open("w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2, ensure_ascii=False)


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
    """
    Institutional rule: SYSTEM entries are those posted by system/batch identities.
    Expand as user model evolves.
    """
    u = (maker_user_id or "").strip().upper()
    return u in {"SYSTEM", "BATCH", "EOD", "MONTHEND", "YEAR_END", "AUTO"}


def _validate_override(override: Optional[Dict[str, Any]]) -> None:
    """
    Enforces presence of audit-grade override metadata.
    """
    if not override or not isinstance(override, dict):
        raise PermissionError("Dormant account posting requires an override object (approved by authority).")

    required = ["approved_by", "approved_by_role", "reason"]
    missing = [k for k in required if not override.get(k)]
    if missing:
        raise PermissionError(f"Override missing required fields: {missing}")


def _is_customer_account_from_coa(coa_meta: Dict[str, Any]) -> bool:
    """
    Your current Phase 1 COA is GL-only, but customer-related accounts are represented as:
      LIABILITIES group=DEPOSITS  (Customer Deposits – Demand, etc.)
    """
    acct_type = str(coa_meta.get("type", "")).upper()
    grp = str(coa_meta.get("group", "")).upper()
    return (acct_type == "LIABILITY") and (grp == "DEPOSITS")


def _ensure_runtime_state_initialized(reg: Dict[str, Any], account_no: str) -> None:
    """
    First-touch initialization of runtime state.
    """
    if account_no not in reg:
        reg[account_no] = {
            "status": "ACTIVE",
            "last_customer_activity_date": None,
        }


def _enforce_account_rules(
    *,
    coa: Dict[str, Any],
    reg: Dict[str, Any],
    account_no: str,
    maker_user_id: str,
    override: Optional[Dict[str, Any]],
) -> None:
    """
    Enforces:
    - Structural existence in COA
    - Runtime status blocks (CLOSED/FROZEN)
    - Dormancy policy for customer accounts
    """
    # 1) Structural COA validation
    if account_no not in coa:
        raise ValueError(f"Account not defined in Chart of Accounts: {account_no}")

    # 2) Ensure runtime record exists
    _ensure_runtime_state_initialized(reg, account_no)

    state = reg.get(account_no, {})
    status = str(state.get("status", "ACTIVE")).upper()

    if status not in {"ACTIVE", "DORMANT", "CLOSED", "FROZEN"}:
        raise ValueError(f"Invalid runtime status for {account_no}: {status}")

    # 3) Hard blocks
    if status in {"CLOSED", "FROZEN"}:
        raise PermissionError(f"Posting blocked: account {account_no} status={status}")

    # 4) Dormancy
    coa_meta = coa.get(account_no, {})
    if _is_customer_account_from_coa(coa_meta) and status == "DORMANT":
        if _is_system_origin(maker_user_id):
            return
        _validate_override(override)


def _reactivate_if_customer_origin(
    *,
    coa: Dict[str, Any],
    reg: Dict[str, Any],
    touched_accounts: List[str],
    maker_user_id: str,
    transaction_date: str,
) -> bool:
    """
    If CUSTOMER-origin transaction posts successfully and it touched any dormant CUSTOMER account,
    auto-reactivate it.
    """
    if _is_system_origin(maker_user_id):
        return False

    changed = False
    for acc in touched_accounts:
        if acc not in coa:
            continue
        if not _is_customer_account_from_coa(coa[acc]):
            continue

        state = reg.get(acc, {})
        if str(state.get("status", "ACTIVE")).upper() == "DORMANT":
            state["status"] = "ACTIVE"
            state["last_customer_activity_date"] = transaction_date
            # optional: clear dormancy metadata
            state.pop("dormancy", None)
            reg[acc] = state
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
    """
    Post balanced transaction atomically.

    Args:
      ticket_id: posting ticket id (e.g., BASELINE-POST-1)
      entries: list of {account_no, side, amount}
      maker_user_id: maker id for governance & duplicate-guard logic
      execution_date: YYYY-MM-DD (defaults to today UTC)
      value_date: YYYY-MM-DD (defaults to execution_date)
      description: narrative
      currency: ISO alpha code (default NGN)
      override: optional dict, required for dormant customer postings when origin=CUSTOMER

    Returns:
      {"transaction_id": ..., "entries_written": N, "reactivated_accounts": bool}
    """
    _ensure_journal_exists()

    # Fail if journal already corrupted
    _validate_global_balance()

    # Validate transaction legs
    _validate_transaction(entries)

    # Normalize dates
    exec_dt = execution_date or datetime.utcnow().strftime("%Y-%m-%d")
    val_dt = value_date or exec_dt

    created_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Load authorities once per transaction
    coa = _load_coa()
    reg = _load_account_registry()

    # Enforce rules for every leg
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

    # One transaction_id for all legs (institutional)
    transaction_id = f"TXN-{uuid.uuid4().hex.upper()}"

    records: List[str] = []

    for e in entries:
        entry_id = f"ENT-{uuid.uuid4().hex.upper()}"
        journal_id = entry_id  # legacy alias retained

        record = {
            # --- legacy keys ---
            "journal_id": journal_id,
            "ticket_id": ticket_id,
            "execution_date": exec_dt,
            "account_no": str(e["account_no"]),
            "side": str(e["side"]).upper(),
            "amount": str(e["amount"]),
            "created_at": created_at,

            # --- new keys ---
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

    # Atomic append (single write operation)
    with JOURNAL_FILE.open("a", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(records) + "\n")

    # Verify integrity after write
    _validate_global_balance()

    # Auto-reactivate dormant customer accounts on successful customer-origin posting
    reactivated = _reactivate_if_customer_origin(
        coa=coa,
        reg=reg,
        touched_accounts=touched_accounts,
        maker_user_id=maker_user_id,
        transaction_date=exec_dt,
    )

    # Persist runtime state (init records + possible reactivation)
    if reactivated or touched_accounts:
        _save_account_registry(reg)

    return {
        "transaction_id": transaction_id,
        "entries_written": len(entries),
        "reactivated_accounts": bool(reactivated),
    }
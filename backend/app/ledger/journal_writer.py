"""
Capital Strata Systems
Phase 23A – Journal Writer (COA + Dormancy Enforcement)

Guarantees:
- Per-transaction DR = CR validation
- Atomic append of all legs
- Global journal balance verification
- Fail-closed on corruption
- UTF-8 enforced

Backwards compatibility:
- Keeps legacy keys
- Adds governance keys (transaction_id, entry_id, maker_user_id, dates, description, currency, override)

New in Phase 23A:
- COA / account registry validation (fail-closed if account missing or inactive)
- Dormancy rules for CUSTOMER accounts:
    * SYSTEM entries allowed even if DORMANT
    * CUSTOMER-origin entries into DORMANT accounts require override approval
    * Successful CUSTOMER-origin posting auto-reactivates account (status -> ACTIVE)
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional, Any


JOURNAL_FILE = Path("audit_logs/journal.jsonl")
ACCOUNT_REGISTRY_FILE = Path("backend/app/ledger/account_registry.json")


def _to_decimal(val) -> Decimal:
    return Decimal(str(val))


def _ensure_file_exists(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")


def _ensure_journal_exists() -> None:
    _ensure_file_exists(JOURNAL_FILE)


def _load_account_registry() -> Dict[str, Any]:
    if not ACCOUNT_REGISTRY_FILE.exists():
        raise FileNotFoundError(f"Account registry missing: {ACCOUNT_REGISTRY_FILE}")
    with ACCOUNT_REGISTRY_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Account registry must be a JSON object keyed by account_no")
    return data


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
    You can expand this list as your user model evolves.
    """
    u = (maker_user_id or "").strip().upper()
    return u in {"SYSTEM", "BATCH", "EOD", "MONTHEND", "YEAR_END", "AUTO"}


def _validate_override(override: Optional[Dict[str, Any]]) -> None:
    if not override or not isinstance(override, dict):
        raise PermissionError("Dormant account posting requires an override object (approved by authority).")

    # Minimum required fields for auditability
    required = ["approved_by", "approved_by_role", "reason"]
    missing = [k for k in required if not override.get(k)]
    if missing:
        raise PermissionError(f"Override missing required fields: {missing}")


def _enforce_account_rules(
    *,
    reg: Dict[str, Any],
    account_no: str,
    maker_user_id: str,
    override: Optional[Dict[str, Any]],
) -> None:
    if account_no not in reg:
        raise ValueError(f"Unknown account_no (not in registry): {account_no}")

    meta = reg.get(account_no, {})
    status = str(meta.get("status", "ACTIVE")).upper()
    category = str(meta.get("category", "GL")).upper()

    if status not in {"ACTIVE", "DORMANT", "CLOSED", "FROZEN"}:
        raise ValueError(f"Invalid account status in registry for {account_no}: {status}")

    if status in {"CLOSED", "FROZEN"}:
        raise PermissionError(f"Posting blocked: account {account_no} status={status}")

    # Dormancy enforcement applies only to CUSTOMER accounts
    if category == "CUSTOMER" and status == "DORMANT":
        if _is_system_origin(maker_user_id):
            # SYSTEM entries are allowed into dormant customer accounts
            return
        # CUSTOMER-origin entries require override approval
        _validate_override(override)


def _reactivate_if_customer_origin(
    *,
    reg: Dict[str, Any],
    touched_accounts: List[str],
    maker_user_id: str,
    transaction_date: str,
) -> bool:
    """
    If a CUSTOMER-origin transaction posts successfully and it touched any dormant CUSTOMER account,
    auto-reactivate those accounts.
    """
    if _is_system_origin(maker_user_id):
        return False

    changed = False
    for acc in touched_accounts:
        meta = reg.get(acc)
        if not isinstance(meta, dict):
            continue
        if str(meta.get("category", "GL")).upper() != "CUSTOMER":
            continue
        if str(meta.get("status", "ACTIVE")).upper() == "DORMANT":
            meta["status"] = "ACTIVE"
            meta["last_customer_activity_date"] = transaction_date
            # optional: clear dormancy reason
            meta.pop("dormancy", None)
            changed = True

    if changed:
        _save_account_registry(reg)

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

    # Load registry once per transaction
    reg = _load_account_registry()

    # Enforce COA + dormancy rules for every leg
    touched_accounts: List[str] = []
    for e in entries:
        acc = str(e["account_no"])
        touched_accounts.append(acc)
        _enforce_account_rules(
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
        reg=reg,
        touched_accounts=touched_accounts,
        maker_user_id=maker_user_id,
        transaction_date=exec_dt,
    )

    return {
        "transaction_id": transaction_id,
        "entries_written": len(entries),
        "reactivated_accounts": bool(reactivated),
    }
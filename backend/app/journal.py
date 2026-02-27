"""
journal.py — governance-safe journal posting utility
Capital Strata Systems

Purpose:
- Provide a stable `post_to_journal()` API for append-only journaling.
- Default journal location is repo-root anchored: audit_logs/journal.jsonl
- Write flat JSON lines (schema-compatible with existing audit_logs/journal.jsonl)

Governance:
- If gl_account_id is provided -> MUST be internal (10 digits, startswith "000")
- If customer_acct is provided -> MUST be 10 digits and must NOT startwith "000"
- Dashed inputs are accepted and canonicalized to 10 digits
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    # Preferred: shared invariant utilities
    from engine.accounting.account_ids import (
        normalize_account_id,
        try_normalize_10digits,
        validate_customer_acct,
        validate_internal_gl,
        is_internal_gl,
    )
except Exception:
    # Fail-closed if engine package is not available in some minimal contexts
    normalize_account_id = None  # type: ignore
    try_normalize_10digits = None  # type: ignore
    validate_customer_acct = None  # type: ignore
    validate_internal_gl = None  # type: ignore
    is_internal_gl = None  # type: ignore


@dataclass
class JournalResult:
    ok: bool
    path: str
    entry_id: str
    error: Optional[str] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def _repo_root() -> str:
    """
    Resolve repo root from cwd at runtime (PowerShell runs from repo root in your workflow).
    If you run from a subdir, this still works as long as 'audit_logs' is relative to cwd.
    """
    return os.getcwd()


def _default_journal_path() -> str:
    return os.path.join(_repo_root(), "audit_logs", "journal.jsonl")


def _default_overrides_path() -> str:
    return os.path.join(_repo_root(), "audit_logs", "overrides.jsonl")


def _canonicalize_if_possible(value: Any) -> Optional[str]:
    """
    Accept '1234-840-001' or '1234840001' -> '1234840001' if 10-digit.
    Returns None if not canonicalizable.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None

    if normalize_account_id is not None:
        try:
            canon = normalize_account_id(s)
            return canon if len(canon) == 10 else None
        except Exception:
            return None

    # fallback minimal normalization
    s2 = s.replace("-", "").replace(" ", "")
    return s2 if (s2.isdigit() and len(s2) == 10) else None


def _apply_account_id_governance(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforce account-id invariants if the keys are present (fail-closed).
    Also attempts safe enrichment:
    - if account_no looks like a 10-digit internal GL, set gl_account_id
    """
    out = dict(entry)

    # -----------------------------
    # Normalize / validate customer_acct
    # -----------------------------
    cust_raw = out.get("customer_acct", None) or out.get("customer_account", None)
    cust = _canonicalize_if_possible(cust_raw)
    if cust is not None:
        if validate_customer_acct is None:
            raise PermissionError("account id validator unavailable (engine.accounting.account_ids import failed)")
        out["customer_acct"] = validate_customer_acct(cust)

    # -----------------------------
    # Normalize / validate gl_account_id (internal-ledger flagged by '000')
    # -----------------------------
    gl_raw = out.get("gl_account_id", None)
    gl = _canonicalize_if_possible(gl_raw)
    if gl is not None:
        if validate_internal_gl is None:
            raise PermissionError("account id validator unavailable (engine.accounting.account_ids import failed)")
        out["gl_account_id"] = validate_internal_gl(gl)

    # -----------------------------
    # Safe enrichment from account_no (legacy)
    # If account_no is already a 10-digit internal GL, stamp gl_account_id.
    # -----------------------------
    acct_no = out.get("account_no", None)
    acct10 = _canonicalize_if_possible(acct_no)
    if acct10 is not None and gl is None:
        if is_internal_gl is not None and is_internal_gl(acct10):
            if validate_internal_gl is None:
                raise PermissionError("account id validator unavailable (engine.accounting.account_ids import failed)")
            out["gl_account_id"] = validate_internal_gl(acct10)

    return out


def post_to_journal(
    entry: Dict[str, Any],
    *,
    journal_path: Optional[str] = None,
    entry_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Append ONE journal entry as ONE JSON line (flat dict).

    - Adds ts_utc + entry_id if missing
    - Applies governance validation if customer_acct/gl_account_id are present
    - Fail-closed: invalid account ids raise error (returned as ok=False)

    Args:
        entry: dict payload describing the journal line (flat)
        journal_path: optional explicit path; defaults to audit_logs/journal.jsonl (repo-root)
        entry_id: optional external id; generated if missing

    Returns:
        dict with fields: ok, path, entry_id, error (if any)
    """
    safe_entry_id = entry_id or entry.get("entry_id") or f"jrn_{int(datetime.now().timestamp() * 1000)}"
    path = journal_path or _default_journal_path()

    record = dict(entry)
    record.setdefault("entry_id", safe_entry_id)
    record.setdefault("ts_utc", _utc_now_iso())
    record.setdefault("created_at", record.get("created_at") or record["ts_utc"])

    try:
        record = _apply_account_id_governance(record)

        _ensure_parent_dir(path)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return asdict(JournalResult(ok=True, path=path, entry_id=safe_entry_id))

    except Exception as e:
        return asdict(JournalResult(ok=False, path=path, entry_id=safe_entry_id, error=str(e)))


def post_override_to_journal(
    override_entry: Dict[str, Any],
    *,
    overrides_path: Optional[str] = None,
    entry_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Append ONE override audit entry as ONE JSON line to audit_logs/overrides.jsonl.
    """
    safe_entry_id = entry_id or override_entry.get("entry_id") or f"ovr_{int(datetime.now().timestamp() * 1000)}"
    path = overrides_path or _default_overrides_path()

    record = dict(override_entry)
    record.setdefault("entry_id", safe_entry_id)
    record.setdefault("ts_utc", _utc_now_iso())
    record.setdefault("created_at", record.get("created_at") or record["ts_utc"])

    try:
        record = _apply_account_id_governance(record)

        _ensure_parent_dir(path)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return asdict(JournalResult(ok=True, path=path, entry_id=safe_entry_id))

    except Exception as e:
        return asdict(JournalResult(ok=False, path=path, entry_id=safe_entry_id, error=str(e)))
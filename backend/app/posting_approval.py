"""
backend/app/posting_approval.py

Central Posting Governance Gate (Control Layer)
-----------------------------------------------
This module is NOT a screen. It is a reusable governance rule engine.

Hard rules implemented:
1) AUDIT_CONTROL is READ-ONLY: cannot post, cannot approve, cannot override.
2) TREASURY postings must include dims.instrument_id and it must exist in instrument_master.json.
3) Account-ID Governance (10-digit):
   - Internal GL accounts MUST be 10 digits and start with "000" (e.g., 0001-840-001)
   - Customer accounts MUST be 10 digits and MUST NOT start with "000" (e.g., 1234-840-001)
   - ISO-4217 numeric currency code (3 digits) is embedded in the 10-digit format.
   - Dashed input is accepted and canonicalized.

Org model:
- user -> team -> branch -> division -> country (resolved from org_structure.json)

Design:
- Fail-closed by callers (screens/APIs should block if this module isn't available).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]

ORG_FILE = REPO_ROOT / "backend" / "app" / "config" / "org_structure.json"
INSTR_FILE = REPO_ROOT / "backend" / "app" / "config" / "instrument_master.json"

AUDIT_ROLE = "AUDIT_CONTROL"

# -------------------------------------------------
# Optional shared validators (preferred)
# -------------------------------------------------
try:
    from engine.accounting.account_ids import (
        normalize_account_id,
        validate_customer_acct,
        validate_internal_gl,
        is_internal_gl,
    )
except Exception:
    normalize_account_id = None  # type: ignore
    validate_customer_acct = None  # type: ignore
    validate_internal_gl = None  # type: ignore
    is_internal_gl = None  # type: ignore


# -----------------------------
# Decision object
# -----------------------------

@dataclass(frozen=True)
class PostingGateDecision:
    approved: bool
    reason: str = ""


# -----------------------------
# Utilities
# -----------------------------

def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"Missing config file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_user_team(user_id: str) -> str:
    """
    Returns team name (e.g., 'TREASURY', 'FIN_CTRL') based on org_structure.json.
    """
    if not user_id:
        return "UNKNOWN"

    org = _load_json(ORG_FILE, default={})
    divisions = org.get("divisions", {}) or {}

    for div_obj in divisions.values():
        branches = (div_obj or {}).get("branches", {}) or {}
        for branch_obj in branches.values():
            teams = (branch_obj or {}).get("teams", {}) or {}
            for team_name, team in teams.items():
                supervisors = team.get("supervisors") or []
                members = team.get("members") or []
                if user_id in supervisors or user_id in members:
                    return str(team_name).strip().upper()

    return "UNKNOWN"


def _instrument_exists(instr_id: str) -> bool:
    if not instr_id:
        return False
    master = _load_json(INSTR_FILE, default={})
    return str(instr_id).strip() in master


def _canon10(value: Any) -> Optional[str]:
    """
    Accept '1234-840-001' or '1234840001' -> '1234840001' if it is 10 digits.
    Returns None if not canonicalizable to 10 digits.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None

    if normalize_account_id is not None:
        try:
            c = normalize_account_id(s)
            return c if len(c) == 10 else None
        except Exception:
            return None

    # fallback minimal normalization
    s2 = s.replace("-", "").replace(" ", "")
    if s2.isdigit() and len(s2) == 10:
        return s2
    return None


def _is_internal(value10: str) -> bool:
    if is_internal_gl is not None:
        return bool(is_internal_gl(value10))
    return value10.startswith("000")


def _validate_account_governance(payload: Dict[str, Any]) -> Optional[str]:
    """
    Returns error string if invalid; else None.
    Enforces:
      - gl_account_id if present -> internal "000..." + 10 digits
      - customer_acct if present -> NOT "000..." + 10 digits
      - account_no (legacy):
          * if 10 digits and startswith "000" -> allowed as internal ledger id
          * if 10 digits and NOT startswith "000" -> reject (customer acct mistakenly in account_no)
    """
    # customer_acct
    cust = payload.get("customer_acct") or payload.get("customer_account")
    cust10 = _canon10(cust)
    if cust10 is not None:
        if validate_customer_acct is None:
            return "Account-ID validators unavailable (engine.accounting.account_ids import failed)."
        try:
            validate_customer_acct(cust10)
        except Exception as e:
            return f"Invalid customer_acct: {e}"

    # gl_account_id
    gl = payload.get("gl_account_id")
    gl10 = _canon10(gl)
    if gl10 is not None:
        if validate_internal_gl is None:
            return "Account-ID validators unavailable (engine.accounting.account_ids import failed)."
        try:
            validate_internal_gl(gl10)
        except Exception as e:
            return f"Invalid gl_account_id (internal GL must start with '000'): {e}"

    # legacy account_no
    acct_no = payload.get("account_no")
    acct10 = _canon10(acct_no)
    if acct10 is not None:
        if _is_internal(acct10):
            # ok: internal GL in legacy field
            return None
        # 10-digit but not internal => this is a CUSTOMER acct mistakenly passed as account_no
        return (
            f"Invalid account_no for internal ledger. "
            f"10-digit customer-style account detected ({acct10}). "
            f"Internal GL accounts must start with '000'. "
            f"Use customer_acct for customer ledger postings."
        )

    return None


# -----------------------------
# Main Gate
# -----------------------------

def validate_posting(payload: Dict[str, Any], role: str) -> Dict[str, Any]:
    """
    Governance gate.

    Args:
      payload:
        - maker_user_id: str (preferred)
        - dims: dict (optional, required for TREASURY instrument enforcement)
        - customer_acct / gl_account_id / account_no (optional fields)
      role:
        - caller-provided user role (e.g. 'TREASURY', 'AUDIT_CONTROL', 'SUPER_USER')

    Returns:
      { "approved": bool, "reason": str }
    """
    role = (role or "").strip().upper()

    # 1) Audit is read-only (hard fail, no override)
    if role == AUDIT_ROLE:
        d = PostingGateDecision(
            approved=False,
            reason="AUDIT_CONTROL role is read-only and cannot post or approve postings.",
        )
        return {"approved": d.approved, "reason": d.reason}

    maker_user_id = str(payload.get("maker_user_id") or "").strip()
    dims = payload.get("dims") or {}
    if not isinstance(dims, dict):
        dims = {}

    # Optional fallback if older payloads carry maker in dims
    if not maker_user_id:
        maker_user_id = str(dims.get("maker_user_id") or "").strip()

    team = _resolve_user_team(maker_user_id)

    # 2) Treasury postings must carry a valid instrument_id
    if team == "TREASURY":
        instr_id = str(dims.get("instrument_id") or "").strip()
        if not instr_id:
            d = PostingGateDecision(
                approved=False,
                reason="Treasury postings must include dims.instrument_id.",
            )
            return {"approved": d.approved, "reason": d.reason}

        if not _instrument_exists(instr_id):
            d = PostingGateDecision(
                approved=False,
                reason=f"Invalid dims.instrument_id '{instr_id}' — not found in instrument_master.json.",
            )
            return {"approved": d.approved, "reason": d.reason}

    # 3) Account-ID governance (fail-closed)
    err = _validate_account_governance(payload)
    if err:
        d = PostingGateDecision(approved=False, reason=err)
        return {"approved": d.approved, "reason": d.reason}

    return {"approved": True, "reason": ""}
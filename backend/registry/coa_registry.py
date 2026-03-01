"""
Capital Strata Systems (CSS)
Phase 23.2B — GL Ledger Creation Authority Lock

Hard Controls:
- Only FINCON or SUPER_USER may create GL accounts
- GL accounts must start with 000-
- Must follow numbering schema: 000-CCC-XXX
- No duplicate GL account creation
- Audit log required
- Fail closed
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


COA_FILE = Path("backend/app/config/chart_of_accounts.json")
GL_REGISTRY = Path("backend/registry/coa_registry.json")
GL_EVENTS = Path("audit_logs/gl_account_events.jsonl")


# ============================================================
# Utilities
# ============================================================

def _now():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_files():
    GL_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    GL_EVENTS.parent.mkdir(parents=True, exist_ok=True)

    if not GL_REGISTRY.exists():
        GL_REGISTRY.write_text("{}", encoding="utf-8")

    if not GL_EVENTS.exists():
        GL_EVENTS.write_text("", encoding="utf-8")


def _load_registry() -> Dict[str, Any]:
    _ensure_files()
    if GL_REGISTRY.stat().st_size == 0:
        return {}
    with GL_REGISTRY.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_registry(data: Dict[str, Any]):
    with GL_REGISTRY.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _log_event(event: Dict[str, Any]):
    with GL_EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


# ============================================================
# Authority Gate
# ============================================================

def _enforce_gl_authority(maker_department: str):
    dept = maker_department.strip().upper()
    if dept not in ("FINCON", "SUPER_USER"):
        raise PermissionError(
            "Only FINCON or SUPER_USER may create new GL ledger accounts."
        )


# ============================================================
# Numbering Schema Validation
# ============================================================

def _validate_gl_account_number(account_no: str):
    if not account_no.startswith("000-"):
        raise ValueError("GL account must start with 000-")

    parts = account_no.split("-")
    if len(parts) != 3:
        raise ValueError("GL account must follow schema 000-CCC-XXX")

    if not parts[1].isdigit() or not parts[2].isdigit():
        raise ValueError("Currency and account code segments must be numeric")


# ============================================================
# GL Creator
# ============================================================

def create_gl_account(
    *,
    maker_user_id: str,
    maker_department: str,
    account_no: str,
    name: str,
    type: str,
    group: str,
) -> Dict[str, Any]:

    # --------------------------------------------------------
    # Authority Enforcement
    # --------------------------------------------------------
    _enforce_gl_authority(maker_department)

    # --------------------------------------------------------
    # Numbering Validation
    # --------------------------------------------------------
    _validate_gl_account_number(account_no)

    registry = _load_registry()

    if account_no in registry:
        raise ValueError("GL account already exists.")

    record = {
        "account_no": account_no,
        "name": name,
        "type": type.upper(),
        "group": group.upper(),
        "created_by": maker_user_id,
        "created_department": maker_department,
        "created_at": _now(),
        "status": "ACTIVE",
    }

    registry[account_no] = record
    _save_registry(registry)

    # --------------------------------------------------------
    # Audit Log
    # --------------------------------------------------------
    _log_event({
        "event_type": "GL_ACCOUNT_CREATE",
        "account_no": account_no,
        "maker_user_id": maker_user_id,
        "department": maker_department,
        "timestamp": _now(),
    })

    return {
        "ok": True,
        "account_no": account_no,
        "status": "ACTIVE",
    }
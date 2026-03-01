"""
Capital Strata Systems (CSS)
Phase 23.2 — Account Creation Authority Enforcement

Hard Controls:
- Only CUSTOMER_SERVICE department may create CUSTOMER accounts
- Only GL accounts with 000- prefix allowed as control GL
- Strict KYC fields required
- Duplicate detection (DOB + Email)
- Audit event logging
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

ACCOUNT_REGISTRY = Path("backend/app/ledger/account_registry.json")
ACCOUNT_EVENTS = Path("audit_logs/account_events.jsonl")


# ============================================================
# Utilities
# ============================================================

def _now():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_files():
    ACCOUNT_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNT_EVENTS.parent.mkdir(parents=True, exist_ok=True)

    if not ACCOUNT_REGISTRY.exists():
        ACCOUNT_REGISTRY.write_text("{}", encoding="utf-8")

    if not ACCOUNT_EVENTS.exists():
        ACCOUNT_EVENTS.write_text("", encoding="utf-8")


def _load_registry() -> Dict[str, Any]:
    _ensure_files()
    if ACCOUNT_REGISTRY.stat().st_size == 0:
        return {}
    with ACCOUNT_REGISTRY.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_registry(data: Dict[str, Any]):
    with ACCOUNT_REGISTRY.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _log_event(event: Dict[str, Any]):
    with ACCOUNT_EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


# ============================================================
# Authority Gate
# ============================================================

def _enforce_department_authority(maker_department: str):
    if maker_department.strip().upper() != "CUSTOMER_SERVICE":
        raise PermissionError(
            "Only CUSTOMER_SERVICE department can create new customer accounts."
        )


# ============================================================
# Duplicate Guard
# ============================================================

def _customer_uniqueness_guard(registry, email, dob):
    for acct in registry.values():
        if acct.get("category") == "CUSTOMER":
            if (
                acct.get("email", "").lower() == email.lower()
                and acct.get("date_of_birth") == dob
            ):
                raise ValueError(
                    "Duplicate customer detected: same DOB + Email already exists."
                )


# ============================================================
# Account Creator
# ============================================================

def create_customer_account(
    *,
    maker_user_id: str,
    maker_department: str,
    currency_num: str,
    product: str,
    control_gl_account_no: str,
    title: str,
    first_name: str,
    last_name: str,
    sex: str,
    date_of_birth: str,
    residential_address: str,
    email: str,
    phone: str,
    next_of_kin: str,
    signature_mandate: str,
    signature_status: str,
    preferred_contact_mode: str = "",
    next_of_kin_name: str = "",
    next_of_kin_phone: str = "",
    next_of_kin_email: str = "",
    business_segment: str = "",
    industry: str = "",
    business_address: str = "",
    rc_number: str = "",
) -> Dict[str, Any]:

    # --------------------------------------------------------
    # Authority Enforcement
    # --------------------------------------------------------
    _enforce_department_authority(maker_department)

    # --------------------------------------------------------
    # Control GL validation
    # --------------------------------------------------------
    if not control_gl_account_no.startswith("000-"):
        raise ValueError("Control GL account must start with 000-")

    registry = _load_registry()

    # --------------------------------------------------------
    # Duplicate Check
    # --------------------------------------------------------
    _customer_uniqueness_guard(registry, email, date_of_birth)

    # --------------------------------------------------------
    # Generate Account Number
    # --------------------------------------------------------
    base = f"CUST-{currency_num}-000"
    counter = 1
    while True:
        acct_no = f"{base}{counter:05d}"
        if acct_no not in registry:
            break
        counter += 1

    # --------------------------------------------------------
    # Create Record
    # --------------------------------------------------------
    record = {
        "account_no": acct_no,
        "category": "CUSTOMER",
        "status": "ACTIVE",
        "currency": currency_num,
        "product": product,
        "control_gl_account_no": control_gl_account_no,
        "created_by": maker_user_id,
        "created_department": maker_department,
        "created_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "last_customer_activity_date": None,

        # KYC Core
        "title": title,
        "first_name": first_name,
        "last_name": last_name,
        "sex": sex,
        "date_of_birth": date_of_birth,
        "residential_address": residential_address,
        "email": email,
        "phone": phone,

        # Contact
        "preferred_contact_mode": preferred_contact_mode,

        # NOK
        "next_of_kin": next_of_kin,
        "next_of_kin_name": next_of_kin_name,
        "next_of_kin_phone": next_of_kin_phone,
        "next_of_kin_email": next_of_kin_email,

        # Business Fields
        "business_segment": business_segment,
        "industry": industry,
        "business_address": business_address,
        "rc_number": rc_number,

        # Mandate
        "signature_mandate": signature_mandate,
        "signature_status": signature_status,
    }

    registry[acct_no] = record
    _save_registry(registry)

    # --------------------------------------------------------
    # Audit Log
    # --------------------------------------------------------
    _log_event({
        "event_type": "ACCOUNT_CREATE",
        "account_no": acct_no,
        "maker_user_id": maker_user_id,
        "department": maker_department,
        "timestamp": _now(),
    })

    return {
        "ok": True,
        "account_no": acct_no,
        "status": "ACTIVE",
        "category": "CUSTOMER",
    }
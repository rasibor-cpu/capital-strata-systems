"""
backend/app/ledger/account_create.py
Capital Strata Systems (CSS)

Phase 23D+ — Account Creation Governance + System-Generated Customer Accounts (KYC-Ready)
Phase 23D.1 — Numbering Schema Validation
Phase 23D.2 — Account Events Audit Logging (JSONL)

Governance (LOCKED):
- Only Customer Service department can create NEW customer accounts.
- Only Super User / FinCon departments can create NEW GL ledger accounts.

Authoritative Sources:
- Structural COA (GL only): backend/app/config/chart_of_accounts.json
- Runtime registry (GL states + CUSTOMER accounts): backend/app/ledger/account_registry.json
- Sequences: audit_logs/account_sequences.json
- Account events (audit trail): audit_logs/account_events.jsonl

Customer account creation:
- System-generated account numbers only (no manual entry)
- Enforced mandatory KYC / identifier fields (per your spec)
- Stored as runtime registry record with category="CUSTOMER"
- Linked to a control GL account (e.g., Customer Deposits – Demand control GL)
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List


COA_FILE = Path("backend/app/config/chart_of_accounts.json")
RUNTIME_REGISTRY_FILE = Path("backend/app/ledger/account_registry.json")
SEQUENCE_FILE = Path("audit_logs/account_sequences.json")
ACCOUNT_EVENTS_FILE = Path("audit_logs/account_events.jsonl")

# -------------------------------
# Numbering schema (hard rules)
# -------------------------------
GL_ACCT_RE = re.compile(r"^000-\d{3}-\d{3}$")          # e.g. 000-840-300
CUST_ACCT_RE = re.compile(r"^CUST-\d{3}-\d{8}$")       # e.g. CUST-840-00000001


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _utc_ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _append_event(event: Dict[str, Any]) -> None:
    """
    Immutable-ish audit trail for account lifecycle events (JSONL).
    """
    ACCOUNT_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = dict(event)
    record.setdefault("event_id", f"EVT-{uuid.uuid4().hex.upper()}")
    record.setdefault("ts_utc", _utc_ts())

    with ACCOUNT_EVENTS_FILE.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _require_dept(department: str, allowed: set[str], action: str) -> None:
    dept = (department or "").strip().upper()
    if dept not in allowed:
        raise PermissionError(f"{action} blocked: department '{department}' not authorized.")


def _normalize_email(email: str) -> str:
    e = (email or "").strip().lower()
    if not e:
        return ""
    # minimal validation
    if "@" not in e or "." not in e.split("@")[-1]:
        raise ValueError("Invalid email address format.")
    return e


def _normalize_phone(phone: str) -> str:
    p = (phone or "").strip()
    if not p:
        return ""
    # allow +, digits, spaces, hyphen, parentheses
    if not re.fullmatch(r"[0-9+\-\s()]{7,25}", p):
        raise ValueError("Invalid phone number format.")
    return p


def _parse_dob(dob_ymd: str) -> str:
    s = (dob_ymd or "").strip()
    if not s:
        raise ValueError("date_of_birth is required (YYYY-MM-DD).")
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        raise ValueError("date_of_birth must be YYYY-MM-DD.")
    return s


def _load_coa_accounts_by_no() -> Dict[str, Dict[str, Any]]:
    data = _load_json(COA_FILE, {})
    accounts = data.get("accounts", [])
    if not isinstance(accounts, list):
        raise ValueError("chart_of_accounts.json invalid: 'accounts' must be a list")
    out: Dict[str, Dict[str, Any]] = {}
    for a in accounts:
        if isinstance(a, dict):
            acc_no = str(a.get("account_no", "")).strip()
            if acc_no:
                out[acc_no] = a
    return out


def _load_runtime_registry() -> Dict[str, Any]:
    data = _load_json(RUNTIME_REGISTRY_FILE, {})
    if not isinstance(data, dict):
        raise ValueError("account_registry.json invalid: must be a JSON object keyed by account_no")
    return data


def _save_runtime_registry(reg: Dict[str, Any]) -> None:
    _save_json(RUNTIME_REGISTRY_FILE, reg)


def _next_seq(key: str) -> int:
    seq = _load_json(SEQUENCE_FILE, {})
    if not isinstance(seq, dict):
        seq = {}
    seq[key] = int(seq.get(key, 0)) + 1
    _save_json(SEQUENCE_FILE, seq)
    return int(seq[key])


def _validate_gl_account_no(account_no: str) -> None:
    if not GL_ACCT_RE.fullmatch(account_no):
        raise ValueError(f"Invalid GL account_no '{account_no}'. Expected format: 000-<CUR>-<NNN> (e.g., 000-840-300)")


def _validate_customer_account_no(account_no: str) -> None:
    if not CUST_ACCT_RE.fullmatch(account_no):
        raise ValueError(f"Invalid CUSTOMER account_no '{account_no}'. Expected format: CUST-<CUR>-<8digits> (e.g., CUST-840-00000001)")


def _customer_uniqueness_guard(reg: Dict[str, Any], *, email: str, phone: str, dob: str) -> None:
    """
    Prevent duplicate customer identities (pragmatic control):
    - If an existing CUSTOMER record has same (dob + email) OR (dob + phone) => block.
    This is not a full CIF solution, but it prevents obvious duplication.
    """
    email = (email or "").strip().lower()
    phone = (phone or "").strip()
    dob = (dob or "").strip()

    if not dob:
        return

    for acc_no, meta in reg.items():
        if not isinstance(meta, dict):
            continue
        if str(meta.get("category", "")).upper() != "CUSTOMER":
            continue
        prof = meta.get("customer_profile") or {}
        if not isinstance(prof, dict):
            continue

        edob = str(prof.get("date_of_birth", "")).strip()
        eemail = str(prof.get("email", "")).strip().lower()
        ephone = str(prof.get("phone", "")).strip()

        if edob and edob == dob:
            if email and eemail and eemail == email:
                raise ValueError("Duplicate customer detected: same DOB + Email already exists.")
            if phone and ephone and ephone == phone:
                raise ValueError("Duplicate customer detected: same DOB + Phone already exists.")


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------

def create_customer_account(
    *,
    maker_user_id: str,
    maker_department: str,
    currency_num: str = "840",
    product: str = "DEMAND_DEPOSIT",
    control_gl_account_no: str = "000-840-300",

    # ---- Mandatory identifier / KYC fields (your spec) ----
    title: str,
    first_name: str,
    last_name: str,
    other_names: str = "",
    sex: str = "",
    date_of_birth: str = "",
    residential_address: str = "",
    email: str = "",
    phone: str = "",
    next_of_kin: str = "",
    signature_mandate: str = "",
    signature_status: str = "",

    # ---- Additional fields for segmentation / unique identification ----
    customer_type: str = "INDIVIDUAL",  # INDIVIDUAL | BUSINESS
    rc_number: str = "",
    business_segment: str = "",
    industry: str = "",
    business_address: str = "",
) -> Dict[str, Any]:
    """
    Creates a NEW customer account (system-generated account number).

    Authorization:
      - maker_department must be CUSTOMER_SERVICE

    Enforces:
      - Mandatory KYC fields
      - Uniqueness guard (DOB+Email or DOB+Phone)
      - Control GL must exist in COA and be a valid GL account_no
      - Account number is system-generated and validated

    Returns:
      {"ok": True, "account_no": "...", "record": {...}}
    """
    _require_dept(maker_department, {"CUSTOMER_SERVICE"}, "Create customer account")

    currency_num = str(currency_num).strip()
    if not re.fullmatch(r"\d{3}", currency_num):
        raise ValueError("currency_num must be a 3-digit numeric currency code (e.g., 840).")

    # Validate control GL account format + existence
    control_gl_account_no = str(control_gl_account_no).strip()
    _validate_gl_account_no(control_gl_account_no)

    coa = _load_coa_accounts_by_no()
    if control_gl_account_no not in coa:
        raise ValueError(f"Control GL account not found in COA: {control_gl_account_no}")

    # Mandatory fields validation
    title = (title or "").strip()
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    if not title:
        raise ValueError("title is required.")
    if not first_name:
        raise ValueError("first_name is required.")
    if not last_name:
        raise ValueError("last_name is required.")

    sex = (sex or "").strip().upper()
    if sex and sex not in {"M", "F", "MALE", "FEMALE"}:
        raise ValueError("sex must be one of: M/F/MALE/FEMALE (or blank).")

    dob = _parse_dob(date_of_birth)
    residential_address = (residential_address or "").strip()
    if not residential_address:
        raise ValueError("residential_address is required.")

    email_n = _normalize_email(email)
    phone_n = _normalize_phone(phone)
    if not email_n:
        raise ValueError("email is required.")
    if not phone_n:
        raise ValueError("phone is required.")

    next_of_kin = (next_of_kin or "").strip()
    if not next_of_kin:
        raise ValueError("next_of_kin is required.")

    signature_mandate = (signature_mandate or "").strip().upper()
    signature_status = (signature_status or "").strip().upper()
    if not signature_mandate:
        raise ValueError("signature_mandate is required.")
    if not signature_status:
        raise ValueError("signature_status is required.")

    customer_type = (customer_type or "INDIVIDUAL").strip().upper()
    if customer_type not in {"INDIVIDUAL", "BUSINESS"}:
        raise ValueError("customer_type must be INDIVIDUAL or BUSINESS.")

    # Business-specific requirements (if BUSINESS)
    rc_number = (rc_number or "").strip()
    business_segment = (business_segment or "").strip()
    industry = (industry or "").strip()
    business_address = (business_address or "").strip()
    if customer_type == "BUSINESS":
        if not rc_number:
            raise ValueError("rc_number is required for BUSINESS customers.")
        if not business_address:
            raise ValueError("business_address is required for BUSINESS customers.")
        if not industry:
            raise ValueError("industry is required for BUSINESS customers.")

    reg = _load_runtime_registry()

    # Guard against duplicate identity
    _customer_uniqueness_guard(reg, email=email_n, phone=phone_n, dob=dob)

    # Generate customer account number (system only)
    seq = _next_seq(f"CUST-{currency_num}")
    account_no = f"CUST-{currency_num}-{seq:08d}"
    _validate_customer_account_no(account_no)

    if account_no in reg:
        raise RuntimeError(f"Generated customer account already exists (unexpected): {account_no}")

    customer_profile = {
        "customer_type": customer_type,
        "title": title,
        "first_name": first_name,
        "last_name": last_name,
        "other_names": (other_names or "").strip(),
        "sex": sex,
        "date_of_birth": dob,
        "residential_address": residential_address,
        "email": email_n,
        "phone": phone_n,
        "next_of_kin": next_of_kin,
        "signature_mandate": signature_mandate,
        "signature_status": signature_status,

        # segmentation / identifiers
        "rc_number": rc_number,
        "business_segment": business_segment,
        "industry": industry,
        "business_address": business_address,
    }

    reg[account_no] = {
        "category": "CUSTOMER",
        "status": "ACTIVE",
        "currency_num": currency_num,
        "product": str(product).strip().upper(),
        "control_gl_account_no": control_gl_account_no,
        "created_by": str(maker_user_id or "UNKNOWN").strip() or "UNKNOWN",
        "created_department": str(maker_department or "").strip().upper(),
        "created_date": _utc_ymd(),
        "last_customer_activity_date": None,
        "customer_profile": customer_profile,
    }

    _save_runtime_registry(reg)

    _append_event({
        "event_type": "CUSTOMER_ACCOUNT_CREATED",
        "account_no": account_no,
        "currency_num": currency_num,
        "product": str(product).strip().upper(),
        "control_gl_account_no": control_gl_account_no,
        "maker_user_id": str(maker_user_id or "UNKNOWN"),
        "maker_department": str(maker_department or "").strip().upper(),
        "customer_type": customer_type,
        "email": email_n,
        "phone": phone_n,
        "date_of_birth": dob,
    })

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

    Enforces:
      - GL numbering schema format: 000-<CUR>-<NNN>
      - No duplicates in COA
    """
    _require_dept(maker_department, {"SUPER_USER", "FINCON"}, "Create GL account")

    account_no = str(account_no).strip()
    _validate_gl_account_no(account_no)

    name = (name or "").strip()
    if not name:
        raise ValueError("name is required for GL account creation.")

    acc_type = (acc_type or "").strip().upper()
    group = (group or "").strip().upper()
    if not acc_type:
        raise ValueError("acc_type is required.")
    if not group:
        raise ValueError("group is required.")

    data = _load_json(COA_FILE, {})
    accounts = data.get("accounts", [])
    if not isinstance(accounts, list):
        raise ValueError("chart_of_accounts.json invalid: 'accounts' must be a list")

    for a in accounts:
        if isinstance(a, dict) and str(a.get("account_no", "")).strip() == account_no:
            raise ValueError(f"GL account already exists in COA: {account_no}")

    new_acc = {
        "account_no": account_no,
        "name": name,
        "type": acc_type,
        "group": group,
    }

    accounts.append(new_acc)
    data["accounts"] = accounts
    _save_json(COA_FILE, data)

    _append_event({
        "event_type": "GL_ACCOUNT_CREATED",
        "account_no": account_no,
        "name": name,
        "type": acc_type,
        "group": group,
        "maker_user_id": str(maker_user_id or "UNKNOWN"),
        "maker_department": str(maker_department or "").strip().upper(),
    })

    return {"ok": True, "account_no": account_no, "added": new_acc}
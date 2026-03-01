"""
backend/app/ledger/account_create.py
Capital Strata Systems (CSS)

Phase 23D.1 — Numbering Schema Validation
Phase 23D.2 — Account Events Audit Logging (JSONL)
Phase 23D.3 — Customer Onboarding Profile Expansion (Account Opening Form fields)

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
- Stores full customer_profile (typical account opening form fields)
- Links to a control GL account (e.g., Customer Deposits – Demand control GL)

Important:
- We keep backward compatibility: existing required fields remain required.
- New fields are optional (UI/workflows can enforce completion later).
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


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
    if "@" not in e or "." not in e.split("@")[-1]:
        raise ValueError("Invalid email address format.")
    return e


def _normalize_phone(phone: str) -> str:
    p = (phone or "").strip()
    if not p:
        return ""
    if not re.fullmatch(r"[0-9+\-\s()]{7,25}", p):
        raise ValueError("Invalid phone number format.")
    return p


def _parse_ymd(d: str, field_name: str) -> str:
    s = (d or "").strip()
    if not s:
        return ""
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        raise ValueError(f"{field_name} must be YYYY-MM-DD.")
    return s


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
        raise ValueError(
            f"Invalid GL account_no '{account_no}'. Expected: 000-<CUR>-<NNN> (e.g., 000-840-300)"
        )


def _validate_customer_account_no(account_no: str) -> None:
    if not CUST_ACCT_RE.fullmatch(account_no):
        raise ValueError(
            f"Invalid CUSTOMER account_no '{account_no}'. Expected: CUST-<CUR>-<8digits> (e.g., CUST-840-00000001)"
        )


def _customer_uniqueness_guard(reg: Dict[str, Any], *, email: str, phone: str, dob: str) -> None:
    email = (email or "").strip().lower()
    phone = (phone or "").strip()
    dob = (dob or "").strip()
    if not dob:
        return

    for _, meta in reg.items():
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


def _normalize_contact_mode(mode: str) -> str:
    m = (mode or "").strip().upper()
    if not m:
        return ""
    allowed = {"EMAIL", "SMS", "PHONE_CALL", "WHATSAPP", "POSTAL_MAIL", "IN_APP"}
    if m not in allowed:
        raise ValueError(f"preferred_contact_mode must be one of {sorted(allowed)}")
    return m


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

    # ---- Core KYC fields (kept mandatory to preserve quality) ----
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

    # ---- Expanded account opening fields (optional; UI can enforce) ----
    # Contacts / preferences
    contact_email: str = "",              # preferred / alternate email
    home_phone: str = "",
    work_phone: str = "",
    preferred_contact_mode: str = "",     # EMAIL/SMS/PHONE_CALL/WHATSAPP/POSTAL_MAIL/IN_APP
    preferred_contact_time_window: str = "",  # e.g. "9AM-5PM"
    do_not_contact: bool = False,
    marketing_consent: bool = False,

    # Addresses
    mailing_address: str = "",            # if different from residential
    business_address: str = "",

    # Next of kin (structured)
    next_of_kin_name: str = "",
    next_of_kin_relationship: str = "",
    next_of_kin_phone: str = "",
    next_of_kin_home_phone: str = "",
    next_of_kin_email: str = "",
    next_of_kin_address: str = "",

    # Identity & demographics
    nationality: str = "",
    state_of_origin: str = "",
    lga: str = "",
    marital_status: str = "",
    occupation: str = "",
    employer_name: str = "",
    employer_address: str = "",
    id_type: str = "",                   # e.g. NIN/PASSPORT/DRIVERS_LICENSE
    id_number: str = "",
    id_issue_date: str = "",             # YYYY-MM-DD
    id_expiry_date: str = "",            # YYYY-MM-DD
    tax_id: str = "",                    # TIN/SSN/ITIN/etc
    bvn: str = "",                       # Nigeria BVN if applicable

    # Customer classification / segmentation
    customer_type: str = "INDIVIDUAL",   # INDIVIDUAL | BUSINESS
    rc_number: str = "",
    business_segment: str = "",
    industry: str = "",

) -> Dict[str, Any]:
    """
    Creates a NEW customer account (system-generated account number).

    Authorization:
      - maker_department must be CUSTOMER_SERVICE

    Enforces:
      - Mandatory core KYC fields
      - Uniqueness guard (DOB+Email or DOB+Phone)
      - Control GL must exist in COA
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

    # Mandatory fields validation (core)
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

    # Expanded validations (optional fields)
    contact_email_n = _normalize_email(contact_email) if (contact_email or "").strip() else ""
    home_phone_n = _normalize_phone(home_phone) if (home_phone or "").strip() else ""
    work_phone_n = _normalize_phone(work_phone) if (work_phone or "").strip() else ""
    pref_mode = _normalize_contact_mode(preferred_contact_mode)

    nok_phone_n = _normalize_phone(next_of_kin_phone) if (next_of_kin_phone or "").strip() else ""
    nok_home_phone_n = _normalize_phone(next_of_kin_home_phone) if (next_of_kin_home_phone or "").strip() else ""
    nok_email_n = _normalize_email(next_of_kin_email) if (next_of_kin_email or "").strip() else ""

    id_issue = _parse_ymd(id_issue_date, "id_issue_date")
    id_exp = _parse_ymd(id_expiry_date, "id_expiry_date")

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
        # Core identity
        "customer_type": customer_type,
        "title": title,
        "first_name": first_name,
        "last_name": last_name,
        "other_names": (other_names or "").strip(),
        "sex": sex,
        "date_of_birth": dob,

        # Primary contact
        "email": email_n,
        "phone": phone_n,
        "contact_email": contact_email_n,
        "home_phone": home_phone_n,
        "work_phone": work_phone_n,

        # Addresses
        "residential_address": residential_address,
        "mailing_address": (mailing_address or "").strip(),
        "business_address": business_address,

        # Preferences / consent
        "preferred_contact_mode": pref_mode,
        "preferred_contact_time_window": (preferred_contact_time_window or "").strip(),
        "do_not_contact": bool(do_not_contact),
        "marketing_consent": bool(marketing_consent),

        # NOK (both a free-text legacy field + structured block)
        "next_of_kin": next_of_kin,
        "next_of_kin_name": (next_of_kin_name or "").strip(),
        "next_of_kin_relationship": (next_of_kin_relationship or "").strip(),
        "next_of_kin_phone": nok_phone_n,
        "next_of_kin_home_phone": nok_home_phone_n,
        "next_of_kin_email": nok_email_n,
        "next_of_kin_address": (next_of_kin_address or "").strip(),

        # Demographics / employment
        "nationality": (nationality or "").strip(),
        "state_of_origin": (state_of_origin or "").strip(),
        "lga": (lga or "").strip(),
        "marital_status": (marital_status or "").strip(),
        "occupation": (occupation or "").strip(),
        "employer_name": (employer_name or "").strip(),
        "employer_address": (employer_address or "").strip(),

        # IDs / compliance
        "id_type": (id_type or "").strip().upper(),
        "id_number": (id_number or "").strip(),
        "id_issue_date": id_issue,
        "id_expiry_date": id_exp,
        "tax_id": (tax_id or "").strip(),
        "bvn": (bvn or "").strip(),

        # Segmentation
        "rc_number": rc_number,
        "business_segment": business_segment,
        "industry": industry,
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
        "preferred_contact_mode": pref_mode,
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
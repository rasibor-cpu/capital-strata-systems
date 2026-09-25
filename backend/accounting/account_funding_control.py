from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
FUNDING_FILE = ARTIFACTS_DIR / "css_account_funding_requests.json"
MARGIN_FILE = ARTIFACTS_DIR / "css_margin_setoff_controls.json"

FUNDING_STATUSES = {"PENDING_VERIFICATION", "VERIFIED", "REJECTED", "REVERSED"}
MARGIN_STATUSES = {"DISABLED", "PENDING", "ACTIVE_VERIFIED", "SUSPENDED"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decimal(value: Any, *, field: str = "amount") -> Decimal:
    try:
        number = Decimal(str(value if value not in (None, "") else "0"))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field} must be numeric")
    if number < 0:
        raise ValueError(f"{field} cannot be negative")
    return number


def _load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return default


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp, path)


def submit_funding_request(
    *,
    user_id: str,
    amount: Any,
    currency: str,
    funding_method: str,
    external_reference: str,
) -> dict[str, Any]:
    uid = str(user_id or "").strip()
    if not uid:
        raise ValueError("user_id is required")
    value = _decimal(amount)
    if value <= 0:
        raise ValueError("amount must be greater than zero")
    curr = str(currency or "").strip().upper()
    if not curr:
        raise ValueError("currency is required")
    method = str(funding_method or "").strip().upper()
    if not method:
        raise ValueError("funding_method is required")

    payload = _load(FUNDING_FILE, {"requests": []})
    rows = payload.get("requests") if isinstance(payload, dict) and isinstance(payload.get("requests"), list) else []
    request = {
        "funding_id": "FND-" + uuid.uuid4().hex[:16].upper(),
        "user_id": uid,
        "amount": format(value, "f"),
        "currency": curr,
        "funding_method": method,
        "external_reference": str(external_reference or "").strip(),
        "status": "PENDING_VERIFICATION",
        "submitted_at": _utc_now(),
        "verified_at": None,
        "verification_source": None,
        "verification_reference": None,
        "credited_to_available_balance": False,
    }
    rows.append(request)
    _write(FUNDING_FILE, {"schema_version": "css.account.funding.v1", "requests": rows})
    return request


def record_funding_verification(
    *,
    funding_id: str,
    status: str,
    verification_source: str,
    verification_reference: str,
) -> dict[str, Any]:
    target = str(funding_id or "").strip()
    outcome = str(status or "").strip().upper()
    if outcome not in FUNDING_STATUSES - {"PENDING_VERIFICATION"}:
        raise ValueError("invalid funding verification status")
    source = str(verification_source or "").strip()
    reference = str(verification_reference or "").strip()
    if outcome == "VERIFIED" and (not source or not reference):
        raise ValueError("verified funding requires external verification source and reference")

    payload = _load(FUNDING_FILE, {"requests": []})
    rows = payload.get("requests") if isinstance(payload, dict) and isinstance(payload.get("requests"), list) else []
    for row in rows:
        if isinstance(row, dict) and str(row.get("funding_id")) == target:
            row["status"] = outcome
            row["verified_at"] = _utc_now()
            row["verification_source"] = source
            row["verification_reference"] = reference
            row["credited_to_available_balance"] = outcome == "VERIFIED"
            _write(FUNDING_FILE, {"schema_version": "css.account.funding.v1", "requests": rows})
            return dict(row)
    raise ValueError("funding request not found")


def funding_requests_for_user(user_id: str) -> list[dict[str, Any]]:
    uid = str(user_id or "").strip()
    payload = _load(FUNDING_FILE, {"requests": []})
    rows = payload.get("requests") if isinstance(payload, dict) and isinstance(payload.get("requests"), list) else []
    return [dict(row) for row in rows if isinstance(row, dict) and str(row.get("user_id")) == uid]


def save_margin_setoff_control(
    *,
    user_id: str,
    status: str,
    currency: str,
    margin_limit: Any,
    linked_credit_account_alias: str,
    setoff_form_version: str,
    setoff_executed: bool,
    actor_user_id: str,
) -> dict[str, Any]:
    uid = str(user_id or "").strip()
    if not uid:
        raise ValueError("user_id is required")
    state = str(status or "DISABLED").strip().upper()
    if state not in MARGIN_STATUSES:
        raise ValueError("invalid margin status")
    limit_value = _decimal(margin_limit, field="margin_limit")
    form_version = str(setoff_form_version or "").strip()
    if state == "ACTIVE_VERIFIED" and (not setoff_executed or not form_version):
        raise ValueError("active verified margin requires an executed set-off instruction")

    payload = _load(MARGIN_FILE, {"profiles": {}})
    profiles = payload.get("profiles") if isinstance(payload, dict) and isinstance(payload.get("profiles"), dict) else {}
    profile = {
        "user_id": uid,
        "status": state,
        "currency": str(currency or "USD").strip().upper() or "USD",
        "margin_limit": format(limit_value, "f"),
        "linked_credit_account_alias": str(linked_credit_account_alias or "").strip(),
        "setoff_form_version": form_version,
        "setoff_executed": bool(setoff_executed),
        "setoff_executed_at": _utc_now() if setoff_executed else None,
        "configured_by": str(actor_user_id or ""),
        "configured_at": _utc_now(),
    }
    profiles[uid] = profile
    _write(MARGIN_FILE, {"schema_version": "css.margin.setoff.v1", "profiles": profiles})
    return profile


def margin_control_for_user(user_id: str) -> dict[str, Any]:
    uid = str(user_id or "").strip()
    payload = _load(MARGIN_FILE, {"profiles": {}})
    profiles = payload.get("profiles") if isinstance(payload, dict) and isinstance(payload.get("profiles"), dict) else {}
    row = profiles.get(uid)
    return dict(row) if isinstance(row, dict) else {
        "user_id": uid,
        "status": "DISABLED",
        "margin_limit": "0",
        "setoff_executed": False,
    }


def assess_trade_funding(
    *,
    requested_amount: Any,
    currency: str,
    account_summary: Mapping[str, Any] | None,
    margin_control: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    request = _decimal(requested_amount, field="requested_amount")
    summary = dict(account_summary or {})
    available_row = summary.get("available_to_trade") if isinstance(summary.get("available_to_trade"), Mapping) else {}
    margin_row = summary.get("margin_available") if isinstance(summary.get("margin_available"), Mapping) else {}

    requested_currency = str(currency or "").strip().upper()
    available_currency = str(available_row.get("currency") or "").strip().upper()
    available_verified = (
        available_row.get("availability_state") == "AVAILABLE"
        and available_row.get("verification_state") in {"VERIFIED", "BROKER_VERIFIED", "SIMULATED_VERIFIED"}
        and available_currency == requested_currency
    )
    available_value = _decimal(available_row.get("value") or 0, field="available_to_trade")
    if available_verified and request <= available_value:
        return {
            "allowed": True,
            "funding_source": "AVAILABLE_CASH",
            "requested_amount": format(request, "f"),
            "available_amount": format(available_value, "f"),
            "margin_used": "0",
            "reason": "VERIFIED_AVAILABLE_BALANCE_SUFFICIENT",
        }

    margin = dict(margin_control or {})
    margin_active = (
        str(margin.get("status") or "").upper() == "ACTIVE_VERIFIED"
        and bool(margin.get("setoff_executed"))
        and str(margin.get("currency") or "").upper() == requested_currency
    )
    margin_verified = (
        margin_row.get("availability_state") == "AVAILABLE"
        and margin_row.get("verification_state") in {"VERIFIED", "BROKER_VERIFIED", "SIMULATED_VERIFIED"}
    )
    margin_available = _decimal(margin_row.get("value") or 0, field="margin_available")
    facility_limit = _decimal(margin.get("margin_limit") or 0, field="margin_limit")
    shortfall = max(Decimal("0"), request - available_value)
    usable_margin = min(margin_available, facility_limit)

    if margin_active and margin_verified and shortfall <= usable_margin:
        return {
            "allowed": True,
            "funding_source": "AVAILABLE_CASH_PLUS_VERIFIED_MARGIN",
            "requested_amount": format(request, "f"),
            "available_amount": format(available_value, "f"),
            "margin_used": format(shortfall, "f"),
            "reason": "VERIFIED_MARGIN_AND_SETOFF_SUFFICIENT",
        }

    return {
        "allowed": False,
        "funding_source": "NONE",
        "requested_amount": format(request, "f"),
        "available_amount": format(available_value, "f"),
        "margin_used": "0",
        "reason": (
            "UNVERIFIED_OR_INSUFFICIENT_AVAILABLE_BALANCE"
            if not margin_active
            else "INSUFFICIENT_VERIFIED_MARGIN_OR_SETOFF_COVER"
        ),
    }


__all__ = [
    "FUNDING_STATUSES",
    "MARGIN_STATUSES",
    "assess_trade_funding",
    "funding_requests_for_user",
    "margin_control_for_user",
    "record_funding_verification",
    "save_margin_setoff_control",
    "submit_funding_request",
]

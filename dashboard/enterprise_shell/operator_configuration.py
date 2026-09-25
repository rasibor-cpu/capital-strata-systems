from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
BROKER_SELECTION_FILE = ARTIFACTS_DIR / "css_operator_broker_selection.json"
USER_ACCOUNT_CONFIG_FILE = ARTIFACTS_DIR / "css_user_account_configuration.json"

VALID_BROKERS = ("COINBASE", "OANDA", "QUESTRADE", "BINANCE")
VALID_BROKER_MODES = ("PAPER", "LIVE_READ_ONLY")
VALID_USER_MODES = ("SELF_DIRECTED", "CSS_ADVISORY_CONFIRM")
VALID_ACCESS_CHARGE_TYPES = ("NONE", "FIXED_MONTHLY", "FIXED_ANNUAL")
VALID_TRADE_COMMISSION_BASES = (
    "NONE",
    "PERCENT_PROFIT",
    "FIXED_PER_TRADE",
    "PERCENT_NOTIONAL",
)
VALID_INDEPENDENT_TRADE_FEE_BASES = (
    "NONE",
    "FIXED_PER_TRADE",
    "PERCENT_NOTIONAL",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, default: Any) -> Any:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _atomic_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def _choice(value: Any, allowed: tuple[str, ...], field: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(allowed)}")
    return normalized


def _nonnegative_decimal(value: Any, field: str) -> str:
    raw = str(value if value not in (None, "") else "0").strip()
    try:
        number = Decimal(raw)
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field} must be numeric")
    if number < 0:
        raise ValueError(f"{field} cannot be negative")
    return format(number, "f")


def _rate(value: Any, field: str, basis: str) -> str:
    result = _nonnegative_decimal(value, field)
    if basis.startswith("PERCENT_") and Decimal(result) > Decimal("100"):
        raise ValueError(f"{field} cannot exceed 100 percent")
    return result



def broker_row_selectable(row: dict[str, Any]) -> bool:
    state = str(row.get("operational_state") or row.get("status") or "").strip().upper()
    readiness = str(row.get("readiness") or "").strip().upper()
    certification = str(row.get("certification") or "").strip().upper()
    unavailable_tokens = (
        "CONFIGURATION_REQUIRED",
        "CREDENTIALS_REQUIRED",
        "NOT_INITIALIZED",
        "DISABLED",
        "UNAVAILABLE",
        "EVIDENCE_MISSING",
        "FAIL_CLOSED",
        "REACTIVATION_REQUIRED",
    )
    combined = " ".join((state, readiness, certification))
    return not any(token in combined for token in unavailable_tokens)



def load_broker_selection() -> dict[str, Any]:
    raw = _load_json(BROKER_SELECTION_FILE, {})
    return dict(raw) if isinstance(raw, dict) else {}


def save_broker_selection(*, broker: str, broker_mode: str, actor_user_id: str, confirmed: bool = False) -> dict[str, Any]:
    selected = _choice(broker, VALID_BROKERS, "broker")
    mode = _choice(broker_mode, VALID_BROKER_MODES, "broker_mode")
    if not confirmed:
        raise ValueError("broker selection must be explicitly confirmed")
    payload = {
        "selected_broker": selected,
        "broker_mode": mode,
        "configured_by": str(actor_user_id or ""),
        "configured_at": _utc_now(),
        "confirmed": True,
        "confirmed_at": _utc_now(),
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        "runtime_application": "NEXT_SAFE_RECONCILIATION",
    }
    _atomic_write(BROKER_SELECTION_FILE, payload)
    return payload


def load_user_account_profiles() -> dict[str, dict[str, Any]]:
    raw = _load_json(USER_ACCOUNT_CONFIG_FILE, {})
    if not isinstance(raw, dict):
        return {}
    profiles = raw.get("profiles") if isinstance(raw.get("profiles"), dict) else raw
    return {
        str(user_id): dict(profile)
        for user_id, profile in profiles.items()
        if isinstance(profile, dict)
    }


def save_user_account_profile(
    *,
    user_id: str,
    role: str,
    user_mode: str,
    system_access_charge_type: str,
    system_access_charge_amount: Any,
    system_access_currency: str,
    trade_commission_basis: str,
    trade_commission_rate: Any,
    independent_trade_fee_basis: str,
    independent_trade_fee_rate: Any,
    broker_charges_pass_through: bool,
    agreement_version: str,
    actor_user_id: str,
) -> dict[str, Any]:
    uid = str(user_id or "").strip()
    if not uid:
        raise ValueError("user_id is required")
    mode = _choice(user_mode, VALID_USER_MODES, "user_mode")
    access_type = _choice(system_access_charge_type, VALID_ACCESS_CHARGE_TYPES, "system_access_charge_type")
    trade_basis = _choice(trade_commission_basis, VALID_TRADE_COMMISSION_BASES, "trade_commission_basis")
    independent_basis = _choice(independent_trade_fee_basis, VALID_INDEPENDENT_TRADE_FEE_BASES, "independent_trade_fee_basis")
    version = str(agreement_version or "").strip()
    if not version:
        raise ValueError("agreement_version is required")

    profiles = load_user_account_profiles()
    prior = profiles.get(uid, {})
    profile = {
        "user_id": uid,
        "role": str(role or "").strip().upper(),
        "user_mode": mode,
        "system_access_charge": {
            "type": access_type,
            "amount": _nonnegative_decimal(system_access_charge_amount, "system_access_charge_amount"),
            "currency": str(system_access_currency or "USD").strip().upper() or "USD",
        },
        "trade_commission": {
            "basis": trade_basis,
            "rate": _rate(trade_commission_rate, "trade_commission_rate", trade_basis),
        },
        "independent_trade_platform_fee": {
            "basis": independent_basis,
            "rate": _rate(independent_trade_fee_rate, "independent_trade_fee_rate", independent_basis),
        },
        "broker_charges_pass_through": bool(broker_charges_pass_through),
        "agreement_version": version,
        "risk_acknowledgement_required": True,
        "execution_policy": (
            "USER_DIRECTED_ONLY"
            if mode == "SELF_DIRECTED"
            else "USER_CONFIRMATION_REQUIRED"
        ),
        "css_suggestions_enabled": mode == "CSS_ADVISORY_CONFIRM",
        "accepted_trade_execution_policy": (
            "ELIGIBLE_ONLY_WHEN_PLATFORM_CERTIFIED_AND_BROKER_ARMED"
            if mode == "CSS_ADVISORY_CONFIRM"
            else "NOT_APPLICABLE"
        ),
        "execution_allowed_now": False,
        "live_trading_blocked": True,
        "acceptance_status": "PENDING",
        "accepted_at": None,
        "accepted_by_user_id": None,
        "configured_by": str(actor_user_id or ""),
        "configured_at": _utc_now(),
        "previous_agreement_version": prior.get("agreement_version"),
    }
    profiles[uid] = profile
    _atomic_write(
        USER_ACCOUNT_CONFIG_FILE,
        {"schema_version": "css.user.account.configuration.v1", "profiles": profiles},
    )
    return profile


def accept_user_account_terms(*, user_id: str, actor_user_id: str, agreement_version: str) -> dict[str, Any]:
    uid = str(user_id or "").strip()
    actor = str(actor_user_id or "").strip()
    if not uid or actor != uid:
        raise PermissionError("Only the configured user may accept their own account terms")
    profiles = load_user_account_profiles()
    profile = profiles.get(uid)
    if not isinstance(profile, dict):
        raise ValueError("User account configuration is not available")
    if str(profile.get("agreement_version") or "") != str(agreement_version or "").strip():
        raise ValueError("Agreement version has changed; review the current terms before accepting")
    profile["acceptance_status"] = "ACCEPTED"
    profile["accepted_at"] = _utc_now()
    profile["accepted_by_user_id"] = actor
    profiles[uid] = profile
    _atomic_write(
        USER_ACCOUNT_CONFIG_FILE,
        {"schema_version": "css.user.account.configuration.v1", "profiles": profiles},
    )
    return dict(profile)


def public_user_account_configuration(users: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    profiles = load_user_account_profiles()
    return {
        "profiles": profiles,
        "users": list(users or []),
        "user_modes": list(VALID_USER_MODES),
        "access_charge_types": list(VALID_ACCESS_CHARGE_TYPES),
        "trade_commission_bases": list(VALID_TRADE_COMMISSION_BASES),
        "independent_trade_fee_bases": list(VALID_INDEPENDENT_TRADE_FEE_BASES),
        "execution_allowed": False,
        "live_trading_blocked": True,
    }


__all__ = [
    "VALID_BROKERS",
    "VALID_BROKER_MODES",
    "VALID_USER_MODES",
    "VALID_ACCESS_CHARGE_TYPES",
    "VALID_TRADE_COMMISSION_BASES",
    "VALID_INDEPENDENT_TRADE_FEE_BASES",
    "accept_user_account_terms",
    "broker_row_selectable",
    "load_broker_selection",
    "load_user_account_profiles",
    "public_user_account_configuration",
    "save_broker_selection",
    "save_user_account_profile",
]

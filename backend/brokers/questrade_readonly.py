from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _timestamp(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def parse_questrade_readonly_response(
    response: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Normalize a Questrade response without making or authorizing requests."""
    if not isinstance(response, Mapping):
        return {
            "status": "UNAVAILABLE",
            "reason_codes": ["BROKER_ERROR", "BALANCE_UNAVAILABLE"],
            "account": None,
            "balances": None,
            "positions": None,
            "activities": None,
            "data_timestamp": None,
            "read_only": True,
        }

    status = _text(response.get("status")).upper() or "AVAILABLE"
    error = _text(response.get("error") or response.get("error_code")).upper()
    if error in {"401", "AUTHENTICATION_REQUIRED", "AUTH_REQUIRED"}:
        status = "UNAVAILABLE"
        reason_codes = ["AUTHENTICATION_REQUIRED"]
    elif error in {"TOKEN_EXPIRED", "EXPIRED_TOKEN"}:
        status = "UNAVAILABLE"
        reason_codes = ["TOKEN_EXPIRED"]
    elif error:
        status = "UNAVAILABLE"
        reason_codes = ["BROKER_ERROR"]
    else:
        reason_codes = []

    accounts = _rows(response.get("accounts"))
    account = dict(accounts[0]) if accounts else (
        dict(response["account"]) if isinstance(response.get("account"), Mapping) else None
    )
    balances = response.get("balances")
    if balances is None and account is not None:
        balances = account.get("balances")
    balance_payload = dict(balances) if isinstance(balances, Mapping) else None
    positions_value = response.get("positions")
    activities_value = response.get("activities")
    positions = _rows(positions_value) if positions_value is not None else None
    activities = _rows(activities_value) if activities_value is not None else None

    if status == "AVAILABLE" and balance_payload is None:
        reason_codes.append("BALANCE_UNAVAILABLE")
    if status == "AVAILABLE" and positions is None:
        reason_codes.append("POSITIONS_UNAVAILABLE")

    data_timestamp = _timestamp(
        response.get("data_timestamp")
        or response.get("timestamp")
        or (balance_payload or {}).get("timestamp")
    )
    return {
        "status": status,
        "reason_codes": sorted(set(reason_codes)),
        "account": account,
        "balances": balance_payload,
        "positions": positions,
        "activities": activities,
        "data_timestamp": data_timestamp,
        "read_only": True,
        "account_count": len(accounts),
    }


__all__ = ["parse_questrade_readonly_response"]
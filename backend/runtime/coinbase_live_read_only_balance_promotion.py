from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.brokers.account_balance_contract import build_broker_balance_summary


SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY = "COINBASE_LIVE_READ_ONLY_BALANCE_ONLY"
ALLOWED_PROMOTION_MODES = frozenset({"LIVE", "LIVE_READ_ONLY"})
BROKER_SNAPSHOT_MAX_AGE_SECONDS = 300
_UNAVAILABLE = "UNAVAILABLE"
_AVAILABLE = "AVAILABLE"


def evaluate_canonical_broker_snapshot_freshness(
    snapshot: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    max_age_seconds: int = BROKER_SNAPSHOT_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    """Fail closed on missing, malformed, naive, future, or stale timestamps."""
    if not isinstance(snapshot, Mapping) or not snapshot:
        return {"ok": False, "reason": "missing_canonical_account_snapshot", "age_seconds": None}
    raw = _first_timestamp(snapshot)
    if raw in (None, ""):
        return {"ok": False, "reason": "missing_timestamp", "age_seconds": None}
    parsed, parse_reason = _parse_aware_utc(raw)
    if parsed is None:
        return {"ok": False, "reason": parse_reason, "age_seconds": None}
    clock = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    if clock.tzinfo is None:
        return {"ok": False, "reason": "naive_now_timestamp", "age_seconds": None}
    if parsed > clock + timedelta(seconds=1):
        return {"ok": False, "reason": "future_timestamp", "age_seconds": None}
    age = (clock - parsed).total_seconds()
    if age > float(max_age_seconds):
        return {"ok": False, "reason": "stale_timestamp", "age_seconds": age}
    return {"ok": True, "reason": "fresh", "age_seconds": age}


def coinbase_balance_only_promotion_allowed(
    *,
    selected_broker: Any,
    canonical_mode: Any,
    coinbase_validation: Mapping[str, Any] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    broker = str(selected_broker or "").strip().upper()
    mode = str(canonical_mode or "").strip().upper()
    validation = coinbase_validation if isinstance(coinbase_validation, Mapping) else {}
    broker_validation = _mapping(validation.get("broker_validation")) or validation
    snapshot = _canonical_account_snapshot(validation)
    validation_status = str(
        broker_validation.get("validation_status") or validation.get("validation_status") or ""
    ).strip().upper()
    balances_loaded = _is_true(
        snapshot.get("balances_loaded")
        if snapshot
        else None,
        broker_validation.get("balances_loaded"),
        validation.get("balances_loaded"),
    )
    reasons: list[str] = []
    if broker != "COINBASE":
        reasons.append("selected_broker_not_coinbase")
    if mode not in ALLOWED_PROMOTION_MODES:
        reasons.append("canonical_mode_not_live_read_family")
    if validation_status != "PASS":
        reasons.append("validation_status_not_pass")
    if not balances_loaded:
        reasons.append("balances_not_loaded")
    if not snapshot:
        reasons.append("canonical_account_snapshot_missing")
    freshness = evaluate_canonical_broker_snapshot_freshness(snapshot, now=now)
    if not freshness["ok"]:
        reasons.append(f"freshness_{freshness['reason']}")
    return {
        "allowed": not reasons,
        "reasons": reasons,
        "source": SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY if not reasons else _UNAVAILABLE,
        "snapshot": dict(snapshot) if snapshot else {},
        "freshness": freshness,
        "validation_status": validation_status or _UNAVAILABLE,
        "balances_loaded": balances_loaded,
        "selected_broker": broker or _UNAVAILABLE,
        "canonical_mode": mode or _UNAVAILABLE,
    }


def apply_coinbase_balance_only_promotion(
    dashboard_payload: Mapping[str, Any] | None,
    *,
    selected_broker: Any,
    canonical_mode: Any,
    coinbase_validation: Mapping[str, Any] | None,
    position_evidence: bool = False,
    pnl_evidence: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    payload = dict(dashboard_payload) if isinstance(dashboard_payload, Mapping) else {}
    decision = coinbase_balance_only_promotion_allowed(
        selected_broker=selected_broker,
        canonical_mode=canonical_mode,
        coinbase_validation=coinbase_validation,
        now=now,
    )
    payload["coinbase_balance_only_promotion"] = {
        "allowed": decision["allowed"],
        "reasons": list(decision["reasons"]),
        "source": decision["source"],
        "freshness": dict(decision["freshness"]),
        "validation_status": decision["validation_status"],
        "balances_loaded": decision["balances_loaded"],
    }
    if not decision["allowed"]:
        return payload

    snapshot = decision["snapshot"]
    account = dict(_mapping(payload.get("account_summary")))
    cash = snapshot.get("cash", snapshot.get("available_balance"))
    equity = snapshot.get("equity", snapshot.get("balance"))
    buying_power = snapshot.get("buying_power", snapshot.get("available_balance"))
    available_balance = snapshot.get("available_balance", snapshot.get("cash"))
    margin_available = snapshot.get("margin_available", snapshot.get("free_margin"))
    margin_used = snapshot.get("margin_required")
    account.update(
        {
            "account_balance": cash,
            "cash_balance": cash,
            "cash": cash,
            "total_equity": equity,
            "equity": equity,
            "buying_power": buying_power,
            "available_balance": available_balance,
            "available_margin": margin_available,
            "margin_used": margin_used,
            "currency": snapshot.get("currency") or account.get("currency") or "UNAVAILABLE",
            "broker": "COINBASE",
            "account_mode": str(canonical_mode or account.get("account_mode") or "LIVE_READ_ONLY"),
            "cash_balance_availability": _available_if_number(cash),
            "total_equity_availability": _available_if_number(equity),
            "buying_power_availability": _available_if_number(buying_power),
            "available_margin_availability": _available_if_number(margin_available),
            "margin_used_availability": _available_if_number(margin_used),
            "availability_state": _AVAILABLE
            if any(_is_number(value) for value in (cash, equity, buying_power, available_balance, margin_available))
            else _UNAVAILABLE,
            "source": SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY,
            "freshness": decision["freshness"].get("reason", "fresh"),
        }
    )
    account["broker_balance_summary"] = build_broker_balance_summary(
        account,
        broker="COINBASE",
        mode=str(canonical_mode or "LIVE_READ_ONLY"),
        as_of=str(snapshot.get("timestamp") or snapshot.get("balance_timestamp") or ""),
    )
    payload["account_summary"] = account

    pnl = dict(_mapping(payload.get("pnl_summary")))
    if not pnl_evidence:
        for field in ("realized_pnl", "unrealized_pnl", "net_pnl", "account_equity"):
            current = pnl.get(field)
            pnl[field] = current if _is_number(current) else 0.0
            pnl[f"{field}_availability"] = _UNAVAILABLE
        pnl["source"] = SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
        pnl["availability_state"] = _UNAVAILABLE
    payload["pnl_summary"] = pnl

    if not position_evidence:
        position_state = dict(_mapping(payload.get("position_state")))
        open_positions = dict(_mapping(payload.get("open_positions")))
        current_count = position_state.get("open_count", open_positions.get("total"))
        count = current_count if _is_int_like(current_count) else 0
        position_state["open_count"] = count
        position_state["open_count_availability"] = _UNAVAILABLE
        position_state["source"] = SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
        if not position_state.get("positions"):
            position_state["positions"] = []
        open_positions["total"] = count
        open_positions["total_availability"] = _UNAVAILABLE
        open_positions["source"] = SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
        payload["position_state"] = position_state
        payload["open_positions"] = open_positions
    return payload


def _canonical_account_snapshot(validation: Mapping[str, Any]) -> dict[str, Any]:
    broker_validation = _mapping(validation.get("broker_validation"))
    operational = _mapping(
        validation.get("broker_operational_status")
        or broker_validation.get("broker_operational_status")
    )
    for candidate in (
        broker_validation.get("canonical_account_snapshot"),
        broker_validation.get("account_snapshot"),
        operational.get("canonical_account_snapshot"),
        operational.get("account_snapshot"),
        validation.get("canonical_account_snapshot"),
        validation.get("account_snapshot"),
    ):
        if isinstance(candidate, Mapping) and candidate:
            return dict(candidate)
    return {}


def _first_timestamp(snapshot: Mapping[str, Any]) -> Any:
    for key in (
        "timestamp",
        "balance_timestamp",
        "as_of",
        "last_successful_sync",
        "validation_timestamp",
    ):
        value = snapshot.get(key)
        if value not in (None, ""):
            return value
    return None


def _parse_aware_utc(value: Any) -> tuple[datetime | None, str]:
    text = str(value).strip()
    if not text:
        return None, "missing_timestamp"
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None, "malformed_timestamp"
    if parsed.tzinfo is None:
        return None, "naive_timestamp"
    return parsed.astimezone(timezone.utc), "ok"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _is_true(*values: Any) -> bool:
    for value in values:
        if value is True:
            return True
        if isinstance(value, str) and value.strip().upper() in {"TRUE", "PASS", "OK", "AVAILABLE"}:
            return True
    return False


def _is_number(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _is_int_like(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


def _available_if_number(value: Any) -> str:
    return _AVAILABLE if _is_number(value) else _UNAVAILABLE


__all__ = [
    "ALLOWED_PROMOTION_MODES",
    "BROKER_SNAPSHOT_MAX_AGE_SECONDS",
    "SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY",
    "apply_coinbase_balance_only_promotion",
    "coinbase_balance_only_promotion_allowed",
    "evaluate_canonical_broker_snapshot_freshness",
]

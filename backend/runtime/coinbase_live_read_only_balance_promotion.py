from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.brokers.account_balance_contract import build_broker_balance_summary
from backend.executive_intelligence.freshness_policy import gate_config, load_freshness_policy


SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY = "COINBASE_LIVE_READ_ONLY_BALANCE_ONLY"
# Balance-only promotion is a LIVE_READ_ONLY evidence contract. RuntimeMode.LIVE is a
# distinct execution-capable mode and is excluded to avoid provenance ambiguity.
# This grant is read-only: it never arms a broker, starts an engine, or enables orders.
ALLOWED_PROMOTION_MODES = frozenset({"LIVE_READ_ONLY"})
COMPATIBLE_PNL_SOURCES = frozenset(
    {
        "COINBASE_LIVE_READ_ONLY",
        "COINBASE_LIVE_READ_ONLY_PNL",
    }
)
COMPATIBLE_POSITION_SOURCES = frozenset(
    {
        "COINBASE_LIVE_READ_ONLY",
        "COINBASE_LIVE_READ_ONLY_POSITIONS",
    }
)
_UNAVAILABLE = "UNAVAILABLE"
_AVAILABLE = "AVAILABLE"
_BROKER_SNAPSHOT_GATE = "broker_snapshot"


def resolve_broker_snapshot_max_age_seconds(
    policy: Mapping[str, Any] | None = None,
    *,
    policy_path: Path | str | None = None,
) -> dict[str, Any]:
    """Resolve canonical broker_snapshot max age. Fail closed if unusable."""
    try:
        if policy is None:
            loaded = load_freshness_policy(policy_path=policy_path)
        elif isinstance(policy, Mapping):
            loaded = dict(policy)
        else:
            return {"ok": False, "max_age_seconds": None, "reason": "policy_unusable"}
    except Exception:
        return {"ok": False, "max_age_seconds": None, "reason": "policy_unusable"}

    if not isinstance(loaded, dict) or not loaded:
        return {"ok": False, "max_age_seconds": None, "reason": "policy_missing"}

    gates = loaded.get("gates")
    if not isinstance(gates, dict):
        return {"ok": False, "max_age_seconds": None, "reason": "policy_malformed"}

    raw_gate = gates.get(_BROKER_SNAPSHOT_GATE)
    if raw_gate is None:
        return {"ok": False, "max_age_seconds": None, "reason": "broker_snapshot_gate_missing"}
    if not isinstance(raw_gate, dict):
        return {"ok": False, "max_age_seconds": None, "reason": "broker_snapshot_gate_malformed"}
    if "max_age_seconds" not in raw_gate:
        return {"ok": False, "max_age_seconds": None, "reason": "max_age_missing"}

    try:
        cfg = gate_config(loaded, _BROKER_SNAPSHOT_GATE)
    except Exception:
        return {"ok": False, "max_age_seconds": None, "reason": "gate_config_unusable"}
    if not isinstance(cfg, dict) or not cfg:
        return {"ok": False, "max_age_seconds": None, "reason": "broker_snapshot_gate_missing"}

    max_age = _positive_max_age(cfg.get("max_age_seconds"))
    if max_age is None:
        return {"ok": False, "max_age_seconds": None, "reason": "max_age_unusable"}
    return {"ok": True, "max_age_seconds": max_age, "reason": "ok"}


def evaluate_canonical_broker_snapshot_freshness(
    snapshot: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    policy: Mapping[str, Any] | None = None,
    policy_path: Path | str | None = None,
) -> dict[str, Any]:
    """Fail closed on missing, malformed, naive, future, or stale timestamps."""
    age_decision = resolve_broker_snapshot_max_age_seconds(policy, policy_path=policy_path)
    if not age_decision["ok"]:
        return {
            "ok": False,
            "reason": f"policy_{age_decision['reason']}",
            "age_seconds": None,
            "max_age_seconds": None,
        }
    max_age_seconds = float(age_decision["max_age_seconds"])
    if not isinstance(snapshot, Mapping) or not snapshot:
        return {
            "ok": False,
            "reason": "missing_canonical_account_snapshot",
            "age_seconds": None,
            "max_age_seconds": max_age_seconds,
        }
    raw = _first_timestamp(snapshot)
    if raw in (None, ""):
        return {
            "ok": False,
            "reason": "missing_timestamp",
            "age_seconds": None,
            "max_age_seconds": max_age_seconds,
        }
    parsed, parse_reason = _parse_aware_utc(raw)
    if parsed is None:
        return {
            "ok": False,
            "reason": parse_reason,
            "age_seconds": None,
            "max_age_seconds": max_age_seconds,
        }
    clock = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    if clock.tzinfo is None:
        return {
            "ok": False,
            "reason": "naive_now_timestamp",
            "age_seconds": None,
            "max_age_seconds": max_age_seconds,
        }
    if parsed > clock + timedelta(seconds=1):
        return {
            "ok": False,
            "reason": "future_timestamp",
            "age_seconds": None,
            "max_age_seconds": max_age_seconds,
        }
    age = (clock - parsed).total_seconds()
    if age > max_age_seconds:
        return {
            "ok": False,
            "reason": "stale_timestamp",
            "age_seconds": age,
            "max_age_seconds": max_age_seconds,
        }
    return {
        "ok": True,
        "reason": "fresh",
        "age_seconds": age,
        "max_age_seconds": max_age_seconds,
    }


def proven_independent_pnl_evidence(
    evidence: Any,
    *,
    now: datetime | None = None,
    policy: Mapping[str, Any] | None = None,
    policy_path: Path | str | None = None,
) -> bool:
    """True only with compatible Coinbase source plus freshness-gated timestamp."""
    return _proven_independent_evidence(
        evidence,
        compatible_sources=COMPATIBLE_PNL_SOURCES,
        now=now,
        policy=policy,
        policy_path=policy_path,
    )


def proven_independent_position_evidence(
    evidence: Any,
    *,
    now: datetime | None = None,
    policy: Mapping[str, Any] | None = None,
    policy_path: Path | str | None = None,
) -> bool:
    """True only with compatible Coinbase source plus freshness-gated timestamp."""
    return _proven_independent_evidence(
        evidence,
        compatible_sources=COMPATIBLE_POSITION_SOURCES,
        now=now,
        policy=policy,
        policy_path=policy_path,
    )


def coinbase_balance_only_promotion_allowed(
    *,
    selected_broker: Any,
    canonical_mode: Any,
    coinbase_validation: Mapping[str, Any] | None,
    now: datetime | None = None,
    policy: Mapping[str, Any] | None = None,
    policy_path: Path | str | None = None,
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
        snapshot.get("balances_loaded") if snapshot else None,
        broker_validation.get("balances_loaded"),
        validation.get("balances_loaded"),
    )
    reasons: list[str] = []
    if broker != "COINBASE":
        reasons.append("selected_broker_not_coinbase")
    if mode not in ALLOWED_PROMOTION_MODES:
        reasons.append("canonical_mode_not_live_read_only")
    if validation_status != "PASS":
        reasons.append("validation_status_not_pass")
    if not balances_loaded:
        reasons.append("balances_not_loaded")
    if not snapshot:
        reasons.append("canonical_account_snapshot_missing")
    freshness = evaluate_canonical_broker_snapshot_freshness(
        snapshot,
        now=now,
        policy=policy,
        policy_path=policy_path,
    )
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
    position_evidence: Any = False,
    pnl_evidence: Any = False,
    now: datetime | None = None,
    policy: Mapping[str, Any] | None = None,
    policy_path: Path | str | None = None,
) -> dict[str, Any]:
    payload = dict(dashboard_payload) if isinstance(dashboard_payload, Mapping) else {}
    decision = coinbase_balance_only_promotion_allowed(
        selected_broker=selected_broker,
        canonical_mode=canonical_mode,
        coinbase_validation=coinbase_validation,
        now=now,
        policy=policy,
        policy_path=policy_path,
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
        from backend.runtime.coinbase_spot_asset_balances import attach_spot_asset_balances

        return attach_spot_asset_balances(
            payload,
            decision=decision,
            coinbase_validation=coinbase_validation,
            selected_broker=selected_broker,
            canonical_mode=canonical_mode,
        )

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
    retain_pnl = _retain_independent_evidence(
        pnl_evidence,
        fallback=pnl,
        compatible_sources=COMPATIBLE_PNL_SOURCES,
        now=now,
        policy=policy,
        policy_path=policy_path,
    )
    if not retain_pnl:
        for field in ("realized_pnl", "unrealized_pnl", "net_pnl", "account_equity"):
            current = pnl.get(field)
            pnl[field] = current if _is_number(current) else 0.0
            pnl[f"{field}_availability"] = _UNAVAILABLE
        pnl["source"] = SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
        pnl["availability_state"] = _UNAVAILABLE
    payload["pnl_summary"] = pnl

    position_state = dict(_mapping(payload.get("position_state")))
    open_positions = dict(_mapping(payload.get("open_positions")))
    retain_positions = _retain_independent_evidence(
        position_evidence,
        fallback=position_state,
        compatible_sources=COMPATIBLE_POSITION_SOURCES,
        now=now,
        policy=policy,
        policy_path=policy_path,
    )
    if not retain_positions:
        current_count = position_state.get("open_count", open_positions.get("total"))
        count = current_count if _is_int_like(current_count) else 0
        position_state["open_count"] = count
        position_state["open_count_availability"] = _UNAVAILABLE
        position_state["source"] = SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
        if not isinstance(position_state.get("positions"), list):
            position_state["positions"] = []
        open_positions["total"] = count
        open_positions["total_availability"] = _UNAVAILABLE
        open_positions["source"] = SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
        payload["position_state"] = position_state
        payload["open_positions"] = open_positions
    from backend.runtime.coinbase_spot_asset_balances import attach_spot_asset_balances

    return attach_spot_asset_balances(
        payload,
        decision=decision,
        coinbase_validation=coinbase_validation,
        selected_broker=selected_broker,
        canonical_mode=canonical_mode,
    )


def _retain_independent_evidence(
    candidate: Any,
    *,
    fallback: Mapping[str, Any],
    compatible_sources: frozenset[str],
    now: datetime | None,
    policy: Mapping[str, Any] | None,
    policy_path: Path | str | None,
) -> bool:
    if candidate is False or candidate is None:
        return False
    evidence = candidate if isinstance(candidate, Mapping) else fallback
    if candidate is True:
        evidence = fallback
    return _proven_independent_evidence(
        evidence,
        compatible_sources=compatible_sources,
        now=now,
        policy=policy,
        policy_path=policy_path,
    )


def _proven_independent_evidence(
    evidence: Any,
    *,
    compatible_sources: frozenset[str],
    now: datetime | None,
    policy: Mapping[str, Any] | None,
    policy_path: Path | str | None,
) -> bool:
    if evidence is True or evidence is False or evidence is None:
        return False
    if not isinstance(evidence, Mapping) or not evidence:
        return False
    source = str(evidence.get("source") or "").strip().upper()
    if source not in compatible_sources:
        return False
    status = str(evidence.get("validation_status") or "").strip().upper()
    if status and status != "PASS":
        return False
    freshness = evaluate_canonical_broker_snapshot_freshness(
        evidence,
        now=now,
        policy=policy,
        policy_path=policy_path,
    )
    return bool(freshness.get("ok"))


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
        "pnl_timestamp",
        "positions_timestamp",
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


def _positive_max_age(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        value = text
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed or parsed <= 0 or parsed == float("inf"):
        return None
    return parsed


__all__ = [
    "ALLOWED_PROMOTION_MODES",
    "COMPATIBLE_PNL_SOURCES",
    "COMPATIBLE_POSITION_SOURCES",
    "SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY",
    "apply_coinbase_balance_only_promotion",
    "coinbase_balance_only_promotion_allowed",
    "evaluate_canonical_broker_snapshot_freshness",
    "proven_independent_pnl_evidence",
    "proven_independent_position_evidence",
    "resolve_broker_snapshot_max_age_seconds",
]

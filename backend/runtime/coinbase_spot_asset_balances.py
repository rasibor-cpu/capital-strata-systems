"""Coinbase LIVE_READ_ONLY spot / account asset balance exposure (not positions)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from backend.runtime.coinbase_live_read_only_balance_promotion import (
    SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY,
    _canonical_account_snapshot,
    _first_timestamp,
    _is_number,
    _mapping,
    coinbase_balance_only_promotion_allowed,
)


_AVAILABLE = "AVAILABLE"
_UNAVAILABLE = "UNAVAILABLE"
SECTION_KIND = "spot_asset_balances"
# No reliable fiat/crypto classifier exists in-repo. Present every trustworthy
# balance row under this label rather than guessing cash vs non-cash.
SECTION_LABEL = "Account Asset Balances"
SYNTHETIC_ACCOUNT_IDS = frozenset(
    {"", "UNKNOWN", "UNKNOWN_ID", "FALLBACK-COINBASE", "NONE", "NULL", "N/A"}
)
_SECRET_ACCOUNT_ID_TOKENS = ("secret", "private", "token", "key", "passphrase", "signature")
_FORBIDDEN_POSITION_LABELS = frozenset(
    {
        "open positions",
        "trades",
        "futures positions",
        "options positions",
        "leveraged positions",
    }
)


def unavailable_spot_asset_balances(
    *,
    reason: str,
    source: str = _UNAVAILABLE,
    timestamp: str = _UNAVAILABLE,
    freshness: Mapping[str, Any] | None = None,
    reasons: Sequence[str] | None = None,
) -> dict[str, Any]:
    payload = {
        "status": _UNAVAILABLE,
        "source": source or _UNAVAILABLE,
        "timestamp": timestamp or _UNAVAILABLE,
        "section_kind": SECTION_KIND,
        "section_label": SECTION_LABEL,
        "market_value_availability": _UNAVAILABLE,
        "rows": [],
        "reason": reason,
        "freshness": dict(freshness) if isinstance(freshness, Mapping) else {},
    }
    if reasons:
        payload["reasons"] = list(reasons)
    return payload


def build_spot_asset_balances(
    *,
    selected_broker: Any,
    canonical_mode: Any,
    coinbase_validation: Mapping[str, Any] | None,
    now: Any = None,
    policy: Mapping[str, Any] | None = None,
    policy_path: Any = None,
    decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize Coinbase account-balance rows. Never labels them as positions."""
    gate = (
        dict(decision)
        if isinstance(decision, Mapping)
        else coinbase_balance_only_promotion_allowed(
            selected_broker=selected_broker,
            canonical_mode=canonical_mode,
            coinbase_validation=coinbase_validation,
            now=now,
            policy=policy,
            policy_path=policy_path,
        )
    )
    snapshot = _mapping(gate.get("snapshot"))
    timestamp = _first_present_timestamp(snapshot, coinbase_validation)
    if not gate.get("allowed"):
        reasons = [str(item) for item in gate.get("reasons") or [] if str(item)]
        return unavailable_spot_asset_balances(
            reason=reasons[0] if reasons else "promotion_not_allowed",
            reasons=reasons,
            source=_UNAVAILABLE,
            timestamp=timestamp,
            freshness=_mapping(gate.get("freshness")),
        )

    rows = extract_spot_asset_balance_rows(
        coinbase_validation,
        snapshot=snapshot,
        source=SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY,
    )
    if not rows:
        return unavailable_spot_asset_balances(
            reason="no_trustworthy_balance_rows",
            source=SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY,
            timestamp=timestamp,
            freshness=_mapping(gate.get("freshness")),
        )
    return {
        "status": _AVAILABLE,
        "source": SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY,
        "timestamp": timestamp,
        "section_kind": SECTION_KIND,
        "section_label": SECTION_LABEL,
        "market_value_availability": _UNAVAILABLE,
        "rows": rows,
        "reason": "ok",
        "freshness": dict(_mapping(gate.get("freshness"))),
    }


def extract_spot_asset_balance_rows(
    coinbase_validation: Mapping[str, Any] | None,
    *,
    snapshot: Mapping[str, Any] | None = None,
    source: str,
) -> list[dict[str, Any]]:
    validation = coinbase_validation if isinstance(coinbase_validation, Mapping) else {}
    broker_validation = _mapping(validation.get("broker_validation"))
    snap = _mapping(snapshot) or _canonical_account_snapshot(validation)
    candidates = _candidate_raw_rows(validation, broker_validation, snap)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for raw in candidates:
        normalized = _normalize_balance_row(raw, source=source)
        if normalized is None:
            continue
        identity = (
            normalized.get("asset"),
            normalized.get("available_quantity"),
            normalized.get("held_quantity"),
            normalized.get("total_quantity"),
            normalized.get("account_id"),
        )
        if identity in seen:
            continue
        seen.add(identity)
        rows.append(normalized)
    return rows


def attach_spot_asset_balances(
    payload: Mapping[str, Any] | None,
    *,
    decision: Mapping[str, Any],
    coinbase_validation: Mapping[str, Any] | None,
    selected_broker: Any = None,
    canonical_mode: Any = None,
) -> dict[str, Any]:
    out = dict(payload) if isinstance(payload, Mapping) else {}
    out["spot_asset_balances"] = build_spot_asset_balances(
        selected_broker=selected_broker if selected_broker is not None else decision.get("selected_broker"),
        canonical_mode=canonical_mode if canonical_mode is not None else decision.get("canonical_mode"),
        coinbase_validation=coinbase_validation,
        decision=decision,
    )
    return out


def _candidate_raw_rows(
    validation: Mapping[str, Any],
    broker_validation: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    lists: list[Any] = []
    for container in (validation, broker_validation, snapshot):
        if not isinstance(container, Mapping):
            continue
        for key in (
            "account_asset_balances",
            "accounts",
            "balances",
            "assets",
            "currencies",
        ):
            value = container.get(key)
            if isinstance(value, list) and value:
                lists.append(value)
    rows: list[Mapping[str, Any]] = []
    for group in lists:
        for item in group:
            if isinstance(item, Mapping) and item:
                rows.append(item)
    if rows:
        return rows
    fallback = _snapshot_fallback_row(snapshot)
    return [fallback] if fallback else []


def _snapshot_fallback_row(snapshot: Mapping[str, Any]) -> dict[str, Any] | None:
    if not isinstance(snapshot, Mapping) or not snapshot:
        return None
    asset = snapshot.get("currency")
    available = None
    for key in ("available_balance", "cash", "balance"):
        if key in snapshot and _is_number(snapshot.get(key)):
            available = snapshot.get(key)
            break
    if asset in (None, "") or available is None:
        return None
    row: dict[str, Any] = {
        "currency": asset,
        "available_balance": available,
        "row_source": "canonical_account_snapshot",
    }
    account_id = snapshot.get("account_id")
    if _safe_account_id(account_id) is not None:
        row["account_id"] = account_id
    return row


def _normalize_balance_row(raw: Mapping[str, Any], *, source: str) -> dict[str, Any] | None:
    asset = raw.get("asset") or raw.get("currency") or raw.get("symbol")
    if asset in (None, ""):
        return None
    asset_text = str(asset).strip().upper()
    if not asset_text or asset_text in {"UNAVAILABLE", "UNKNOWN", "NONE"}:
        return None

    available = _independent_number(
        raw,
        ("available_balance", "available", "available_quantity", "cash"),
    )
    held = None
    held_independent = False
    if not _is_fabricated_fallback_hold(raw):
        held = _independent_number(
            raw,
            ("held_balance", "held_quantity", "held", "hold", "locked", "reserved"),
        )
        held_independent = held is not None

    total = None
    total_provenance = _UNAVAILABLE
    independent_total = _independent_number(
        raw,
        ("total_balance", "total_quantity", "total"),
    )
    if available is not None and held_independent:
        derived = float(available) + float(held)
        total = derived
        total_provenance = "derived_available_plus_held"
        if independent_total is not None and float(independent_total) == derived:
            total = float(independent_total)
    elif independent_total is not None and available is None and not held_independent:
        total = independent_total
        total_provenance = "broker_reported"
    elif independent_total is not None and available is not None and not held_independent:
        # Adapter derives total = available + hold. Without an independently
        # present hold, do not treat a lone total as a second quantity.
        total = None
        total_provenance = _UNAVAILABLE

    if available is None and not held_independent and total is None:
        return None

    account_id = _safe_account_id(raw.get("account_id") or raw.get("uuid") or raw.get("id"))
    row: dict[str, Any] = {
        "asset": asset_text,
        "available_quantity": available,
        "available_quantity_availability": _AVAILABLE if available is not None else _UNAVAILABLE,
        "held_quantity": held if held_independent else None,
        "held_quantity_availability": _AVAILABLE if held_independent else _UNAVAILABLE,
        "total_quantity": total,
        "total_quantity_availability": _AVAILABLE if total is not None else _UNAVAILABLE,
        "total_quantity_provenance": total_provenance,
        "market_value": None,
        "market_value_availability": _UNAVAILABLE,
        "availability": _AVAILABLE,
        "provenance": source,
    }
    if account_id is not None:
        row["account_id"] = account_id
    return row


def _independent_number(raw: Mapping[str, Any], keys: Sequence[str]) -> float | None:
    for key in keys:
        if key not in raw:
            continue
        value = raw.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, Mapping):
            nested = value.get("value")
            if nested is None:
                nested = value.get("amount")
            value = nested
        if _is_number(value):
            return float(value)
    return None


def _is_fabricated_fallback_hold(raw: Mapping[str, Any]) -> bool:
    account_id = str(raw.get("account_id") or "").strip().upper()
    return account_id == "FALLBACK-COINBASE" and "held_balance" in raw


def _safe_account_id(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.upper() in SYNTHETIC_ACCOUNT_IDS:
        return None
    lowered = text.lower()
    if any(token in lowered for token in _SECRET_ACCOUNT_ID_TOKENS):
        return None
    return text


def _first_present_timestamp(
    snapshot: Mapping[str, Any],
    coinbase_validation: Mapping[str, Any] | None,
) -> str:
    raw = _first_timestamp(snapshot) if snapshot else None
    if raw not in (None, ""):
        return str(raw)
    validation = coinbase_validation if isinstance(coinbase_validation, Mapping) else {}
    broker_validation = _mapping(validation.get("broker_validation"))
    for candidate in (
        broker_validation.get("validation_timestamp"),
        validation.get("validation_timestamp"),
        broker_validation.get("last_successful_sync"),
        validation.get("last_successful_sync"),
    ):
        if candidate not in (None, ""):
            return str(candidate)
    return _UNAVAILABLE


def assert_not_position_label(label: str) -> None:
    token = str(label or "").strip().lower()
    if token in _FORBIDDEN_POSITION_LABELS:
        raise ValueError(f"asset balances must not be labeled as {label}")


__all__ = [
    "SECTION_KIND",
    "SECTION_LABEL",
    "attach_spot_asset_balances",
    "build_spot_asset_balances",
    "extract_spot_asset_balance_rows",
    "unavailable_spot_asset_balances",
]

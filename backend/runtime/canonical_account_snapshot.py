from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping


SCHEMA_VERSION = "css.phase166e.canonical_account_snapshot.v1"
PROVENANCE_VALUES = frozenset({"LIVE", "CACHE", "HISTORICAL", "SIMULATION", "UNAVAILABLE", "UNKNOWN"})
NUMERIC_PROVENANCE_FIELDS = (
    "cash",
    "equity",
    "balance",
    "buying_power",
    "available_balance",
    "margin_available",
    "margin_required",
    "free_margin",
)


@dataclass(frozen=True)
class CanonicalAccountSnapshot:
    broker: str = "NONE"
    mode: str = "paper"
    authenticated: bool = False
    connected: bool = False
    account_loaded: bool = False
    portfolio_loaded: bool = False
    balances_loaded: bool = False
    equity_loaded: bool = False
    buying_power_loaded: bool = False
    margin_loaded: bool = False
    market_data_loaded: bool = False
    currency: str = "UNKNOWN"
    timestamp: str = ""
    provenance: Mapping[str, str] = field(default_factory=dict)
    failure_reason: str = "UNAVAILABLE"
    state_hash: str = ""
    account_id: str = ""
    portfolio_id: str = ""
    account_count: int = 0
    portfolio_count: int = 0
    balance_timestamp: str = ""
    equity: float | None = None
    cash: float | None = None
    balance: float | None = None
    buying_power: float | None = None
    available_balance: float | None = None
    margin_available: float | None = None
    margin_required: float | None = None
    free_margin: float | None = None
    contradiction_reasons: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "broker", str(self.broker or "NONE").upper())
        object.__setattr__(self, "mode", str(self.mode or "paper").lower())
        object.__setattr__(self, "currency", str(self.currency or "UNKNOWN").upper())
        object.__setattr__(self, "timestamp", str(self.timestamp or _utc_iso()))
        object.__setattr__(self, "account_count", max(int(self.account_count or 0), 0))
        object.__setattr__(self, "portfolio_count", max(int(self.portfolio_count or 0), 0))

        provenance = _normalized_provenance(self.provenance)
        for key in NUMERIC_PROVENANCE_FIELDS:
            provenance.setdefault(key, "LIVE" if self.mode == "live" and self.balances_loaded else "UNAVAILABLE")

        contradictions = list(self.contradiction_reasons)
        numeric_fields = {
            "equity": self.equity,
            "cash": self.cash,
            "balance": self.balance,
            "buying_power": self.buying_power,
            "available_balance": self.available_balance,
            "margin_available": self.margin_available,
            "margin_required": self.margin_required,
            "free_margin": self.free_margin,
        }

        if not self.balances_loaded:
            object.__setattr__(self, "equity_loaded", False)
            object.__setattr__(self, "buying_power_loaded", False)
            object.__setattr__(self, "margin_loaded", False)
            for name in numeric_fields:
                object.__setattr__(self, name, None)
                provenance[name] = "UNAVAILABLE"
        else:
            object.__setattr__(self, "equity_loaded", bool(self.equity_loaded and self.account_loaded))
            object.__setattr__(self, "buying_power_loaded", bool(self.buying_power_loaded))
            object.__setattr__(self, "margin_loaded", bool(self.margin_loaded))

        if self.equity_loaded and not self.account_loaded:
            contradictions.append("equity_loaded_without_account")
        if self.buying_power_loaded and not self.balances_loaded:
            contradictions.append("buying_power_loaded_without_balances")
        if self.margin_loaded and not self.balances_loaded:
            contradictions.append("margin_loaded_without_balances")
        if self.mode == "live" and not self.balances_loaded:
            for name, value in numeric_fields.items():
                if _positive(value) and provenance.get(name) == "LIVE":
                    contradictions.append(f"live_{name}_with_unavailable_balances")

        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "contradiction_reasons", tuple(dict.fromkeys(str(item) for item in contradictions if str(item))))
        if self.contradiction_reasons and self.failure_reason in {"", "NONE", "NO_FAILURE", "UNAVAILABLE"}:
            object.__setattr__(self, "failure_reason", self.contradiction_reasons[0])
        elif not self.failure_reason:
            object.__setattr__(self, "failure_reason", "NO_FAILURE" if self.balances_loaded else "BALANCE_UNAVAILABLE")
        object.__setattr__(self, "state_hash", self.stable_hash())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["provenance"] = dict(self.provenance)
        payload["contradiction_reasons"] = list(self.contradiction_reasons)
        payload["state_hash"] = self.state_hash
        return _json_safe(payload)

    def stable_json(self) -> str:
        payload = asdict(self)
        payload.pop("state_hash", None)
        payload["provenance"] = dict(self.provenance)
        return json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), default=str)

    def stable_hash(self) -> str:
        return hashlib.sha256(self.stable_json().encode("utf-8")).hexdigest()


def build_canonical_account_snapshot(
    *,
    broker: str = "NONE",
    mode: str = "paper",
    runtime_payload: Mapping[str, Any] | None = None,
    adapter_status: Mapping[str, Any] | None = None,
    certification: Mapping[str, Any] | None = None,
    margin_snapshot: Mapping[str, Any] | None = None,
    timestamp: str | None = None,
) -> CanonicalAccountSnapshot:
    runtime = _mapping(runtime_payload)
    adapter = _mapping(adapter_status)
    cert = _mapping(certification)
    margin = _mapping(margin_snapshot)

    existing = _first_mapping(
        runtime.get("canonical_account_snapshot"),
        runtime.get("account_snapshot"),
        adapter.get("canonical_account_snapshot"),
        adapter.get("account_snapshot"),
        cert.get("canonical_account_snapshot"),
        cert.get("account_snapshot"),
    )
    if existing:
        return CanonicalAccountSnapshot(**_snapshot_kwargs(existing, broker=broker, mode=mode, timestamp=timestamp))

    broker_name = str(broker or runtime.get("broker") or runtime.get("selected_broker") or adapter.get("broker") or cert.get("broker") or "NONE").upper()
    mode_key = str(mode or runtime.get("broker_mode") or runtime.get("mode") or adapter.get("broker_mode") or cert.get("mode") or "paper").lower()
    account_loaded = _status_bool(runtime.get("account_status"), runtime.get("account_loaded"), adapter.get("account_loaded"), cert.get("account_loaded"))
    balances_loaded = _status_bool(runtime.get("balance_status"), runtime.get("balances_loaded"), adapter.get("balances_loaded"), cert.get("balances_loaded"))
    authenticated = _status_bool(runtime.get("authentication_status"), runtime.get("broker_authenticated"), runtime.get("authenticated"), adapter.get("broker_authenticated"), cert.get("authenticated"))
    connected = _status_bool(runtime.get("connection_status"), runtime.get("broker_connected"), runtime.get("connected"), adapter.get("broker_connected"), cert.get("api_reachable"))
    portfolio_loaded = _status_bool(runtime.get("portfolio_status"), runtime.get("portfolio_loaded"), adapter.get("portfolio_loaded"), cert.get("portfolio_loaded"))
    market_data_loaded = _status_bool(runtime.get("market_data_status"), runtime.get("market_data_loaded"), adapter.get("market_data_loaded"), cert.get("market_data_loaded"))

    equity = _first_float(runtime, adapter, cert, margin, keys=("account_equity", "equity", "portfolio_value", "balance"))
    cash = _first_float(runtime, adapter, cert, margin, keys=("cash", "available_balance", "account_balance", "balance"))
    balance = _first_float(runtime, adapter, cert, margin, keys=("balance", "account_balance", "cash", "available_balance"))
    buying_power = _first_float(runtime, adapter, cert, margin, keys=("buying_power", "available_balance", "margin_available", "free_margin"))
    available_balance = _first_float(runtime, adapter, cert, margin, keys=("available_balance", "cash", "balance"))
    margin_available = _first_float(margin, runtime, adapter, cert, keys=("margin_available", "available_margin", "free_margin", "buying_power"))
    margin_required = _first_float(margin, runtime, adapter, cert, keys=("required_margin", "margin_required", "margin_used", "initial_margin"))
    free_margin = _first_float(margin, runtime, adapter, cert, keys=("free_margin", "buying_power", "margin_available"))

    if balance is None:
        balance = cash
    if cash is None:
        cash = balance
    if equity is None:
        equity = balance
    if available_balance is None:
        available_balance = cash
    if buying_power is None:
        buying_power = available_balance
    if margin_available is None:
        margin_available = buying_power
    if free_margin is None:
        free_margin = margin_available
    if margin_required is None and balances_loaded:
        margin_required = 0.0

    provenance = _normalized_provenance(runtime.get("account_value_provenance") or runtime.get("provenance") or {})
    status_provenance = _mapping(runtime.get("status_provenance") or adapter.get("status_provenance") or cert.get("status_provenance"))
    provenance.setdefault("cash", status_provenance.get("balances", _source_for(mode_key, balances_loaded)))
    provenance.setdefault("balance", status_provenance.get("balances", _source_for(mode_key, balances_loaded)))
    provenance.setdefault("available_balance", status_provenance.get("balances", _source_for(mode_key, balances_loaded)))
    provenance.setdefault("equity", status_provenance.get("balances", _source_for(mode_key, balances_loaded)))
    provenance.setdefault("buying_power", status_provenance.get("buying_power", _source_for(mode_key, balances_loaded and buying_power is not None)))
    provenance.setdefault("margin_available", status_provenance.get("margin", _source_for(mode_key, balances_loaded and margin_available is not None)))
    provenance.setdefault("margin_required", status_provenance.get("margin", _source_for(mode_key, balances_loaded and margin_required is not None)))
    provenance.setdefault("free_margin", status_provenance.get("margin", _source_for(mode_key, balances_loaded and free_margin is not None)))

    account_id = _first_text(runtime, adapter, cert, margin, keys=("account_id", "selected_account_id"))
    portfolio_id = _first_text(runtime, adapter, cert, keys=("portfolio_id", "selected_portfolio_id"))
    contradictions = _identity_contradictions(runtime, adapter, cert, margin)
    failure_reason = str(runtime.get("failure_reason") or adapter.get("failure_reason") or cert.get("failure_reason") or "")

    return CanonicalAccountSnapshot(
        broker=broker_name,
        mode=mode_key,
        authenticated=authenticated,
        connected=connected,
        account_loaded=account_loaded,
        portfolio_loaded=portfolio_loaded,
        balances_loaded=balances_loaded,
        equity_loaded=balances_loaded and account_loaded and equity is not None,
        buying_power_loaded=balances_loaded and buying_power is not None,
        margin_loaded=balances_loaded and margin_available is not None,
        market_data_loaded=market_data_loaded,
        currency=_first_text(runtime, adapter, cert, margin, keys=("currency", "account_currency")) or "UNKNOWN",
        timestamp=timestamp or _first_text(runtime, adapter, cert, keys=("timestamp", "generated_at", "validation_timestamp")) or _utc_iso(),
        provenance=provenance,
        failure_reason=failure_reason or ("NO_FAILURE" if balances_loaded else "BALANCE_UNAVAILABLE"),
        account_id=account_id,
        portfolio_id=portfolio_id,
        account_count=int(_first_float(runtime, adapter, cert, keys=("account_count", "accounts_loaded")) or (1 if account_loaded else 0)),
        portfolio_count=int(_first_float(runtime, adapter, cert, keys=("portfolio_count", "portfolios_loaded")) or (1 if portfolio_loaded else 0)),
        balance_timestamp=_first_text(runtime, adapter, cert, margin, keys=("balance_timestamp", "last_successful_balance_read", "last_successful_sync")),
        equity=equity,
        cash=cash,
        balance=balance,
        buying_power=buying_power,
        available_balance=available_balance,
        margin_available=margin_available,
        margin_required=margin_required,
        free_margin=free_margin,
        contradiction_reasons=tuple(contradictions),
    )


def validate_account_snapshot_consumer_hash(snapshot: Mapping[str, Any] | CanonicalAccountSnapshot, consumer_hash: str) -> bool:
    canonical = snapshot if isinstance(snapshot, CanonicalAccountSnapshot) else CanonicalAccountSnapshot(**_snapshot_kwargs(snapshot))
    return bool(consumer_hash) and str(consumer_hash) == canonical.state_hash


def _snapshot_kwargs(payload: Mapping[str, Any], *, broker: str = "NONE", mode: str = "paper", timestamp: str | None = None) -> dict[str, Any]:
    allowed = set(CanonicalAccountSnapshot.__dataclass_fields__.keys())
    data = {key: value for key, value in dict(payload).items() if key in allowed}
    data.setdefault("broker", broker or payload.get("broker", "NONE"))
    data.setdefault("mode", mode or payload.get("mode", "paper"))
    if timestamp:
        data["timestamp"] = timestamp
    return data


def _identity_contradictions(*payloads: Mapping[str, Any]) -> list[str]:
    account_ids = {str(payload.get("account_id") or payload.get("selected_account_id") or "").strip() for payload in payloads if str(payload.get("account_id") or payload.get("selected_account_id") or "").strip()}
    portfolio_ids = {str(payload.get("portfolio_id") or payload.get("selected_portfolio_id") or "").strip() for payload in payloads if str(payload.get("portfolio_id") or payload.get("selected_portfolio_id") or "").strip()}
    balance_times = {str(payload.get("balance_timestamp") or "").strip() for payload in payloads if str(payload.get("balance_timestamp") or "").strip()}
    reasons: list[str] = []
    if len(account_ids) > 1:
        reasons.append("account_identity_mismatch")
    if len(portfolio_ids) > 1:
        reasons.append("portfolio_identity_mismatch")
    if len(balance_times) > 1:
        reasons.append("balance_timestamp_mismatch")
    return reasons


def _normalized_provenance(value: Any) -> dict[str, str]:
    source = _mapping(value)
    provenance: dict[str, str] = {}
    for key, raw in source.items():
        text = str(raw or "").strip().upper()
        provenance[str(key)] = text if text in PROVENANCE_VALUES else "UNKNOWN"
    return provenance


def _source_for(mode: str, loaded: bool) -> str:
    if not loaded:
        return "UNAVAILABLE"
    return "LIVE" if str(mode).lower() == "live" else "SIMULATION"


def _status_bool(*values: Any) -> bool:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value > 0
        text = str(value).strip().upper()
        if text in {"PASS", "PRESENT", "READY", "OK", "AVAILABLE", "AUTHENTICATED", "CONNECTED", "GREEN", "OPERATIONAL"}:
            return True
        if text in {"FAIL", "FAILED", "ERROR", "RED", "UNAVAILABLE", "NOT_AVAILABLE", "MISSING", "FALSE"}:
            return False
    return False


def _first_float(*payloads: Mapping[str, Any], keys: tuple[str, ...]) -> float | None:
    for payload in payloads:
        for key in keys:
            value = payload.get(key)
            parsed = _float_or_none(value)
            if parsed is not None:
                return parsed
    return None


def _first_text(*payloads: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for payload in payloads:
        for key in keys:
            value = payload.get(key)
            if value not in (None, ""):
                return str(value)
    return ""


def _float_or_none(value: Any) -> float | None:
    if value in (None, "", "DATA UNAVAILABLE", "UNAVAILABLE", "NOT_APPLICABLE"):
        return None
    if isinstance(value, Mapping):
        for key in ("value", "amount", "balance", "available"):
            if key in value:
                return _float_or_none(value.get(key))
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def _positive(value: Any) -> bool:
    parsed = _float_or_none(value)
    return parsed is not None and parsed > 0


def _first_mapping(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, Mapping) and value:
            return dict(value)
    return {}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "CanonicalAccountSnapshot",
    "NUMERIC_PROVENANCE_FIELDS",
    "PROVENANCE_VALUES",
    "SCHEMA_VERSION",
    "build_canonical_account_snapshot",
    "validate_account_snapshot_consumer_hash",
]

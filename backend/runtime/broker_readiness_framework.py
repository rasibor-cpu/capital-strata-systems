from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


CANONICAL_BROKER_READINESS_FIELDS = (
    "broker_name",
    "broker_type",
    "mode",
    "credentials_present",
    "authenticated",
    "connected",
    "account_loaded",
    "market_data_ready",
    "products_loaded",
    "broker_health",
    "infrastructure_health",
    "credentials_health",
    "authentication_health",
    "connection_health",
    "market_data_health",
    "account_data_health",
    "execution_supported",
    "execution_enabled",
    "last_successful_sync",
    "account_balance",
    "equity",
    "buying_power",
    "authority_block_reason",
    "readiness_score",
)

BROKER_PARITY_COMPARABLE_FIELDS = tuple(
    field
    for field in CANONICAL_BROKER_READINESS_FIELDS
    if field
    not in {
        "broker_name",
        "broker_type",
        "last_successful_sync",
        "account_balance",
        "equity",
        "buying_power",
    }
)


@dataclass(frozen=True)
class BrokerReadinessSnapshot:
    broker_name: str
    broker_type: str = "UNKNOWN"
    mode: str = "paper"
    credentials_present: bool = False
    authenticated: bool = False
    connected: bool = False
    account_loaded: bool = False
    market_data_ready: bool = False
    products_loaded: int = 0
    broker_health: str = "UNKNOWN"
    infrastructure_health: str = "UNKNOWN"
    credentials_health: str = "UNKNOWN"
    authentication_health: str = "UNKNOWN"
    connection_health: str = "UNKNOWN"
    market_data_health: str = "UNKNOWN"
    account_data_health: str = "UNKNOWN"
    execution_supported: bool = False
    execution_enabled: bool = False
    last_successful_sync: str = ""
    account_balance: float | None = None
    equity: float | None = None
    buying_power: float | None = None
    authority_block_reason: str = "Credentials Missing"
    readiness_score: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_broker_readiness_snapshot(
    payload: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> BrokerReadinessSnapshot:
    data: dict[str, Any] = {}
    if isinstance(payload, Mapping):
        data.update(dict(payload))
    data.update(overrides)

    diagnostics = data.get("credential_diagnostics") if isinstance(data.get("credential_diagnostics"), Mapping) else {}
    credentials_present = _truthy(data.get("credentials_present")) or str(
        data.get("credential_status")
        or data.get("credentials")
        or diagnostics.get("credential_status")
        or ""
    ).upper() in {"PRESENT", "PASS", "READY"}
    authenticated = _truthy(data.get("authenticated", data.get("broker_authenticated", False)))
    connected = _truthy(data.get("connected", data.get("broker_connected", False)))
    account_loaded = (
        _truthy(data.get("account_loaded", False))
        or _value_present(data.get("account_equity"))
        or _value_present(data.get("equity"))
        or _value_present(data.get("account_balance"))
        or _value_present(data.get("cash"))
        or _value_present(data.get("available_balance"))
    )
    products_loaded = _int(data.get("products_loaded", 0))
    market_status = str(data.get("market_data_status", data.get("product_price_status", ""))).upper()
    market_data_ready = _truthy(data.get("market_data_ready", False)) or (
        products_loaded > 0 and market_status in {"READY", "OK", "PASS", "AVAILABLE"}
    )
    execution_enabled = _truthy(data.get("execution_authority", data.get("execution_enabled", data.get("broker_execution_enabled", False))))
    readiness_score = _score(
        credentials_present,
        authenticated,
        connected,
        account_loaded,
        market_data_ready,
        not execution_enabled,
    )
    return BrokerReadinessSnapshot(
        broker_name=str(data.get("broker_name", data.get("selected_broker", data.get("broker", "NONE"))) or "NONE").upper(),
        broker_type=str(data.get("broker_type", "EXTERNAL") or "EXTERNAL").upper(),
        mode=str(data.get("mode", data.get("broker_mode", "paper")) or "paper").lower(),
        credentials_present=credentials_present,
        authenticated=authenticated,
        connected=connected,
        account_loaded=account_loaded,
        market_data_ready=market_data_ready,
        products_loaded=products_loaded,
        broker_health=str(data.get("broker_health", data.get("broker_infrastructure_health", "UNKNOWN")) or "UNKNOWN"),
        infrastructure_health=str(data.get("infrastructure_health", data.get("broker_infrastructure_health", "UNKNOWN")) or "UNKNOWN"),
        credentials_health=str(data.get("credentials_health", "UNKNOWN") or "UNKNOWN"),
        authentication_health=str(data.get("authentication_health", "UNKNOWN") or "UNKNOWN"),
        connection_health=str(data.get("connection_health", "UNKNOWN") or "UNKNOWN"),
        market_data_health=str(data.get("market_data_health", "UNKNOWN") or "UNKNOWN"),
        account_data_health=str(data.get("account_data_health", "UNKNOWN") or "UNKNOWN"),
        execution_supported=_truthy(data.get("execution_supported", False)),
        execution_enabled=execution_enabled,
        last_successful_sync=str(data.get("last_successful_sync", data.get("last_broker_sync", "")) or ""),
        account_balance=_float_or_none(data.get("account_balance", data.get("cash"))),
        equity=_float_or_none(data.get("equity", data.get("account_equity"))),
        buying_power=_float_or_none(data.get("buying_power", data.get("available_balance"))),
        authority_block_reason=str(data.get("authority_block_reason", data.get("authority_reason", _first_block_reason(credentials_present, authenticated, connected, account_loaded, market_data_ready))) or ""),
        readiness_score=float(data.get("readiness_score", readiness_score) or readiness_score),
    )


def broker_readiness_payload(snapshot: BrokerReadinessSnapshot | Mapping[str, Any] | None) -> dict[str, Any]:
    if isinstance(snapshot, BrokerReadinessSnapshot):
        payload = snapshot.as_dict()
    else:
        payload = build_broker_readiness_snapshot(snapshot).as_dict()
    payload["broker_ready"] = bool(
        payload["credentials_present"]
        and payload["authenticated"]
        and payload["connected"]
        and payload["account_loaded"]
        and payload["market_data_ready"]
    )
    payload["advisory_only"] = True
    payload["execution_allowed"] = False
    return payload


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _score(*checks: bool) -> float:
    if not checks:
        return 0.0
    return round(sum(1 for check in checks if check) / len(checks) * 100.0, 2)


def _first_block_reason(
    credentials_present: bool,
    authenticated: bool,
    connected: bool,
    account_loaded: bool,
    market_data_ready: bool,
) -> str:
    if not credentials_present:
        return "Credentials Missing"
    if not authenticated:
        return "Authentication Not Verified"
    if not connected:
        return "Broker Connection Not Verified"
    if not account_loaded:
        return "Account Data Missing"
    if not market_data_ready:
        return "Market Data Not Ready"
    return "Broker Execution Disabled"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "enabled", "armed", "connected", "authenticated", "pass", "ok", "green", "healthy", "ready", "clear"}


def _value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().upper() not in {"", "DATA UNAVAILABLE", "NONE", "NULL", "NOT_TESTED"}
    return True


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "BROKER_PARITY_COMPARABLE_FIELDS",
    "CANONICAL_BROKER_READINESS_FIELDS",
    "BrokerReadinessSnapshot",
    "broker_readiness_payload",
    "build_broker_readiness_snapshot",
    "utc_now_iso",
]

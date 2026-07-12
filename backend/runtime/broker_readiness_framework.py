from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from abc import ABC, abstractmethod

from backend.common.advisory_payload import AdvisoryPayloadBuilder
from backend.runtime.broker_operational_status import build_broker_operational_status
from backend.runtime.broker_credential_diagnostics import (
    authority_reason_from_diagnostics,
    diagnostics_payload,
)


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
    canonical_diagnostics = data.get("broker_credential_diagnostics")
    if not isinstance(canonical_diagnostics, Mapping):
        canonical_diagnostics = diagnostics.get("broker_credential_diagnostics") if isinstance(diagnostics.get("broker_credential_diagnostics"), Mapping) else diagnostics
    credential_payload = diagnostics_payload(canonical_diagnostics)
    credentials_present = _truthy(data.get("credentials_present")) or str(
        data.get("credential_status")
        or data.get("credentials")
        or credential_payload.get("credential_status")
        or diagnostics.get("credential_status")
        or ""
    ).upper() in {"PRESENT", "PASS", "READY"} or _truthy(credential_payload.get("credentials_present"))
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
        credentials_health=str(
            data.get(
                "credentials_health",
                "READY" if credential_payload.get("credentials_present") else "MISSING",
            )
            or "UNKNOWN"
        ),
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
        authority_block_reason=str(
            data.get(
                "authority_block_reason",
                data.get(
                    "authority_reason",
                    _first_block_reason(
                        credentials_present,
                        authenticated,
                        connected,
                        account_loaded,
                        market_data_ready,
                        credential_payload,
                    ),
                ),
            )
            or ""
        ),
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
    return AdvisoryPayloadBuilder.lock(payload)


def broker_readiness_with_operational_status(
    snapshot: BrokerReadinessSnapshot | Mapping[str, Any] | None,
    operational_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = broker_readiness_payload(snapshot)
    payload["broker_operational_status"] = build_broker_operational_status(
        {
            "broker": payload.get("broker_name", "UNKNOWN"),
            "broker_type": payload.get("broker_type", "UNKNOWN"),
            "mode": payload.get("mode", "paper"),
            "last_successful_sync": payload.get("last_successful_sync", "NOT_AVAILABLE"),
            "account_sync_status": "OK" if payload.get("account_loaded") else "PENDING",
            "product_count": payload.get("products_loaded", 0),
            "market_data_status": "OK" if payload.get("market_data_ready") else "PENDING",
            "balance_status": "AVAILABLE" if payload.get("account_balance") is not None else "NOT_AVAILABLE",
            "margin_status": "BROKER_UNAVAILABLE" if payload.get("account_loaded") else "READ_ONLY_PENDING_ACCOUNT",
        }
        | dict(operational_payload or {})
    )
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
    credential_payload: Mapping[str, Any] | None = None,
) -> str:
    if not credentials_present:
        return authority_reason_from_diagnostics(credential_payload or {})
    diagnostic_reason = authority_reason_from_diagnostics(credential_payload or {})
    if not authenticated and diagnostic_reason not in {"Broker Execution Disabled", "Credentials Missing"}:
        return diagnostic_reason
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



class BrokerReadOnlyInterface(ABC):
    """
    Canonical interface that all read-only broker adapters must implement.
    Allows validation and readiness frameworks to interact with any broker
    polymorphically.
    """

    @abstractmethod
    def authenticate(self) -> dict[str, Any]:
        """Authenticate with the broker. Returns status dict."""
        pass

    @abstractmethod
    def account_summary(self) -> dict[str, Any]:
        """Fetch general account summary (NAV, balance, buying power)."""
        pass

    @abstractmethod
    def market_data(self, symbol: str | None = None) -> dict[str, Any]:
        """Fetch market data/pricing evidence for the given or default symbol."""
        pass

    @abstractmethod
    def positions(self) -> list[dict[str, Any]]:
        """Fetch open positions."""
        pass

    @abstractmethod
    def server_time(self) -> dict[str, Any]:
        """Fetch server time or status."""
        pass

    @abstractmethod
    def health(self) -> str:
        """Get the current health status of the broker adapter (GREEN/AMBER/RED/UNKNOWN)."""
        pass

    @abstractmethod
    def latency(self) -> dict[str, Any]:
        """Get recent sync latency figures for different stages."""
        pass


__all__ = [
    "BROKER_PARITY_COMPARABLE_FIELDS",
    "CANONICAL_BROKER_READINESS_FIELDS",
    "BrokerReadinessSnapshot",
    "broker_readiness_payload",
    "broker_readiness_with_operational_status",
    "build_broker_readiness_snapshot",
    "utc_now_iso",
    "BrokerReadOnlyInterface",
]

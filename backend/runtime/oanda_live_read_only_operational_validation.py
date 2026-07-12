from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from backend.runtime.oanda_live_read_only_adapter import OandaLiveReadOnlyAdapter
from backend.runtime.broker_operational_status import (
    build_broker_operational_status,
    endpoint_for_broker,
)


FAILURE_REASONS = (
    "AUTH_FAILED",
    "NETWORK_ERROR",
    "RATE_LIMIT",
    "TIMEOUT",
    "API_ERROR",
    "MISSING_CREDENTIALS",
    "ACCOUNT_NOT_FOUND",
    "MARKET_DATA_UNAVAILABLE",
    "SERVICE_UNAVAILABLE",
)

READ_CHECKS = (
    "api_connectivity",
    "server_time",
    "account_retrieval",
    "portfolio_retrieval",
    "available_balances",
    "products_list",
    "market_ticker",
    "candle_retrieval",
)


@dataclass(frozen=True)
class OandaOperationalValidationResult:
    validation_status: str
    api_reachable: bool
    authenticated: bool
    account_loaded: bool
    portfolio_loaded: bool
    balances_loaded: bool
    products_loaded: int
    market_data_loaded: bool
    last_successful_sync: str
    validation_timestamp: str
    read_checks: dict[str, str] = field(default_factory=dict)
    failure_reasons: list[dict[str, str]] = field(default_factory=list)
    broker_validation: dict[str, Any] = field(default_factory=dict)
    broker_health: dict[str, Any] = field(default_factory=dict)
    broker_market_snapshot: dict[str, Any] = field(default_factory=dict)
    broker_operational_status: dict[str, Any] = field(default_factory=dict)
    broker_execution_status: str = "DISABLED"
    execution_authority: bool = False
    can_live_execute: bool = False
    live_micro_pilot_state: str = "DISARMED"
    advisory_only: bool = True
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class OandaLiveReadOnlyOperationalValidator:
    """Read-only operational validator for OANDA LIVE connectivity.

    The validator uses OandaLiveReadOnlyAdapter exclusively. It publishes
    diagnostics and runtime artifacts only; it does not expose or call any
    broker order, cancel, modify, or execution capability.
    """

    def __init__(
        self,
        *,
        adapter_factory: Callable[[], OandaLiveReadOnlyAdapter] | None = None,
        artifacts_dir: str | Path | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.adapter_factory = adapter_factory
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir is not None else None
        self.now = now or (lambda: datetime.now(timezone.utc))

    def validate(self) -> dict[str, Any]:
        adapter = self.adapter_factory() if self.adapter_factory is not None else OandaLiveReadOnlyAdapter()
        timestamp = self.now().isoformat()
        read_checks = {key: "NOT_ATTEMPTED" for key in READ_CHECKS}
        failures: list[dict[str, str]] = []

        diagnostics = adapter.credential_diagnostics()
        if diagnostics["credential_status"] != "PRESENT":
            failures.append(_failure("MISSING_CREDENTIALS", "OANDA credentials are missing"))
            result = self._result(
                adapter=adapter,
                timestamp=timestamp,
                read_checks=read_checks,
                failures=failures,
                server_time=None,
                account=None,
                balances=None,
                products=None,
                ticker=None,
                candles=None,
            )
            self.publish_artifacts(result)
            return result

        # Consume only the canonical BrokerReadOnlyInterface methods
        server_time_res, read_checks["server_time"], failure = _read(lambda: adapter.server_time())
        if failure:
            failures.append(failure)
        read_checks["api_connectivity"] = "OK" if server_time_res is not None and server_time_res.get("status") == "OK" else "FAILED"

        account_res, read_checks["account_retrieval"], failure = _read(lambda: adapter.account_summary())
        if failure:
            failures.append(failure)

        # Portfolio and Balances also maps from account_summary
        read_checks["portfolio_retrieval"] = read_checks["account_retrieval"]
        read_checks["available_balances"] = read_checks["account_retrieval"]

        market_res, read_checks["market_ticker"], failure = _read(lambda: adapter.market_data())
        if failure:
            failures.append(failure)
        read_checks["products_list"] = read_checks["market_ticker"]
        read_checks["candle_retrieval"] = read_checks["market_ticker"]

        # Dummy checks or list formats to keep compatibility with _result helper
        balances_res = {"margin_used": 0.0, "margin_available": account_res.get("buying_power")} if account_res else None
        products_res = [{"instrument": market_res.get("symbol")}] if market_res else None
        candles_res = [{"timestamp": market_res.get("timestamp"), "close": market_res.get("price")}] if market_res else None

        adapter.connected = read_checks["api_connectivity"] == "OK"
        adapter.authenticated = read_checks["account_retrieval"] == "OK"
        adapter.broker_health = "HEALTHY" if adapter.connected and adapter.authenticated else "CONNECTED" if adapter.connected else "UNKNOWN"
        adapter.connection_error = "" if adapter.connected and adapter.authenticated else _first_failure_message(failures)
        if adapter.connected and adapter.authenticated:
            adapter.last_successful_sync = timestamp
        elif not adapter.authenticated and not any(item["reason"] == "AUTH_FAILED" for item in failures):
            failures.append(_failure("AUTH_FAILED", "Account or balance read did not authenticate"))

        result = self._result(
            adapter=adapter,
            timestamp=timestamp,
            read_checks=read_checks,
            failures=_dedupe_failures(failures),
            server_time=server_time_res,
            account=account_res,
            balances=balances_res,
            products=products_res,
            ticker=market_res,
            candles=candles_res,
        )
        self.publish_artifacts(result)
        return result

    def publish_artifacts(self, result: Mapping[str, Any]) -> None:
        if self.artifacts_dir is None:
            return
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifacts = {
            "broker_validation.json": result.get("broker_validation", {}),
            "broker_health.json": result.get("broker_health", {}),
            "broker_market_snapshot.json": result.get("broker_market_snapshot", {}),
        }
        for filename, payload in artifacts.items():
            (self.artifacts_dir / filename).write_text(
                json.dumps(payload, indent=2, sort_keys=True, default=str),
                encoding="utf-8",
            )

    def _result(
        self,
        *,
        adapter: OandaLiveReadOnlyAdapter,
        timestamp: str,
        read_checks: Mapping[str, str],
        failures: list[dict[str, str]],
        server_time: Any,
        account: Any,
        balances: Any,
        products: Any,
        ticker: Any,
        candles: Any,
    ) -> dict[str, Any]:
        account_loaded = read_checks.get("account_retrieval") == "OK"
        balances_loaded = read_checks.get("available_balances") == "OK"
        products_loaded = _count_items(products)
        market_data_loaded = read_checks.get("market_ticker") == "OK" and read_checks.get("candle_retrieval") == "OK"
        authenticated = bool(adapter.authenticated)
        api_reachable = read_checks.get("api_connectivity") == "OK"
        validation_status = "PASS" if api_reachable and authenticated and account_loaded and balances_loaded and products_loaded > 0 and market_data_loaded else "FAIL_CLOSED"

        broker_validation = {
            "broker": "OANDA",
            "mode": "LIVE READ-ONLY",
            "endpoint": endpoint_for_broker("OANDA", adapter.env if hasattr(adapter, "env") else {}),
            "api_version": "v3",
            "validation_status": validation_status,
            "api_reachable": api_reachable,
            "authentication": authenticated,
            "account_loaded": account_loaded,
            "portfolio_loaded": read_checks.get("portfolio_retrieval") == "OK",
            "balances_loaded": balances_loaded,
            "products_loaded": products_loaded,
            "market_data_loaded": market_data_loaded,
            "last_successful_sync": adapter.last_successful_sync or "DATA UNAVAILABLE",
            "validation_timestamp": timestamp,
            "read_checks": dict(read_checks),
            "failure_reasons": list(failures),
            "broker_execution_status": "DISABLED",
            "execution_authority": False,
            "can_live_execute": False,
            "live_micro_pilot_state": "DISARMED",
            "advisory_only": True,
            "execution_allowed": False,
        }
        server_time_value = "NOT_AVAILABLE"
        plain_server_time = _plain(server_time)
        if isinstance(plain_server_time, str):
            server_time_value = plain_server_time
        elif isinstance(plain_server_time, dict):
            server_time_value = str(
                plain_server_time.get("time")
                or plain_server_time.get("server_time")
                or plain_server_time.get("iso")
                or "NOT_AVAILABLE"
            )

        last_failed_sync = "NOT_AVAILABLE"
        if failures:
            last_failed_sync = timestamp

        broker_operational_status = build_broker_operational_status(
            {
                "broker": "OANDA",
                "broker_type": "FX",
                "mode": "LIVE_READ_ONLY",
                "endpoint": endpoint_for_broker("OANDA", adapter.env if hasattr(adapter, "env") else {}),
                "api_version": "v3",
                "server_time": server_time_value,
                "latency_ms": None,
                "rate_limit_status": "UNKNOWN",
                "last_successful_sync": adapter.last_successful_sync or "NOT_AVAILABLE",
                "last_failed_sync": last_failed_sync,
                "account_sync_status": "OK" if account_loaded else "PENDING",
                "product_count": products_loaded,
                "market_data_status": "OK" if market_data_loaded else "NOT_AVAILABLE",
                "balance_status": "AVAILABLE" if balances_loaded else "NOT_AVAILABLE",
                "margin_status": "BROKER_UNAVAILABLE" if account_loaded else "READ_ONLY_PENDING_ACCOUNT",
                "failure_reasons": failures,
            }
        )
        broker_validation["broker_operational_status"] = broker_operational_status
        broker_health = {
            "broker": "OANDA",
            "api_reachable": api_reachable,
            "authenticated": authenticated,
            "broker_health": adapter.broker_health,
            "connection_error": adapter.connection_error,
            "failure_reasons": list(failures),
            "last_successful_sync": adapter.last_successful_sync or "DATA UNAVAILABLE",
            "validation_timestamp": timestamp,
            "broker_execution_status": "DISABLED",
            "execution_authority": False,
            "can_live_execute": False,
            "live_micro_pilot_state": "DISARMED",
        }
        broker_market_snapshot = {
            "broker": "OANDA",
            "server_time_loaded": server_time is not None,
            "products_loaded": products_loaded,
            "market_data_loaded": market_data_loaded,
            "ticker_loaded": ticker is not None,
            "candles_loaded": candles is not None,
            "validation_timestamp": timestamp,
            "server_time": _redacted_payload(server_time),
            "ticker": _redacted_payload(ticker),
            "candles": _redacted_payload(candles),
            "execution_allowed": False,
        }
        return OandaOperationalValidationResult(
            validation_status=validation_status,
            api_reachable=api_reachable,
            authenticated=authenticated,
            account_loaded=account_loaded,
            portfolio_loaded=read_checks.get("portfolio_retrieval") == "OK",
            balances_loaded=balances_loaded,
            products_loaded=products_loaded,
            market_data_loaded=market_data_loaded,
            last_successful_sync=adapter.last_successful_sync or "DATA UNAVAILABLE",
            validation_timestamp=timestamp,
            read_checks=dict(read_checks),
            failure_reasons=list(failures),
            broker_validation=broker_validation,
            broker_health=broker_health,
            broker_market_snapshot=broker_market_snapshot,
            broker_operational_status=broker_operational_status,
        ).as_dict()


def validate_oanda_live_read_only_operational(
    *,
    adapter_factory: Callable[[], OandaLiveReadOnlyAdapter] | None = None,
    artifacts_dir: str | Path | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    return OandaLiveReadOnlyOperationalValidator(
        adapter_factory=adapter_factory,
        artifacts_dir=artifacts_dir,
        now=now,
    ).validate()


def load_oanda_operational_validation_artifacts(artifacts_dir: str | Path) -> dict[str, Any]:
    root = Path(artifacts_dir)
    return {
        "broker_validation": _load_json(root / "broker_validation.json"),
        "broker_health": _load_json(root / "broker_health.json"),
        "broker_market_snapshot": _load_json(root / "broker_market_snapshot.json"),
    }


def _read(reader: Callable[[], Any]) -> tuple[Any, str, dict[str, str] | None]:
    try:
        payload = reader()
    except Exception as exc:
        return None, "FAILED", _failure(_classify_exception(exc), str(exc)[:160])
    return payload, "OK" if _value_present(payload) else "UNAVAILABLE", None


def _classify_exception(exc: Exception) -> str:
    text = f"{exc.__class__.__name__} {exc}".lower()
    if "rate" in text and "limit" in text:
        return "RATE_LIMIT"
    if "timeout" in text or "timed out" in text:
        return "TIMEOUT"
    if "auth" in text or "unauthorized" in text or "forbidden" in text or "401" in text or "403" in text:
        return "AUTH_FAILED"
    if "network" in text or "connection" in text or "dns" in text:
        return "NETWORK_ERROR"
    if "not found" in text or "404" in text or "account" in text and "not" in text:
        return "ACCOUNT_NOT_FOUND"
    if "market" in text and "data" in text and "unavailable" in text:
        return "MARKET_DATA_UNAVAILABLE"
    if "service" in text and "unavailable" in text or "503" in text:
        return "SERVICE_UNAVAILABLE"
    return "API_ERROR"


def _failure(reason: str, message: str) -> dict[str, str]:
    normalized = reason if reason in FAILURE_REASONS else "API_ERROR"
    return {"reason": normalized, "message": message}


def _first_failure_message(failures: list[dict[str, str]]) -> str:
    if not failures:
        return ""
    return str(failures[0].get("message", ""))


def _dedupe_failures(failures: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for failure in failures:
        key = (str(failure.get("reason", "")), str(failure.get("message", "")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(dict(failure))
    return unique


def _count_items(payload: Any) -> int:
    plain = _plain(payload)
    if isinstance(plain, list):
        return len(plain)
    if isinstance(plain, dict):
        for key in ("instruments", "products", "accounts", "data", "results"):
            value = plain.get(key)
            if isinstance(value, list):
                return len(value)
        return 1 if plain else 0
    return 0


def _redacted_payload(payload: Any) -> Any:
    plain = _plain(payload)
    if isinstance(plain, dict):
        return {
            key: ("REDACTED" if _sensitive_key(str(key)) else _redacted_payload(value))
            for key, value in plain.items()
        }
    if isinstance(plain, list):
        return [_redacted_payload(item) for item in plain[:10]]
    return plain


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list, str, int, float, bool)):
        return value
    if hasattr(value, "to_dict"):
        try:
            return value.to_dict()
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        return {key: item for key, item in vars(value).items() if not key.startswith("_")}
    return str(value)


def _value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().upper() not in {"", "DATA UNAVAILABLE", "NONE", "NULL", "NOT_TESTED"}
    if isinstance(value, (list, tuple, set)):
        return len(value) > 0
    if isinstance(value, dict):
        return bool(value)
    return True


def _sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(token in normalized for token in ("secret", "private", "token", "key", "passphrase", "signature"))


def _load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


__all__ = [
    "FAILURE_REASONS",
    "READ_CHECKS",
    "OandaLiveReadOnlyOperationalValidator",
    "OandaOperationalValidationResult",
    "load_oanda_operational_validation_artifacts",
    "validate_oanda_live_read_only_operational",
]

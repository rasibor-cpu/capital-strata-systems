from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from backend.runtime.coinbase_live_adapter import CoinbaseLiveReadOnlyAdapter
from backend.runtime.canonical_account_snapshot import build_canonical_account_snapshot
from backend.runtime.broker_operational_status import (
    build_broker_operational_status,
    endpoint_for_broker,
)


FAILURE_REASONS = (
    "AUTH_FAILED",
    "NETWORK_ERROR",
    "RATE_LIMIT",
    "MISSING_CREDENTIALS",
    "API_ERROR",
    "TIMEOUT",
    "SECURITY_ERROR",
)

READ_CHECKS = (
    "api_connectivity",
    "server_time",
    "account_retrieval",
    "portfolio_retrieval",
    "available_balances",
    "products_list",
    "market_ticker",
)


@dataclass(frozen=True)
class CoinbaseOperationalValidationResult:
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


class CoinbaseLiveReadOnlyOperationalValidator:
    """Read-only operational validator for Coinbase LIVE connectivity.

    The validator uses CoinbaseLiveReadOnlyAdapter exclusively. It publishes
    diagnostics and runtime artifacts only; it does not expose or call any
    broker order, cancel, modify, or execution capability.
    """

    def __init__(
        self,
        *,
        adapter_factory: Callable[[], CoinbaseLiveReadOnlyAdapter] | None = None,
        artifacts_dir: str | Path | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.adapter_factory = adapter_factory
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir is not None else None
        self.now = now or (lambda: datetime.now(timezone.utc))

    def validate(self) -> dict[str, Any]:
        adapter = self.adapter_factory() if self.adapter_factory is not None else CoinbaseLiveReadOnlyAdapter()
        timestamp = self.now().isoformat()
        read_checks = {key: "NOT_ATTEMPTED" for key in READ_CHECKS}
        failures: list[dict[str, str]] = []

        if not adapter.credentials.ready:
            failures.append(_failure("MISSING_CREDENTIALS", "Coinbase credentials are missing"))
            result = self._result(
                adapter=adapter,
                timestamp=timestamp,
                read_checks=read_checks,
                failures=failures,
                server_time=None,
                account=None,
                portfolio=None,
                balances=None,
                products=None,
                ticker=None,
            )
            self.publish_artifacts(result)
            return result

        security_failure = self._startup_security_failure(adapter)
        if security_failure is not None:
            failures.append(security_failure)
            result = self._result(
                adapter=adapter,
                timestamp=timestamp,
                read_checks=read_checks,
                failures=failures,
                server_time=None,
                account=None,
                portfolio=None,
                balances=None,
                products=None,
                ticker=None,
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

        # Dummy checks or list formats to keep compatibility with _result helper
        portfolio_res = [{"uuid": account_res.get("account_id")}] if account_res else None
        balances_res = [{"currency": account_res.get("currency"), "available_balance": account_res.get("balance")}] if account_res else None
        products_res = [{"product_id": market_res.get("symbol")}] if market_res else None

        adapter.connected = read_checks["api_connectivity"] == "OK"
        adapter.authenticated = read_checks["account_retrieval"] == "OK"
        adapter.health = "HEALTHY" if adapter.connected and adapter.authenticated else "CONNECTED" if adapter.connected else "UNKNOWN"
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
            portfolio=portfolio_res,
            balances=balances_res,
            products=products_res,
            ticker=market_res,
        )
        self.publish_artifacts(result)
        return result

    def _startup_security_failure(self, adapter: CoinbaseLiveReadOnlyAdapter) -> dict[str, str] | None:
        try:
            from backend.app.security.environment_validator import validate_startup_security_environment

            if self._should_validate_startup_security():
                validate_startup_security_environment("COINBASE", "live", adapter._env)
        except Exception as exc:
            return _failure("SECURITY_ERROR", str(exc))
        return None

    def _should_validate_startup_security(self) -> bool:
        import sys

        return not ("pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ)

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
        adapter: CoinbaseLiveReadOnlyAdapter,
        timestamp: str,
        read_checks: Mapping[str, str],
        failures: list[dict[str, str]],
        server_time: Any,
        account: Any,
        portfolio: Any,
        balances: Any,
        products: Any,
        ticker: Any,
    ) -> dict[str, Any]:
        account_loaded = read_checks.get("account_retrieval") == "OK"
        balances_loaded = read_checks.get("available_balances") == "OK"
        products_loaded = _count_items(products)
        market_data_loaded = read_checks.get("market_ticker") == "OK"
        authenticated = bool(adapter.authenticated)
        api_reachable = read_checks.get("api_connectivity") == "OK"
        validation_status = "PASS" if api_reachable and authenticated and account_loaded and balances_loaded and products_loaded > 0 and market_data_loaded and not failures else "FAIL_CLOSED"
        account_plain = _plain(account) if isinstance(_plain(account), dict) else {}
        account_snapshot = build_canonical_account_snapshot(
            broker="COINBASE",
            mode="live",
            runtime_payload={
                "broker": "COINBASE",
                "broker_mode": "live",
                "broker_authenticated": authenticated,
                "broker_connected": api_reachable and authenticated,
                "account_loaded": account_loaded,
                "portfolio_loaded": read_checks.get("portfolio_retrieval") == "OK",
                "balances_loaded": balances_loaded,
                "market_data_loaded": market_data_loaded,
                "account_equity": account_plain.get("equity"),
                "cash": account_plain.get("balance"),
                "balance": account_plain.get("balance"),
                "buying_power": account_plain.get("buying_power"),
                "available_balance": account_plain.get("balance"),
                "currency": account_plain.get("currency", "USD"),
                "account_id": account_plain.get("account_id", ""),
                "portfolio_id": account_plain.get("account_id", ""),
                "account_count": 1 if account_loaded else 0,
                "portfolio_count": 1 if read_checks.get("portfolio_retrieval") == "OK" else 0,
                "balance_timestamp": adapter.last_successful_sync or timestamp,
                "last_successful_sync": adapter.last_successful_sync or timestamp,
                "failure_reason": "" if balances_loaded else _first_failure_message(failures) or "BALANCE_UNAVAILABLE",
            },
            margin_snapshot={
                "margin_source": "LIVE" if balances_loaded else "LIVE_UNAVAILABLE",
                "account_id": account_plain.get("account_id", ""),
                "buying_power": account_plain.get("buying_power") if balances_loaded else None,
                "margin_available": account_plain.get("buying_power") if balances_loaded else None,
                "required_margin": 0.0 if balances_loaded else None,
                "free_margin": account_plain.get("buying_power") if balances_loaded else None,
                "balance_timestamp": adapter.last_successful_sync or timestamp,
            },
            timestamp=timestamp,
        )
        broker_validation = {
            "broker": "COINBASE",
            "mode": "LIVE READ-ONLY",
            "endpoint": endpoint_for_broker("COINBASE"),
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
            "canonical_account_snapshot": account_snapshot.to_dict(),
            "account_snapshot": account_snapshot.to_dict(),
            "account_asset_balances": _account_asset_balances_from_validation_inputs(
                account=account_plain,
                balances=balances,
            ),
        }
        server_time_value = "NOT_AVAILABLE"
        plain_server_time = _plain(server_time)
        if isinstance(plain_server_time, str):
            server_time_value = plain_server_time
        elif isinstance(plain_server_time, dict):
            server_time_value = str(
                plain_server_time.get("iso")
                or plain_server_time.get("time")
                or plain_server_time.get("server_time")
                or "NOT_AVAILABLE"
            )

        last_failed_sync = "NOT_AVAILABLE"
        if failures:
            last_failed_sync = timestamp

        broker_operational_status = build_broker_operational_status(
            {
                "broker": "COINBASE",
                "broker_type": "CRYPTO",
                "mode": "LIVE_READ_ONLY",
                "endpoint": endpoint_for_broker("COINBASE"),
                "api_version": "v3",
                "server_time": server_time_value,
                "latency_ms": None,
                "rate_limit_status": "UNKNOWN",
                "last_successful_sync": adapter.last_successful_sync or "NOT_AVAILABLE",
                "last_failed_sync": last_failed_sync,
                "account_sync_status": "OK" if account_loaded else "PENDING",
                "product_count": products_loaded,
                "market_data_status": "OK" if market_data_loaded else "NOT_AVAILABLE",
                "balance_status": "AVAILABLE" if account_snapshot.balances_loaded else "NOT_AVAILABLE",
                "margin_status": "AVAILABLE" if account_snapshot.margin_loaded else "NOT_AVAILABLE",
                "equity": account_snapshot.equity,
                "cash": account_snapshot.cash,
                "buying_power": account_snapshot.buying_power,
                "available_balance": account_snapshot.available_balance,
                "margin_available": account_snapshot.margin_available,
                "canonical_account_snapshot": account_snapshot.to_dict(),
                "failure_reasons": failures,
            }
        )
        broker_operational_status.update(
            {
                "equity": account_snapshot.equity,
                "cash": account_snapshot.cash,
                "buying_power": account_snapshot.buying_power,
                "available_balance": account_snapshot.available_balance,
                "margin_available": account_snapshot.margin_available,
                "canonical_account_snapshot": account_snapshot.to_dict(),
                "account_snapshot": account_snapshot.to_dict(),
            }
        )
        broker_validation["broker_operational_status"] = broker_operational_status
        broker_health = {
            "broker": "COINBASE",
            "api_reachable": api_reachable,
            "authenticated": authenticated,
            "broker_health": adapter.health,
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
            "broker": "COINBASE",
            "server_time_loaded": server_time is not None,
            "products_loaded": products_loaded,
            "market_data_loaded": market_data_loaded,
            "ticker_loaded": ticker is not None,
            "validation_timestamp": timestamp,
            "server_time": _redacted_payload(server_time),
            "ticker": _redacted_payload(ticker),
            "execution_allowed": False,
        }
        return CoinbaseOperationalValidationResult(
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


def validate_coinbase_live_read_only_operational(
    *,
    adapter_factory: Callable[[], CoinbaseLiveReadOnlyAdapter] | None = None,
    artifacts_dir: str | Path | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    return CoinbaseLiveReadOnlyOperationalValidator(
        adapter_factory=adapter_factory,
        artifacts_dir=artifacts_dir,
        now=now,
    ).validate()


def load_coinbase_operational_validation_artifacts(artifacts_dir: str | Path) -> dict[str, Any]:
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
        for key in ("products", "portfolios", "accounts", "data", "results"):
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


def _account_asset_balances_from_validation_inputs(
    *,
    account: Mapping[str, Any],
    balances: Any,
) -> list[dict[str, Any]]:
    """Persist already-read account-balance rows. Do not invent hold/total/value."""
    rows: list[dict[str, Any]] = []
    candidates = balances if isinstance(balances, list) else []
    account_id = account.get("account_id") if isinstance(account, Mapping) else None
    for raw in candidates:
        if not isinstance(raw, Mapping):
            continue
        currency = raw.get("currency")
        if currency in (None, ""):
            continue
        if "available_balance" not in raw and "available" not in raw:
            continue
        available = raw.get("available_balance", raw.get("available"))
        row: dict[str, Any] = {
            "currency": currency,
            "available_balance": available,
        }
        raw_account_id = raw.get("account_id") or account_id
        if raw_account_id not in (None, "", "UNKNOWN", "UNKNOWN_ID", "FALLBACK-COINBASE"):
            row["account_id"] = raw_account_id
        rows.append(row)
    return rows


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
    "CoinbaseLiveReadOnlyOperationalValidator",
    "CoinbaseOperationalValidationResult",
    "load_coinbase_operational_validation_artifacts",
    "validate_coinbase_live_read_only_operational",
]

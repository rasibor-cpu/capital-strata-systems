"""Binance LIVE_READ_ONLY operational validation. Read-only artifacts only."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.app.brokers.binance_live_read_only_adapter import (
    DEFAULT_BINANCE_REST_URL,
    SOURCE_BINANCE_LIVE_READ_ONLY,
    BinanceConfigurationError,
    BinanceLiveReadOnlyAdapter,
)
from backend.executive_intelligence.freshness_policy import gate_config, load_freshness_policy
from backend.runtime.broker_operational_status import build_broker_operational_status


FAILURE_REASONS = (
    "AUTH_FAILED",
    "NETWORK_ERROR",
    "RATE_LIMIT",
    "MISSING_CREDENTIALS",
    "API_ERROR",
    "TIMEOUT",
    "SECURITY_ERROR",
    "STALE_TIMESTAMP",
    "FUTURE_TIMESTAMP",
    "MALFORMED_TIMESTAMP",
)

READ_CHECKS = (
    "api_connectivity",
    "server_time",
    "account_retrieval",
    "available_balances",
    "products_list",
    "market_ticker",
)

_BROKER_SNAPSHOT_GATE = "broker_snapshot"
_UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class BinanceOperationalValidationResult:
    validation_status: str
    api_reachable: bool
    authenticated: bool
    account_loaded: bool
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
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    open_positions_availability: str = _UNAVAILABLE
    session_pnl_availability: str = _UNAVAILABLE
    maturity_availability: str = _UNAVAILABLE

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class BinanceLiveReadOnlyOperationalValidator:
    """Read-only operational validator for Binance LIVE connectivity.

    Uses BinanceLiveReadOnlyAdapter exclusively. Publishes sanitized diagnostics
    only. Never calls order, cancel, modify, withdrawal, or execution methods.
    """

    def __init__(
        self,
        *,
        adapter_factory: Callable[[], BinanceLiveReadOnlyAdapter] | None = None,
        artifacts_dir: str | Path | None = None,
        now: Callable[[], datetime] | None = None,
        policy: Mapping[str, Any] | None = None,
        policy_path: Path | str | None = None,
    ) -> None:
        self.adapter_factory = adapter_factory
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir is not None else None
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.policy = policy
        self.policy_path = policy_path

    def validate(self) -> dict[str, Any]:
        adapter = self.adapter_factory() if self.adapter_factory is not None else BinanceLiveReadOnlyAdapter()
        timestamp = self.now().astimezone(timezone.utc).isoformat()
        read_checks = {key: "NOT_ATTEMPTED" for key in READ_CHECKS}
        failures: list[dict[str, str]] = []

        diagnostics = adapter.credential_diagnostics()
        if diagnostics.get("credential_status") != "PRESENT":
            failures.append(_failure("MISSING_CREDENTIALS", "Binance credentials are missing"))
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
                balances=None,
                products=None,
                ticker=None,
            )
            self.publish_artifacts(result)
            return result

        server_time_res, read_checks["server_time"], failure = _read(adapter.server_time)
        if failure:
            failures.append(failure)
        freshness = self._evaluate_server_time_freshness(server_time_res)
        if server_time_res is not None and not freshness["ok"]:
            failures.append(_failure(freshness["reason"], freshness["message"]))
            read_checks["api_connectivity"] = "FAILED"
        else:
            read_checks["api_connectivity"] = (
                "OK" if server_time_res is not None and server_time_res.get("status") == "OK" else "FAILED"
            )
            if read_checks["api_connectivity"] != "OK" and not failure:
                failures.append(_failure("API_ERROR", "Binance server time was not reachable"))

        account_res, read_checks["account_retrieval"], failure = _read(adapter.account_summary)
        if failure:
            failures.append(failure)
        balances = list(account_res.get("balances") or []) if isinstance(account_res, Mapping) else None
        read_checks["available_balances"] = (
            "OK" if isinstance(balances, list) and read_checks["account_retrieval"] == "OK" else read_checks["account_retrieval"]
        )

        products_res, read_checks["products_list"], failure = _read(adapter.get_products)
        if failure:
            failures.append(failure)

        ticker_res, read_checks["market_ticker"], failure = _read(adapter.market_data)
        if failure:
            failures.append(failure)

        adapter.connected = read_checks["api_connectivity"] == "OK"
        adapter.authenticated = read_checks["account_retrieval"] == "OK"
        adapter.health = (
            "HEALTHY"
            if adapter.connected and adapter.authenticated
            else "CONNECTED"
            if adapter.connected
            else "UNKNOWN"
        )
        adapter.connection_error = "" if adapter.connected and adapter.authenticated else _first_failure_message(failures)
        if adapter.connected and adapter.authenticated:
            adapter.last_successful_sync = timestamp
        elif not adapter.authenticated and not any(item["reason"] == "AUTH_FAILED" for item in failures):
            if read_checks["account_retrieval"] != "OK":
                failures.append(_failure("AUTH_FAILED", "Account or balance read did not authenticate"))

        result = self._result(
            adapter=adapter,
            timestamp=timestamp,
            read_checks=read_checks,
            failures=_dedupe_failures(failures),
            server_time=server_time_res,
            account=account_res,
            balances=balances,
            products=products_res,
            ticker=ticker_res,
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
                json.dumps(_redacted_payload(payload), indent=2, sort_keys=True, default=str),
                encoding="utf-8",
            )

    def _startup_security_failure(self, adapter: BinanceLiveReadOnlyAdapter) -> dict[str, str] | None:
        try:
            from backend.app.security.environment_validator import validate_startup_security_environment

            if self._should_validate_startup_security():
                validate_startup_security_environment("BINANCE", "live", adapter._env)
        except Exception as exc:
            return _failure("SECURITY_ERROR", str(exc)[:160])
        return None

    def _should_validate_startup_security(self) -> bool:
        import sys

        return not ("pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ)

    def _evaluate_server_time_freshness(self, server_time: Any) -> dict[str, Any]:
        if not isinstance(server_time, Mapping) or not server_time:
            return {"ok": False, "reason": "MALFORMED_TIMESTAMP", "message": "missing_server_time"}
        raw = server_time.get("timestamp") or server_time.get("server_time_ms")
        parsed = _parse_aware_utc(raw)
        if parsed is None:
            return {"ok": False, "reason": "MALFORMED_TIMESTAMP", "message": "malformed_or_naive_server_time"}
        clock = self.now()
        if clock.tzinfo is None:
            return {"ok": False, "reason": "MALFORMED_TIMESTAMP", "message": "naive_now_timestamp"}
        clock = clock.astimezone(timezone.utc)
        if parsed > clock + timedelta(seconds=1):
            return {"ok": False, "reason": "FUTURE_TIMESTAMP", "message": "future_server_time"}
        max_age = _broker_snapshot_max_age_seconds(self.policy, self.policy_path)
        if max_age is None:
            return {"ok": False, "reason": "MALFORMED_TIMESTAMP", "message": "freshness_policy_unusable"}
        age = (clock - parsed).total_seconds()
        if age > max_age:
            return {"ok": False, "reason": "STALE_TIMESTAMP", "message": "stale_server_time"}
        return {"ok": True, "reason": "ok", "message": "fresh", "age_seconds": age, "max_age_seconds": max_age}

    def _result(
        self,
        *,
        adapter: BinanceLiveReadOnlyAdapter,
        timestamp: str,
        read_checks: Mapping[str, str],
        failures: list[dict[str, str]],
        server_time: Any,
        account: Any,
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
        validation_status = (
            "PASS"
            if api_reachable
            and authenticated
            and account_loaded
            and balances_loaded
            and products_loaded > 0
            and market_data_loaded
            and not failures
            else "FAIL_CLOSED"
        )
        account_plain = _plain(account) if isinstance(_plain(account), dict) else {}
        asset_rows = _account_asset_balances(account_plain, balances)
        broker_validation = {
            "broker": "BINANCE",
            "mode": "LIVE READ-ONLY",
            "endpoint": adapter.base_url or DEFAULT_BINANCE_REST_URL,
            "api_version": "v3",
            "validation_status": validation_status,
            "api_reachable": api_reachable,
            "authentication": authenticated,
            "account_loaded": account_loaded,
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
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "open_positions_availability": _UNAVAILABLE,
            "session_pnl_availability": _UNAVAILABLE,
            "maturity_availability": _UNAVAILABLE,
            "section_label": "Account Asset Balances",
            "account_asset_balances": asset_rows,
            "source": SOURCE_BINANCE_LIVE_READ_ONLY if validation_status == "PASS" else _UNAVAILABLE,
        }
        server_time_value = "NOT_AVAILABLE"
        plain_server_time = _plain(server_time)
        if isinstance(plain_server_time, str):
            server_time_value = plain_server_time
        elif isinstance(plain_server_time, dict):
            server_time_value = str(
                plain_server_time.get("timestamp")
                or plain_server_time.get("server_time")
                or plain_server_time.get("iso")
                or "NOT_AVAILABLE"
            )
        last_failed_sync = timestamp if failures else "NOT_AVAILABLE"
        broker_operational_status = build_broker_operational_status(
            {
                "broker": "BINANCE",
                "broker_type": "CRYPTO",
                "mode": "LIVE_READ_ONLY",
                "endpoint": adapter.base_url or DEFAULT_BINANCE_REST_URL,
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
                "margin_status": "UNAVAILABLE",
                "failure_reasons": failures,
                "execution_allowed": False,
                "advisory_only": True,
            }
        )
        broker_validation["broker_operational_status"] = broker_operational_status
        broker_health = {
            "broker": "BINANCE",
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
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        }
        broker_market_snapshot = {
            "broker": "BINANCE",
            "server_time_loaded": server_time is not None,
            "products_loaded": products_loaded,
            "market_data_loaded": market_data_loaded,
            "ticker_loaded": ticker is not None,
            "validation_timestamp": timestamp,
            "server_time": _redacted_payload(server_time),
            "ticker": _redacted_payload(ticker),
            "execution_allowed": False,
            "market_value_availability": _UNAVAILABLE,
        }
        return BinanceOperationalValidationResult(
            validation_status=validation_status,
            api_reachable=api_reachable,
            authenticated=authenticated,
            account_loaded=account_loaded,
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


def validate_binance_live_read_only_operational(
    *,
    adapter_factory: Callable[[], BinanceLiveReadOnlyAdapter] | None = None,
    artifacts_dir: str | Path | None = None,
    now: Callable[[], datetime] | None = None,
    policy: Mapping[str, Any] | None = None,
    policy_path: Path | str | None = None,
) -> dict[str, Any]:
    return BinanceLiveReadOnlyOperationalValidator(
        adapter_factory=adapter_factory,
        artifacts_dir=artifacts_dir,
        now=now,
        policy=policy,
        policy_path=policy_path,
    ).validate()


def load_binance_operational_validation_artifacts(artifacts_dir: str | Path) -> dict[str, Any]:
    root = Path(artifacts_dir)
    return {
        "broker_validation": _load_json(root / "broker_validation.json"),
        "broker_health": _load_json(root / "broker_health.json"),
        "broker_market_snapshot": _load_json(root / "broker_market_snapshot.json"),
    }


def _broker_snapshot_max_age_seconds(
    policy: Mapping[str, Any] | None,
    policy_path: Path | str | None,
) -> float | None:
    try:
        loaded = dict(policy) if isinstance(policy, Mapping) else load_freshness_policy(policy_path=policy_path)
        cfg = gate_config(loaded, _BROKER_SNAPSHOT_GATE)
        value = float(cfg["max_age_seconds"])
    except Exception:
        return None
    if value != value or value <= 0 or value == float("inf"):
        return None
    return value


def _parse_aware_utc(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _read(reader: Callable[[], Any]) -> tuple[Any, str, dict[str, str] | None]:
    try:
        payload = reader()
    except BinanceConfigurationError as exc:
        return None, "FAILED", _failure("MISSING_CREDENTIALS", str(exc)[:160])
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
    if "malformed" in text or "naive" in text:
        return "MALFORMED_TIMESTAMP" if "time" in text else "API_ERROR"
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
        for key in ("products", "symbols", "balances", "data", "results"):
            value = plain.get(key)
            if isinstance(value, list):
                return len(value)
        return 1 if plain else 0
    return 0


def _account_asset_balances(account: Mapping[str, Any], balances: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    candidates = balances if isinstance(balances, list) else account.get("balances") if isinstance(account.get("balances"), list) else []
    account_id = account.get("account_id")
    for raw in candidates:
        if not isinstance(raw, Mapping):
            continue
        asset = raw.get("asset") or raw.get("currency")
        if asset in (None, ""):
            continue
        if raw.get("available_quantity_availability") != "AVAILABLE" and "available_quantity" not in raw and "available_balance" not in raw:
            continue
        available = raw.get("available_quantity", raw.get("available_balance"))
        row: dict[str, Any] = {
            "asset": str(asset).upper(),
            "available_quantity": available,
            "available_quantity_availability": raw.get("available_quantity_availability") or "AVAILABLE",
            "held_quantity": raw.get("held_quantity"),
            "held_quantity_availability": raw.get("held_quantity_availability") or _UNAVAILABLE,
            "total_quantity": raw.get("total_quantity"),
            "total_quantity_availability": raw.get("total_quantity_availability") or _UNAVAILABLE,
            "total_quantity_provenance": raw.get("total_quantity_provenance") or _UNAVAILABLE,
            "market_value": None,
            "market_value_availability": _UNAVAILABLE,
            "availability": raw.get("availability") or "AVAILABLE",
            "provenance": raw.get("provenance") or SOURCE_BINANCE_LIVE_READ_ONLY,
        }
        if account_id not in (None, "", "UNKNOWN"):
            row["account_id"] = account_id
        rows.append(row)
    return rows


def _redacted_payload(payload: Any) -> Any:
    plain = _plain(payload)
    if isinstance(plain, dict):
        return {
            key: ("REDACTED" if _sensitive_key(str(key)) else _redacted_payload(value))
            for key, value in plain.items()
        }
    if isinstance(plain, list):
        return [_redacted_payload(item) for item in plain[:20]]
    if isinstance(plain, str) and _looks_like_secret(plain):
        return "REDACTED"
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
    return any(
        token in normalized
        for token in ("secret", "private", "token", "api_key", "apikey", "passphrase", "signature", "x-mbx-apikey")
    )


def _looks_like_secret(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in ("api_secret", "binance_api_secret", "x-mbx-apikey"))


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
    "BinanceLiveReadOnlyOperationalValidator",
    "BinanceOperationalValidationResult",
    "load_binance_operational_validation_artifacts",
    "validate_binance_live_read_only_operational",
]

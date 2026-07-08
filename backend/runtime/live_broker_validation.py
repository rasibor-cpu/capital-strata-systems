from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.brokers.broker_bootstrap import initialize_broker
from backend.app.brokers.execution_boundary import validate_execution_boundary
from backend.runtime.broker_credential_diagnostics import (
    classify_auth_failure,
    diagnose_broker_credentials,
    diagnostics_payload,
)
from backend.runtime.broker_market_data_evidence import collect_market_data_evidence
from backend.runtime.live_execution_authority import evaluate_live_execution_authority


PASS = "PASS"
FAIL = "FAIL"
GREEN = "GREEN"
RED = "RED"
PAYLOAD_VERSION = "css.phase156a.live_broker_validation.v1"

SUPPORTED_BROKERS = {"oanda", "coinbase"}
STRUCTURAL_CREDENTIAL_FAILURES = {
    "MISSING_CREDENTIALS",
    "KEY_MISSING",
    "SECRET_MISSING",
    "PRIVATE_KEY_INVALID",
    "PEM_INVALID",
    "TOKEN_INVALID",
    "ACCOUNT_ID_MISSING",
}


CredentialDiagnosticsFn = Callable[..., Any]
InitializeBrokerFn = Callable[[str, str], Any]
AuthorityFn = Callable[[Mapping[str, Any]], Any]
ClockFn = Callable[[], float]


@dataclass(frozen=True)
class StageResult:
    status: str
    reason: str = ""
    details: dict[str, Any] | None = None
    latency_ms: int | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"status": self.status}
        if self.reason:
            payload["reason"] = self.reason
        if self.details:
            payload["details"] = _json_safe(self.details)
        if self.latency_ms is not None:
            payload["latency_ms"] = self.latency_ms
        return payload


class LiveBrokerValidationError(RuntimeError):
    """Raised only for invalid local validator usage, never for broker failures."""


class LiveBrokerValidationEngine:
    """
    Advisory read-only validation before controlled live broker testing.

    The engine is intentionally non-authoritative: every report keeps
    execution_allowed=False and live_trading_blocked=True regardless of broker
    health. Broker failures are converted into RED advisory reports.
    """

    def __init__(
        self,
        broker: str,
        *,
        mode: str = "live",
        env: Mapping[str, Any] | None = None,
        credential_diagnostics_fn: CredentialDiagnosticsFn = diagnose_broker_credentials,
        initialize_broker_fn: InitializeBrokerFn = initialize_broker,
        authority_fn: AuthorityFn = evaluate_live_execution_authority,
        clock: ClockFn = time.perf_counter,
    ) -> None:
        self.broker = _normalize_broker(broker)
        self.mode = str(mode or "live").strip().lower()
        self.env = env
        self.credential_diagnostics_fn = credential_diagnostics_fn
        self.initialize_broker_fn = initialize_broker_fn
        self.authority_fn = authority_fn
        self.clock = clock

    def validate(self) -> dict[str, Any]:
        stages: dict[str, StageResult] = {}
        blockers: list[str] = []
        adapter: Any = None

        credentials = self._validate_credentials()
        stages["credentials"] = credentials
        _collect_blocker(blockers, "credentials", credentials)

        if credentials.status == PASS:
            bootstrap = self._validate_bootstrap()
            adapter = bootstrap.details.get("adapter") if bootstrap.details else None
        else:
            bootstrap = StageResult(FAIL, "credential_validation_failed")
        stages["bootstrap"] = bootstrap
        _collect_blocker(blockers, "bootstrap", bootstrap)

        if bootstrap.status == PASS and adapter is not None:
            authentication = self._validate_authentication(adapter)
        else:
            authentication = StageResult(FAIL, "bootstrap_validation_failed")
        stages["authentication"] = authentication
        _collect_blocker(blockers, "authentication", authentication)

        if authentication.status == PASS and adapter is not None:
            account = self._validate_account(adapter)
        else:
            account = StageResult(FAIL, "authentication_validation_failed")
        stages["account"] = account
        _collect_blocker(blockers, "account", account)

        if authentication.status == PASS and adapter is not None:
            market_data = self._validate_market_data(adapter)
        else:
            market_data = StageResult(FAIL, "authentication_validation_failed")
        stages["market_data"] = market_data
        _collect_blocker(blockers, "market_data", market_data)

        firewall = self._validate_firewall()
        stages["execution_firewall"] = firewall
        _collect_blocker(blockers, "execution_firewall", firewall)

        overall = GREEN if all(stage.status == PASS for stage in stages.values()) else RED
        latency = {
            "authentication_ms": stages["authentication"].latency_ms,
            "account_query_ms": stages["account"].latency_ms,
            "market_data_ms": stages["market_data"].latency_ms,
        }

        report = {
            "payload_version": PAYLOAD_VERSION,
            "broker": self.broker.upper() if self.broker else "NONE",
            "mode": self.mode,
            "credentials": stages["credentials"].status,
            "bootstrap": stages["bootstrap"].status,
            "authentication": stages["authentication"].status,
            "account": stages["account"].status,
            "market_data": stages["market_data"].status,
            "latency_ms": _sum_latency(latency),
            "latency": latency,
            "execution_firewall": stages["execution_firewall"].status,
            "overall": overall,
            "advisory_only": True,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "blocker_reasons": blockers,
            "stage_results": {
                name: _redact_stage(result).as_dict()
                for name, result in stages.items()
            },
        }
        return _json_safe(report)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.validate(), indent=indent, sort_keys=True)

    def write_json_report(self, path: str | Path, *, indent: int = 2) -> dict[str, Any]:
        report = self.validate()
        write_live_broker_validation_report(report, path, indent=indent)
        return report

    def _validate_credentials(self) -> StageResult:
        if self.broker not in SUPPORTED_BROKERS:
            return StageResult(FAIL, f"unsupported_broker:{self.broker or 'none'}")

        try:
            diagnostics = self.credential_diagnostics_fn(self.broker, env=self.env)
            payload = diagnostics_payload(diagnostics)
        except Exception as exc:
            return StageResult(FAIL, _failure_reason(exc), {"exception_type": exc.__class__.__name__})

        reason = str(payload.get("canonical_failure_reason") or payload.get("failure_reason") or "").upper()
        credentials_present = bool(payload.get("credentials_present"))
        if not credentials_present or reason in STRUCTURAL_CREDENTIAL_FAILURES:
            return StageResult(
                FAIL,
                reason or "MISSING_CREDENTIALS",
                {
                    "credentials_present": credentials_present,
                    "readiness_status": payload.get("readiness_status"),
                    "missing_credential_fields": payload.get("missing_credential_fields", []),
                    "redacted": True,
                },
            )

        return StageResult(
            PASS,
            details={
                "credentials_present": True,
                "readiness_status": payload.get("readiness_status"),
                "canonical_failure_reason": reason or "NONE",
                "redacted": True,
            },
        )

    def _validate_bootstrap(self) -> StageResult:
        try:
            adapter = self.initialize_broker_fn(self.broker, self.mode)
        except Exception as exc:
            return StageResult(FAIL, _failure_reason(exc), {"exception_type": exc.__class__.__name__})

        if adapter is None:
            return StageResult(FAIL, "broker_adapter_unavailable")

        return StageResult(
            PASS,
            details={
                "adapter": adapter,
                "adapter_class": adapter.__class__.__name__,
            },
        )

    def _validate_authentication(self, adapter: Any) -> StageResult:
        started = self.clock()
        try:
            evidence = _call_first(
                adapter,
                (
                    ("authenticate", ()),
                    ("verify_authentication", ()),
                    ("validate_authentication", ()),
                    ("get_server_time", ()),
                    ("get_server_status", ()),
                    ("is_configured", ()),
                ),
            )
            if evidence is _NOT_FOUND:
                if self.broker == "oanda":
                    evidence = _call_first(adapter, (("get_account_summary", ()),))
                elif self.broker == "coinbase":
                    evidence = _call_first(adapter, (("get_accounts", ()), ("get_account", ()),))
            ok, reason = _read_success(evidence)
        except Exception as exc:
            return StageResult(
                FAIL,
                _failure_reason(exc),
                {"exception_type": exc.__class__.__name__},
                latency_ms=_elapsed_ms(self.clock, started),
            )

        return StageResult(
            PASS if ok else FAIL,
            "" if ok else reason,
            {"method": "read_only_authentication_probe"},
            latency_ms=_elapsed_ms(self.clock, started),
        )

    def _validate_account(self, adapter: Any) -> StageResult:
        started = self.clock()
        try:
            if self.broker == "oanda":
                details = _validate_oanda_account(adapter)
            elif self.broker == "coinbase":
                details = _validate_coinbase_account(adapter)
            else:
                details = {"valid": False, "reason": "unsupported_broker"}
        except Exception as exc:
            return StageResult(
                FAIL,
                _failure_reason(exc),
                {"exception_type": exc.__class__.__name__},
                latency_ms=_elapsed_ms(self.clock, started),
            )

        return StageResult(
            PASS if details.pop("valid", False) else FAIL,
            str(details.pop("reason", "")),
            details,
            latency_ms=_elapsed_ms(self.clock, started),
        )

    def _validate_market_data(self, adapter: Any) -> StageResult:
        started = self.clock()
        try:
            if self.broker == "oanda":
                details = _validate_oanda_market_data(adapter)
            elif self.broker == "coinbase":
                details = _validate_coinbase_market_data(adapter)
            else:
                details = {"valid": False, "reason": "unsupported_broker"}
        except Exception as exc:
            return StageResult(
                FAIL,
                _failure_reason(exc),
                {"exception_type": exc.__class__.__name__},
                latency_ms=_elapsed_ms(self.clock, started),
            )

        return StageResult(
            PASS if details.pop("valid", False) else FAIL,
            str(details.pop("reason", "")),
            details,
            latency_ms=_elapsed_ms(self.clock, started),
        )

    def _validate_firewall(self) -> StageResult:
        details: dict[str, Any] = {
            "execution_allowed": False,
            "live_trading_blocked": True,
            "advisory_only": True,
        }

        try:
            boundary = validate_execution_boundary(
                selected_mode="live",
                capital_source_label="SIMULATED",
            )
            details["execution_boundary_active"] = boundary.allowed is False
            details["execution_boundary_reason"] = boundary.reason
        except Exception as exc:
            return StageResult(FAIL, _failure_reason(exc), {"exception_type": exc.__class__.__name__})

        try:
            authority = self.authority_fn(
                {
                    "broker_readiness": {
                        "broker_name": self.broker.upper() if self.broker else "NONE",
                        "mode": self.mode,
                        "credentials_present": True,
                        "authenticated": True,
                        "connected": True,
                        "account_loaded": True,
                        "market_data_ready": True,
                        "execution_enabled": False,
                    },
                    "operator_requested_live": True,
                    "live_micro_pilot_state": "DISARMED",
                    "capital_governor": "PASS",
                    "unified_trade_gate": "PASS",
                    "margin_gate": "PASS",
                    "anti_bleed_guard": "PASS",
                    "rbac": "PASS",
                    "kill_switch": "CLEAR",
                    "go_no_go": "NO GO",
                }
            )
            payload = authority.as_dict() if hasattr(authority, "as_dict") else dict(authority)
            details["execution_authority"] = bool(payload.get("execution_authority"))
            details["can_live_execute"] = bool(payload.get("can_live_execute"))
            details["authority_state"] = payload.get("live_authority_state")
        except Exception as exc:
            return StageResult(FAIL, _failure_reason(exc), {"exception_type": exc.__class__.__name__})

        if (
            details["execution_allowed"] is False
            and details["live_trading_blocked"] is True
            and details["execution_boundary_active"] is True
            and details["execution_authority"] is False
            and details["can_live_execute"] is False
        ):
            return StageResult(PASS, details=details)

        return StageResult(FAIL, "execution_firewall_not_blocked", details)


def validate_live_broker(
    broker: str,
    *,
    mode: str = "live",
    env: Mapping[str, Any] | None = None,
    credential_diagnostics_fn: CredentialDiagnosticsFn = diagnose_broker_credentials,
    initialize_broker_fn: InitializeBrokerFn = initialize_broker,
    authority_fn: AuthorityFn = evaluate_live_execution_authority,
) -> dict[str, Any]:
    return LiveBrokerValidationEngine(
        broker,
        mode=mode,
        env=env,
        credential_diagnostics_fn=credential_diagnostics_fn,
        initialize_broker_fn=initialize_broker_fn,
        authority_fn=authority_fn,
    ).validate()


def live_broker_validation_json(report: Mapping[str, Any], *, indent: int = 2) -> str:
    return json.dumps(_json_safe(report), indent=indent, sort_keys=True)


def write_live_broker_validation_report(
    report: Mapping[str, Any],
    path: str | Path,
    *,
    indent: int = 2,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(live_broker_validation_json(report, indent=indent), encoding="utf-8")


def _validate_oanda_account(adapter: Any) -> dict[str, Any]:
    summary = _call_first(adapter, (("get_account_summary", ()),))
    ok, reason = _read_success(summary)
    if not ok:
        return {"valid": False, "reason": reason}

    plain = _payload_data(summary)
    account = plain.get("account") if isinstance(plain, Mapping) else {}
    source = account if isinstance(account, Mapping) else plain if isinstance(plain, Mapping) else {}
    balance_present = _has_any(source, ("balance",))
    nav_present = _has_any(source, ("NAV", "nav"))
    margin_available_present = _has_any(source, ("marginAvailable", "margin_available"))
    valid = balance_present and nav_present and margin_available_present
    return {
        "valid": valid,
        "reason": "" if valid else "oanda_account_summary_incomplete",
        "account_summary": True,
        "balance_present": balance_present,
        "nav_present": nav_present,
        "margin_available_present": margin_available_present,
    }


def _validate_coinbase_account(adapter: Any) -> dict[str, Any]:
    accounts = _call_first(adapter, (("get_accounts", ()), ("list_accounts", ()), ("get_account", ()),))
    ok, reason = _read_success(accounts)
    if not ok:
        return {"valid": False, "reason": reason}

    balances = _call_first(
        adapter,
        (
            ("get_balances", ()),
            ("get_balance", ()),
            ("get_account_balance", ()),
            ("get_account", ()),
        ),
    )
    ok, reason = _read_success(balances)
    if not ok:
        return {"valid": False, "reason": reason}

    portfolio = _call_first(
        adapter,
        (
            ("get_portfolios", ()),
            ("get_portfolio", ()),
            ("get_portfolio_information", ()),
            ("get_account", ()),
        ),
    )
    ok, reason = _read_success(portfolio)
    if not ok:
        return {"valid": False, "reason": reason}

    accounts_present = _value_present(accounts)
    balances_present = _value_present(balances)
    portfolio_present = _value_present(portfolio)
    valid = accounts_present and balances_present and portfolio_present
    return {
        "valid": valid,
        "reason": "" if valid else "coinbase_account_payload_incomplete",
        "accounts_present": accounts_present,
        "balances_present": balances_present,
        "portfolio_present": portfolio_present,
    }


def _validate_oanda_market_data(adapter: Any) -> dict[str, Any]:
    evidence = collect_market_data_evidence(adapter, broker="oanda", instrument="EUR_USD")
    ok = evidence.get("success") is True
    return {
        "valid": ok,
        "reason": "" if ok else str(evidence.get("reason") or "market_data_missing"),
        "instrument": "EUR_USD",
        "quote_present": ok,
        "source": evidence.get("source", ""),
        "timestamp": evidence.get("timestamp", ""),
        "evidence": evidence,
    }


def _validate_coinbase_market_data(adapter: Any) -> dict[str, Any]:
    evidence = collect_market_data_evidence(adapter, broker="coinbase", instrument="BTC-USD")
    ok = evidence.get("success") is True
    return {
        "valid": ok,
        "reason": "" if ok else str(evidence.get("reason") or "market_data_missing"),
        "instrument": "BTC-USD",
        "quote_present": ok,
        "source": evidence.get("source", ""),
        "timestamp": evidence.get("timestamp", ""),
        "evidence": evidence,
    }


def _call_first(adapter: Any, candidates: tuple[tuple[str, tuple[Any, ...]], ...]) -> Any:
    for method_name, args in candidates:
        method = getattr(adapter, method_name, None)
        if callable(method):
            try:
                return method(*args)
            except TypeError:
                if args:
                    return method()
                raise
    return _NOT_FOUND


def _read_success(value: Any) -> tuple[bool, str]:
    if value is _NOT_FOUND:
        return False, "read_only_method_unavailable"
    if value is None:
        return False, "empty_broker_response"
    if isinstance(value, bool):
        return (value, "" if value else "broker_returned_false")
    if isinstance(value, Mapping):
        if value.get("ok") is False:
            return False, str(value.get("error") or value.get("reason") or "broker_read_failed")
        status = value.get("status")
        if isinstance(status, int) and not (200 <= status < 300):
            return False, f"http_{status}"
        if str(value.get("error") or "").strip():
            return False, str(value.get("error"))
        if str(value.get("status") or "").upper() in {"FAIL", "FAILED", "FAIL_CLOSED", "ERROR"}:
            return False, str(value.get("reason") or value.get("status"))
    return True, ""


def _payload_data(value: Any) -> Any:
    if isinstance(value, Mapping) and "data" in value:
        return value.get("data")
    return value


def _has_any(source: Mapping[str, Any], keys: tuple[str, ...]) -> bool:
    return any(_value_present(source.get(key)) for key in keys)


def _value_present(value: Any) -> bool:
    if value is _NOT_FOUND or value is None:
        return False
    if isinstance(value, str):
        return value.strip().upper() not in {"", "NONE", "NULL", "DATA UNAVAILABLE", "NOT_AVAILABLE"}
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    return True


def _collect_blocker(blockers: list[str], stage: str, result: StageResult) -> None:
    if result.status == FAIL:
        blockers.append(f"{stage}:{result.reason or 'failed'}")


def _elapsed_ms(clock: ClockFn, started: float) -> int:
    return max(0, int(round((clock() - started) * 1000)))


def _sum_latency(latency: Mapping[str, int | None]) -> int:
    return int(sum(value for value in latency.values() if isinstance(value, int)))


def _failure_reason(exc: BaseException) -> str:
    if isinstance(exc, TimeoutError):
        return "TIMEOUT"
    reason = classify_auth_failure(exc)
    if reason and reason != "UNKNOWN_ERROR":
        return reason
    return str(exc) or exc.__class__.__name__


def _normalize_broker(broker: str) -> str:
    return str(broker or "").strip().lower()


def _redact_stage(result: StageResult) -> StageResult:
    details = dict(result.details or {})
    details.pop("adapter", None)
    return StageResult(
        status=result.status,
        reason=result.reason,
        details=details,
        latency_ms=result.latency_ms,
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class _NotFound:
    pass


_NOT_FOUND = _NotFound()


__all__ = [
    "GREEN",
    "PASS",
    "PAYLOAD_VERSION",
    "RED",
    "FAIL",
    "LiveBrokerValidationEngine",
    "LiveBrokerValidationError",
    "live_broker_validation_json",
    "validate_live_broker",
    "write_live_broker_validation_report",
]

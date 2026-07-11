from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.brokers.broker_bootstrap import initialize_broker
from backend.app.brokers.execution_boundary import validate_execution_boundary
from backend.runtime.broker_market_data_evidence import collect_market_data_evidence_for_symbols
from backend.runtime.broker_operational_remediation import collect_read_only_authentication_evidence
from backend.runtime.live_broker_validation import validate_live_broker
from backend.runtime.live_execution_authority import evaluate_live_execution_authority


PASS = "PASS"
FAIL = "FAIL"
GREEN = "GREEN"
AMBER = "AMBER"
RED = "RED"
PAYLOAD_VERSION = "css.phase156b.live_connectivity_certification.v1"


Phase156AFn = Callable[..., Mapping[str, Any]]
InitializeBrokerFn = Callable[[str, str], Any]
AuthorityFn = Callable[[Mapping[str, Any]], Any]
ClockFn = Callable[[], float]


@dataclass(frozen=True)
class ConnectivityLatencyThresholds:
    stage_green_ms: int = 250
    stage_amber_ms: int = 1000
    overall_green_ms: int = 750
    overall_amber_ms: int = 2500
    degraded_stage_amber_ms: int = 5000
    degraded_overall_amber_ms: int = 12000
    score_green: float = 90.0
    score_amber: float = 70.0


@dataclass(frozen=True)
class ConnectivityStage:
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


class LiveConnectivityCertificationEngine:
    """
    Advisory operational connectivity certifier for configured live brokers.

    It certifies read-only connectivity only. It never certifies execution
    authority, never arms a broker, and always returns execution_allowed=False.
    """

    def __init__(
        self,
        broker: str,
        *,
        mode: str = "live",
        phase156a_fn: Phase156AFn = validate_live_broker,
        initialize_broker_fn: InitializeBrokerFn = initialize_broker,
        authority_fn: AuthorityFn = evaluate_live_execution_authority,
        thresholds: ConnectivityLatencyThresholds | None = None,
        clock: ClockFn = time.perf_counter,
    ) -> None:
        self.broker = str(broker or "").strip().lower()
        self.mode = str(mode or "live").strip().lower()
        self.phase156a_fn = phase156a_fn
        self.initialize_broker_fn = initialize_broker_fn
        self.authority_fn = authority_fn
        self.thresholds = thresholds or ConnectivityLatencyThresholds()
        self.clock = clock

    def certify(self) -> dict[str, Any]:
        started = self.clock()
        phase156a = self._phase156a()
        if str(phase156a.get("overall", "")).upper() != GREEN:
            return self._fail_closed(
                started,
                phase156a=phase156a,
                blockers=["phase156a_not_green"],
                recommendations=["Resolve Phase 156A blockers before controlled live connectivity certification."],
            )

        try:
            adapter = self.initialize_broker_fn(self.broker, self.mode)
        except Exception as exc:
            return self._fail_closed(
                started,
                phase156a=phase156a,
                blockers=[f"bootstrap:{_failure_reason(exc)}"],
                recommendations=["Restore broker bootstrap before connectivity certification."],
            )

        if adapter is None:
            return self._fail_closed(
                started,
                phase156a=phase156a,
                blockers=["bootstrap:broker_adapter_unavailable"],
                recommendations=["Verify the selected broker adapter is registered and loadable."],
            )

        authentication = self._authenticate(adapter)
        account = self._account(adapter) if authentication.status == PASS else ConnectivityStage(FAIL, "authentication_validation_failed")
        market_data = self._market_data(adapter) if authentication.status == PASS else ConnectivityStage(FAIL, "authentication_validation_failed")
        firewall = self._firewall()

        stages = {
            "authentication": authentication,
            "account": account,
            "market_data": market_data,
            "execution_firewall": firewall,
        }
        blockers = [
            f"{name}:{stage.reason or 'failed'}"
            for name, stage in stages.items()
            if stage.status == FAIL
        ]
        latency = {
            "authentication_ms": authentication.latency_ms,
            "account_ms": account.latency_ms,
            "market_data_ms": market_data.latency_ms,
            "overall_ms": _elapsed_ms(self.clock, started),
            "active_validation_ms": _sum_stage_latency(authentication, account, market_data),
        }
        
        # Compute functional score and functional_ok status for relaxed operational latency checks
        func_score = 0.0
        func_score += 20.0 if str(phase156a.get("credentials", PASS)).upper() == PASS and str(phase156a.get("overall", "")).upper() == GREEN else 0.0
        func_score += 20.0 if authentication.status == PASS else 0.0
        func_score += 20.0 if account.status == PASS else 0.0
        func_score += 20.0 if market_data.status == PASS else 0.0
        func_score += 10.0 if firewall.status == PASS else 0.0

        functional_ok = (
            not blockers
            and str(phase156a.get("overall", "")).upper() == GREEN
            and authentication.status == PASS
            and account.status == PASS
            and market_data.status == PASS
            and firewall.status == PASS
            and func_score >= 85.0
        )

        latency_status = self._latency_status(latency, functional_ok=functional_ok)
        score = self._connectivity_score(
            phase156a=phase156a,
            authentication=authentication,
            account=account,
            market_data=market_data,
            firewall=firewall,
            latency_status=latency_status,
        )
        certification = self._certification(blockers, latency_status, score)

        recommendations = self._recommendations(blockers, latency_status, score)
        report = {
            "payload_version": PAYLOAD_VERSION,
            "broker": self.broker.upper() if self.broker else "NONE",
            "mode": self.mode,
            "phase156a": str(phase156a.get("overall", RED)).upper(),
            "authentication": authentication.status,
            "account": account.status,
            "market_data": market_data.status,
            "latency": latency,
            "latency_status": latency_status,
            "connectivity_score": score,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "certification": certification,
            "advisory_only": True,
            "blocker_reasons": blockers,
            "recommendations": recommendations,
            "stage_results": {name: stage.as_dict() for name, stage in stages.items()},
            "phase156a_report": _phase156a_summary(phase156a),
        }
        return _json_safe(report)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.certify(), indent=indent, sort_keys=True)

    def write_json_report(self, path: str | Path, *, indent: int = 2) -> dict[str, Any]:
        report = self.certify()
        write_live_connectivity_certification_report(report, path, indent=indent)
        return report

    def _phase156a(self) -> Mapping[str, Any]:
        try:
            return self.phase156a_fn(self.broker, mode=self.mode)
        except Exception as exc:
            return {
                "overall": RED,
                "blocker_reasons": [f"phase156a_exception:{_failure_reason(exc)}"],
                "advisory_only": True,
                "execution_allowed": False,
                "live_trading_blocked": True,
            }

    def _authenticate(self, adapter: Any) -> ConnectivityStage:
        try:
            evidence = collect_read_only_authentication_evidence(adapter, broker=self.broker, clock=self.clock)
            ok = evidence.get("success") is True
            reason = str(evidence.get("reason", ""))
        except Exception as exc:
            started = self.clock()
            return ConnectivityStage(FAIL, _failure_reason(exc), {"exception_type": exc.__class__.__name__}, _elapsed_ms(self.clock, started))

        latency_ms = evidence.get("latency_ms")
        if not isinstance(latency_ms, int):
            latency_ms = _elapsed_ms(self.clock, started)
        return ConnectivityStage(
            PASS if ok else FAIL,
            "" if ok else reason,
            {"method": "read_only_authentication_probe", "evidence": evidence, "source": evidence.get("source", "")},
            latency_ms,
        )

    def _account(self, adapter: Any) -> ConnectivityStage:
        started = self.clock()
        try:
            details = _oanda_account(adapter) if self.broker == "oanda" else _coinbase_account(adapter)
        except Exception as exc:
            return ConnectivityStage(FAIL, _failure_reason(exc), {"exception_type": exc.__class__.__name__}, _elapsed_ms(self.clock, started))

        return ConnectivityStage(
            PASS if details.pop("valid", False) else FAIL,
            str(details.pop("reason", "")),
            details,
            _elapsed_ms(self.clock, started),
        )

    def _market_data(self, adapter: Any) -> ConnectivityStage:
        started = self.clock()
        try:
            details = _oanda_market_data(adapter) if self.broker == "oanda" else _coinbase_market_data(adapter)
        except Exception as exc:
            return ConnectivityStage(FAIL, _failure_reason(exc), {"exception_type": exc.__class__.__name__}, _elapsed_ms(self.clock, started))

        return ConnectivityStage(
            PASS if details.pop("valid", False) else FAIL,
            str(details.pop("reason", "")),
            details,
            _elapsed_ms(self.clock, started),
        )

    def _firewall(self) -> ConnectivityStage:
        details: dict[str, Any] = {
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        }
        try:
            boundary = validate_execution_boundary(
                selected_mode="live",
                capital_source_label="SIMULATED",
            )
            details["execution_boundary_active"] = boundary.allowed is False
            details["execution_boundary_reason"] = boundary.reason
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
            return ConnectivityStage(FAIL, _failure_reason(exc), {"exception_type": exc.__class__.__name__})

        if (
            details["execution_allowed"] is False
            and details["live_trading_blocked"] is True
            and details["broker_execution_armed"] is False
            and details["execution_boundary_active"] is True
            and details["execution_authority"] is False
            and details["can_live_execute"] is False
        ):
            return ConnectivityStage(PASS, details=details)
        return ConnectivityStage(FAIL, "execution_firewall_not_blocked", details)

    def _latency_status(self, latency: Mapping[str, int | None], *, functional_ok: bool = False) -> str:
        stage_values = [
            _int
            for _int in (
                latency.get("authentication_ms"),
                latency.get("account_ms"),
                latency.get("market_data_ms"),
            )
            if isinstance(_int, int)
        ]
        if not stage_values:
            return RED
        
        overall_val = int(latency.get("active_validation_ms") or latency.get("overall_ms") or 0)

        # 1. Strict GREEN checks
        is_green = (
            overall_val <= self.thresholds.overall_green_ms
            and all(value <= self.thresholds.stage_green_ms for value in stage_values)
        )
        if is_green:
            return GREEN

        # 2. Check if functional_ok allows relaxed operational latency staging
        if functional_ok:
            is_amber = (
                overall_val <= self.thresholds.degraded_overall_amber_ms
                and all(value <= self.thresholds.degraded_stage_amber_ms for value in stage_values)
            )
            if is_amber:
                return AMBER
            return RED
        else:
            # Standard thresholds checking
            is_amber = (
                overall_val <= self.thresholds.overall_amber_ms
                and all(value <= self.thresholds.stage_amber_ms for value in stage_values)
            )
            if is_amber:
                return AMBER
            return RED

    def _connectivity_score(
        self,
        *,
        phase156a: Mapping[str, Any],
        authentication: ConnectivityStage,
        account: ConnectivityStage,
        market_data: ConnectivityStage,
        firewall: ConnectivityStage,
        latency_status: str,
    ) -> float:
        score = 0.0
        score += 20.0 if str(phase156a.get("credentials", PASS)).upper() == PASS and str(phase156a.get("overall", "")).upper() == GREEN else 0.0
        score += 20.0 if authentication.status == PASS else 0.0
        score += 20.0 if account.status == PASS else 0.0
        score += 20.0 if market_data.status == PASS else 0.0
        score += 10.0 if firewall.status == PASS else 0.0
        score += {GREEN: 10.0, AMBER: 5.0, RED: 0.0}.get(latency_status, 0.0)
        return round(score, 2)

    def _certification(self, blockers: list[str], latency_status: str, score: float) -> str:
        if blockers or latency_status == RED or score < self.thresholds.score_amber:
            return RED
        if latency_status == AMBER or score < self.thresholds.score_green:
            return AMBER
        return GREEN

    def _recommendations(self, blockers: list[str], latency_status: str, score: float) -> list[str]:
        recommendations: list[str] = []
        if blockers:
            recommendations.append("Resolve blocker reasons before repeating controlled live connectivity certification.")
        if latency_status == AMBER:
            recommendations.append("Broker is operational but latency is elevated; continue read-only monitoring before live validation.")
        elif latency_status == RED:
            recommendations.append("Broker latency exceeds certification thresholds; do not proceed until latency normalizes.")
        if score < self.thresholds.score_green:
            recommendations.append("Connectivity score is below GREEN threshold; review account, market data, and firewall evidence.")
        if not recommendations:
            recommendations.append("Operational connectivity is certified for advisory review only; live execution remains unauthorized.")
        return recommendations

    def _fail_closed(
        self,
        started: float,
        *,
        phase156a: Mapping[str, Any],
        blockers: list[str],
        recommendations: list[str],
    ) -> dict[str, Any]:
        latency = {
            "authentication_ms": None,
            "account_ms": None,
            "market_data_ms": None,
            "overall_ms": _elapsed_ms(self.clock, started),
        }
        report = {
            "payload_version": PAYLOAD_VERSION,
            "broker": self.broker.upper() if self.broker else "NONE",
            "mode": self.mode,
            "phase156a": str(phase156a.get("overall", RED)).upper(),
            "authentication": FAIL,
            "account": FAIL,
            "market_data": FAIL,
            "latency": latency,
            "latency_status": RED,
            "connectivity_score": 0.0,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "certification": RED,
            "advisory_only": True,
            "blocker_reasons": list(blockers) + list(phase156a.get("blocker_reasons", [])),
            "recommendations": recommendations,
            "stage_results": {},
            "phase156a_report": _phase156a_summary(phase156a),
        }
        return _json_safe(report)


def certify_live_connectivity(
    broker: str,
    *,
    mode: str = "live",
    phase156a_fn: Phase156AFn = validate_live_broker,
    initialize_broker_fn: InitializeBrokerFn = initialize_broker,
    authority_fn: AuthorityFn = evaluate_live_execution_authority,
    thresholds: ConnectivityLatencyThresholds | None = None,
) -> dict[str, Any]:
    return LiveConnectivityCertificationEngine(
        broker,
        mode=mode,
        phase156a_fn=phase156a_fn,
        initialize_broker_fn=initialize_broker_fn,
        authority_fn=authority_fn,
        thresholds=thresholds,
    ).certify()


def live_connectivity_certification_json(report: Mapping[str, Any], *, indent: int = 2) -> str:
    return json.dumps(_json_safe(report), indent=indent, sort_keys=True)


def write_live_connectivity_certification_report(
    report: Mapping[str, Any],
    path: str | Path,
    *,
    indent: int = 2,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(live_connectivity_certification_json(report, indent=indent), encoding="utf-8")


def _oanda_account(adapter: Any) -> dict[str, Any]:
    summary = _call_first(adapter, (("get_account_summary", ()),))
    ok, reason = _read_success(summary)
    if not ok:
        return {"valid": False, "reason": reason}
    source = _account_source(summary)
    fields = {
        "account_id": _first_present(source, ("id", "account_id", "accountID")),
        "alias": _first_present(source, ("alias", "account_alias")),
        "currency": _first_present(source, ("currency", "homeCurrency")),
        "balance": _first_present(source, ("balance",)),
        "nav": _first_present(source, ("NAV", "nav")),
        "margin_available": _first_present(source, ("marginAvailable", "margin_available")),
    }
    missing = [key for key, value in fields.items() if not _value_present(value)]
    return {
        "valid": not missing,
        "reason": "" if not missing else "oanda_account_information_incomplete",
        "missing_fields": missing,
        "account": _presence_map(fields),
    }


def _coinbase_account(adapter: Any) -> dict[str, Any]:
    portfolio_candidates = (
        ("get_portfolios", ()),
        ("get_portfolio", ()),
        ("get_portfolio_information", ()),
        ("get_account", ()),
        ("get_account_balance", ()),
    )
    wallet_candidates = (("get_accounts", ()), ("list_accounts", ()), ("get_wallets", ()),)
    portfolio, wallets = _parallel_call_first(adapter, portfolio_candidates, wallet_candidates)
    ok, reason = _read_success(portfolio)
    if not ok:
        return {"valid": False, "reason": reason}
    ok, reason = _read_success(wallets)
    if not ok:
        return {"valid": False, "reason": reason}
    balances = wallets if _coinbase_wallets_include_balances(wallets) else _call_first(adapter, (("get_balances", ()), ("get_balance", ()), ("get_account_balance", ()), ("get_account", ()),))
    ok, reason = _read_success(balances)
    if not ok:
        return {"valid": False, "reason": reason}
    portfolio_value = _first_portfolio_value(portfolio)
    if not _value_present(portfolio_value):
        portfolio_value = _first_portfolio_value(balances)
    if not _value_present(portfolio_value):
        portfolio_value = _first_portfolio_value(wallets)
    missing = []
    if not _value_present(portfolio):
        missing.append("portfolio")
    if not _value_present(wallets):
        missing.append("wallet_list")
    if not _value_present(balances):
        missing.append("asset_balances")
    if not _value_present(portfolio_value):
        missing.append("portfolio_value")
    return {
        "valid": not missing,
        "reason": "" if not missing else "coinbase_account_information_incomplete",
        "missing_fields": missing,
        "portfolio_present": _value_present(portfolio),
        "wallet_list_present": _value_present(wallets),
        "asset_balances_present": _value_present(balances),
        "portfolio_value_present": _value_present(portfolio_value),
    }


def _coinbase_wallets_include_balances(wallets: Any) -> bool:
    payload = _payload_data(wallets)
    accounts = payload.get("accounts") if isinstance(payload, Mapping) else payload
    if not isinstance(accounts, list):
        return False
    return any(
        isinstance(account, Mapping)
        and any(_value_present(account.get(key)) for key in ("available_balance", "balance", "hold", "total_balance"))
        for account in accounts
    )


def _oanda_market_data(adapter: Any) -> dict[str, Any]:
    return collect_market_data_evidence_for_symbols(adapter, broker="oanda", instruments=("EUR_USD", "USD_JPY"))


def _coinbase_market_data(adapter: Any) -> dict[str, Any]:
    return collect_market_data_evidence_for_symbols(adapter, broker="coinbase", instruments=("BTC-USD", "ETH-USD"))


def _multi_quote(adapter: Any, symbols: tuple[str, ...]) -> dict[str, Any]:
    quotes: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    timestamp = ""
    for symbol in symbols:
        quote = _call_first(
            adapter,
            (
                ("get_quote", (symbol,)),
                ("get_ticker", (symbol,)),
                ("get_pricing", (symbol,)),
                ("get_product", (symbol,)),
                ("get_market_data", (symbol,)),
            ),
        )
        ok, reason = _read_success(quote)
        if not ok:
            missing.append(symbol)
            quotes[symbol] = {"status": FAIL, "reason": reason}
            continue
        payload = _payload_data(quote)
        quotes[symbol] = {"status": PASS}
        quote_timestamp = _quote_timestamp(payload)
        if quote_timestamp and not timestamp:
            timestamp = quote_timestamp
    return {
        "valid": not missing,
        "reason": "" if not missing else "market_data_missing",
        "symbols": list(symbols),
        "missing_symbols": missing,
        "quotes": quotes,
        "timestamp": timestamp or _iso_timestamp(),
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


def _parallel_call_first(
    adapter: Any,
    left: tuple[tuple[str, tuple[Any, ...]], ...],
    right: tuple[tuple[str, tuple[Any, ...]], ...],
) -> tuple[Any, Any]:
    with ThreadPoolExecutor(max_workers=2) as executor:
        left_future = executor.submit(_call_first, adapter, left)
        right_future = executor.submit(_call_first, adapter, right)
        return left_future.result(), right_future.result()


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


def _account_source(value: Any) -> Mapping[str, Any]:
    payload = _payload_data(value)
    if isinstance(payload, Mapping) and isinstance(payload.get("account"), Mapping):
        return payload["account"]
    return payload if isinstance(payload, Mapping) else {}


def _payload_data(value: Any) -> Any:
    if isinstance(value, Mapping) and "data" in value:
        return value.get("data")
    return value


def _first_present(source: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = source.get(key)
        if _value_present(value):
            return value
    return None


def _first_portfolio_value(portfolio: Any) -> Any:
    payload = _payload_data(portfolio)
    if isinstance(payload, Mapping):
        direct = _first_present(payload, ("portfolio_value", "total_balance", "total_value", "value", "balance", "equity", "available_balance"))
        if _value_present(direct):
            return direct
        portfolios = payload.get("portfolios") or payload.get("accounts") or payload.get("data")
    else:
        portfolios = payload
    if isinstance(portfolios, list) and portfolios:
        first = portfolios[0]
        if isinstance(first, Mapping):
            return _first_present(first, ("portfolio_value", "total_balance", "total_value", "value", "balance", "available_balance"))
    return None


def _presence_map(fields: Mapping[str, Any]) -> dict[str, bool]:
    return {key: _value_present(value) for key, value in fields.items()}


def _quote_timestamp(payload: Any) -> str:
    if isinstance(payload, Mapping):
        for key in ("timestamp", "time", "trade_time", "price_time"):
            value = payload.get(key)
            if _value_present(value):
                return str(value)
    return ""


def _iso_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def _elapsed_ms(clock: ClockFn, started: float) -> int:
    return max(0, int(round((clock() - started) * 1000)))


def _sum_stage_latency(*stages: ConnectivityStage) -> int:
    return int(sum(stage.latency_ms for stage in stages if isinstance(stage.latency_ms, int)))


def _failure_reason(exc: BaseException) -> str:
    if isinstance(exc, TimeoutError):
        return "TIMEOUT"
    text = f"{exc.__class__.__name__} {exc}".lower()
    if "timeout" in text or "timed out" in text:
        return "TIMEOUT"
    if "unavailable" in text or "503" in text:
        return "BROKER_UNAVAILABLE"
    if "auth" in text or "unauthorized" in text or "401" in text:
        return "AUTH_FAILED"
    return str(exc) or exc.__class__.__name__


def _phase156a_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "overall": str(report.get("overall", RED)).upper(),
        "credentials": report.get("credentials"),
        "bootstrap": report.get("bootstrap"),
        "authentication": report.get("authentication"),
        "account": report.get("account"),
        "market_data": report.get("market_data"),
        "execution_firewall": report.get("execution_firewall"),
        "execution_allowed": False,
        "live_trading_blocked": True,
        "advisory_only": True,
        "blocker_reasons": list(report.get("blocker_reasons", [])),
    }


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
    "AMBER",
    "GREEN",
    "PASS",
    "PAYLOAD_VERSION",
    "RED",
    "FAIL",
    "ConnectivityLatencyThresholds",
    "LiveConnectivityCertificationEngine",
    "certify_live_connectivity",
    "live_connectivity_certification_json",
    "write_live_connectivity_certification_report",
]

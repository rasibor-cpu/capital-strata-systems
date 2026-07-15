from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from backend.config.order_limit_config import DEFAULT_ORDER_LIMIT_CONFIG
from backend.runtime.canonical_broker_runtime_state import (
    OVERALL_AMBER,
    OVERALL_GREEN,
    OVERALL_RED,
    STATUS_BLOCKED,
    STATUS_FAIL,
    STATUS_NOT_TESTED,
    STATUS_PASS,
    STATUS_UNAVAILABLE,
    STATUS_UNKNOWN,
    CanonicalBrokerRuntimeState,
    canonical_overall,
    canonical_status,
    finite_float,
    finite_int,
)
from backend.runtime.canonical_account_snapshot import build_canonical_account_snapshot
from backend.runtime.canonical_broker_state_registry import classify_coinbase_environment
from backend.runtime.canonical_broker_state_validator import contradiction_reasons, fail_closed_state


SOURCE_PRECEDENCE = (
    "current_live_broker_response",
    "canonical_authentication_account_trace",
    "broker_adapter_state",
    "runtime_registry_state",
    "fresh_marked_cache",
    "historical_diagnostics_only",
)


def build_canonical_broker_runtime_state(
    *,
    broker: str = "NONE",
    mode: str = "paper",
    runtime_payload: Mapping[str, Any] | None = None,
    auth_trace: Mapping[str, Any] | None = None,
    adapter_status: Mapping[str, Any] | None = None,
    certification: Mapping[str, Any] | None = None,
    margin_snapshot: Mapping[str, Any] | None = None,
    env: Mapping[str, Any] | None = None,
    source_modules: tuple[str, ...] | list[str] = (),
    timestamp: str | None = None,
) -> CanonicalBrokerRuntimeState:
    runtime = _mapping(runtime_payload)
    trace = _mapping(auth_trace)
    adapter = _mapping(adapter_status)
    cert = _mapping(certification)
    margin = _mapping(margin_snapshot)
    broker_name = str(broker or runtime.get("broker") or runtime.get("selected_broker") or trace.get("broker") or cert.get("broker") or "NONE").upper()
    mode_key = str(mode or runtime.get("broker_mode") or runtime.get("mode") or trace.get("mode") or cert.get("mode") or "paper").lower()
    environment = _environment_evidence(broker_name, mode_key, env, runtime, trace, margin)

    pre_validation_reasons = _pre_validation_reasons(runtime, trace, cert)
    credential_status = _credential_status(runtime, trace, adapter, cert)
    authentication_status = _authentication_status(trace, runtime, adapter, cert)
    transport_status = _transport_status(runtime, adapter, trace, cert)
    connection_status = _connection_status(transport_status, authentication_status)
    account_status = _read_status("account", runtime, trace, adapter, cert)
    balance_status = _read_status("balance", runtime, trace, adapter, cert)
    buying_power_status = _buying_power_status(runtime, adapter, margin)
    margin_status = _margin_status(runtime, adapter, margin)
    if mode_key == "live" and balance_status != STATUS_PASS:
        buying_power_status = STATUS_UNAVAILABLE
        margin_status = STATUS_UNAVAILABLE
    market_data_status = _read_status("market_data", runtime, trace, adapter, cert)
    product_status = _read_status("product", runtime, trace, adapter, cert)
    readiness_score = _readiness_score(runtime, adapter, cert)
    overall = _overall_status(
        credential_status,
        authentication_status,
        account_status,
        balance_status,
        market_data_status,
        product_status,
        environment,
        cert,
        runtime,
    )
    failure_reason = _failure_reason(runtime, trace, adapter, cert, environment)
    warnings = _warning_reasons(runtime, trace, adapter, cert, environment)
    account_snapshot = build_canonical_account_snapshot(
        broker=broker_name,
        mode=mode_key,
        runtime_payload={
            **runtime,
            "account_status": account_status,
            "balance_status": balance_status,
            "buying_power_status": buying_power_status,
            "margin_status": margin_status,
            "market_data_status": market_data_status,
            "status_provenance": _status_provenance(
                mode=mode_key,
                runtime=runtime,
                trace=trace,
                adapter=adapter,
                cert=cert,
                margin=margin,
                credential_status=credential_status,
                transport_status=transport_status,
                authentication_status=authentication_status,
                connection_status=connection_status,
                account_status=account_status,
                balance_status=balance_status,
                buying_power_status=buying_power_status,
                margin_status=margin_status,
                market_data_status=market_data_status,
                product_status=product_status,
            ),
        },
        adapter_status=adapter,
        certification=cert,
        margin_snapshot=margin,
        timestamp=timestamp or str(runtime.get("timestamp") or runtime.get("generated_at") or _utc_iso()),
    )
    status_provenance = _status_provenance(
        mode=mode_key,
        runtime=runtime,
        trace=trace,
        adapter=adapter,
        cert=cert,
        margin=margin,
        credential_status=credential_status,
        transport_status=transport_status,
        authentication_status=authentication_status,
        connection_status=connection_status,
        account_status=account_status,
        balance_status=balance_status,
        buying_power_status=buying_power_status,
        margin_status=margin_status,
        market_data_status=market_data_status,
        product_status=product_status,
    )
    state = CanonicalBrokerRuntimeState(
        broker=broker_name,
        mode=mode_key,
        credential_status=credential_status,
        transport_status=transport_status,
        authentication_status=authentication_status,
        connection_status=connection_status,
        account_status=account_status,
        balance_status=balance_status,
        buying_power_status=buying_power_status,
        margin_status=margin_status,
        market_data_status=market_data_status,
        product_status=product_status,
        order_submission_status=_order_submission_status(runtime, adapter, cert),
        execution_scope=str(runtime.get("execution_scope") or adapter.get("execution_scope") or cert.get("execution_scope") or "READ_ONLY"),
        execution_allowed=False,
        live_trading_blocked=True,
        broker_execution_armed=False,
        operator_intent="LIVE" if _truthy(runtime.get("operator_requested_live")) else "NONE",
        pilot_state=str(runtime.get("live_micro_pilot_state") or runtime.get("pilot_state") or "DISARMED"),
        capital_governor=str(runtime.get("capital_governor") or f"CANONICAL_ORDER_LIMIT_CONFIG:{DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_total_cad}CAD"),
        readiness_state=str(runtime.get("readiness_state") or cert.get("certification") or overall),
        readiness_score=readiness_score,
        overall_status=overall,
        last_successful_auth=str(runtime.get("last_successful_auth") or runtime.get("last_successful_sync") or adapter.get("last_successful_sync") or ""),
        last_successful_account_read=str(runtime.get("last_successful_account_read") or adapter.get("last_successful_sync") or ""),
        last_successful_balance_read=str(runtime.get("last_successful_balance_read") or adapter.get("last_successful_sync") or ""),
        last_successful_market_data=str(runtime.get("last_successful_market_data") or adapter.get("last_successful_sync") or ""),
        latency_ms=_latency(runtime, trace, adapter, cert),
        http_status=_http_status(runtime, trace, adapter, cert),
        error_code=str(trace.get("coinbase_error_code") or adapter.get("coinbase_error_code") or runtime.get("error_code") or cert.get("error_code") or ""),
        failure_reason=failure_reason,
        warning_reasons=tuple(warnings),
        environment_evidence=environment,
        account_evidence=_account_evidence(
            runtime=runtime,
            trace=trace,
            adapter=adapter,
            cert=cert,
            transport_status=transport_status,
            authentication_status=authentication_status,
            connection_status=connection_status,
            account_status=account_status,
            balance_status=balance_status,
            buying_power_status=buying_power_status,
            margin_status=margin_status,
            market_data_status=market_data_status,
            product_status=product_status,
        ),
        account_snapshot=account_snapshot.to_dict(),
        status_provenance=status_provenance,
        source_modules=tuple(source_modules) or _source_modules(runtime, trace, adapter, cert, margin),
        timestamp=timestamp or str(runtime.get("timestamp") or runtime.get("generated_at") or _utc_iso()),
    )
    reasons = list(dict.fromkeys(pre_validation_reasons + list(account_snapshot.contradiction_reasons) + contradiction_reasons(state)))
    if reasons:
        return fail_closed_state(state, reasons)
    return state


def canonical_state_from_payload(payload: Mapping[str, Any] | None = None, **overrides: Any) -> CanonicalBrokerRuntimeState:
    source = _mapping(payload)
    return build_canonical_broker_runtime_state(
        broker=str(overrides.pop("broker", source.get("broker", source.get("selected_broker", "NONE")))),
        mode=str(overrides.pop("mode", source.get("mode", source.get("broker_mode", "paper")))),
        runtime_payload={**source, **overrides},
        auth_trace=_mapping(source.get("coinbase_authentication_trace") or source.get("authentication_trace")),
        adapter_status=_mapping(source.get("adapter_status") or source.get("coinbase_live_adapter_status")),
        certification=_mapping(source.get("runtime_certification_snapshot") or source.get("certification_snapshot")),
        margin_snapshot=_mapping(source.get("margin_snapshot")),
        env=_mapping(source.get("env")),
    )


def _credential_status(*payloads: Mapping[str, Any]) -> str:
    for payload in payloads:
        diagnostics = _mapping(payload.get("credential_validation") or payload.get("broker_credential_diagnostics") or payload.get("credential_diagnostics"))
        if diagnostics:
            status = diagnostics.get("status") or diagnostics.get("credential_status")
            if status:
                return canonical_status(status)
            if diagnostics.get("credentials_present") is True:
                return STATUS_PASS
            if diagnostics.get("credentials_present") is False:
                return STATUS_FAIL
        if payload.get("credential_status"):
            return canonical_status(payload.get("credential_status"))
            if payload.get("credentials") in {"PASS", "PRESENT", "READY"}:
                return STATUS_PASS
            if payload.get("certification") in {"GREEN", "PASS"} and payload.get("authentication") == "PASS":
                return STATUS_PASS
    return STATUS_UNKNOWN


def _authentication_status(trace: Mapping[str, Any], *payloads: Mapping[str, Any]) -> str:
    if trace:
        return canonical_status(trace.get("authentication") or trace.get("status"))
    for payload in payloads:
        value = (
            payload.get("authentication")
            if payload.get("authentication") is not None
            else payload.get("broker_authenticated")
            if payload.get("broker_authenticated") is not None
            else payload.get("authenticated")
            if payload.get("authenticated") is not None
            else payload.get("authentication_status")
        )
        if value is not None:
            return STATUS_PASS if value is True else STATUS_FAIL if value is False else canonical_status(value)
    return STATUS_NOT_TESTED


def _transport_status(*payloads: Mapping[str, Any]) -> str:
    for payload in payloads:
        value = payload.get("transport_status") or payload.get("api_reachable") or payload.get("transport_reachable") or payload.get("broker_connected") or payload.get("connected")
        if value is not None:
            return STATUS_PASS if value is True else STATUS_FAIL if value is False else canonical_status(value)
    return STATUS_UNKNOWN


def _connection_status(transport_status: str, authentication_status: str) -> str:
    if transport_status == STATUS_PASS and authentication_status == STATUS_PASS:
        return STATUS_PASS
    if authentication_status == STATUS_FAIL:
        return STATUS_FAIL
    if transport_status == STATUS_FAIL:
        return STATUS_FAIL
    return transport_status


def _read_status(kind: str, runtime: Mapping[str, Any], trace: Mapping[str, Any], adapter: Mapping[str, Any], cert: Mapping[str, Any]) -> str:
    endpoints = _mapping(trace.get("endpoint_verification"))
    if kind == "account":
        return _first_status(
            _mapping(endpoints.get("accounts")).get("status"),
            runtime.get("account_status"),
            runtime.get("account_data_health"),
            runtime.get("account_loaded"),
            adapter.get("account_data_health"),
            cert.get("account_access") or cert.get("account"),
        )
    if kind == "balance":
        return _first_status(
            _mapping(endpoints.get("balances")).get("status"),
            runtime.get("balance_status"),
            runtime.get("balance_position_status"),
            runtime.get("balances_loaded"),
            cert.get("balances"),
        )
    if kind == "market_data":
        return _first_status(
            _mapping(endpoints.get("market_data")).get("status"),
            runtime.get("market_data_status"),
            runtime.get("market_data_health"),
            runtime.get("market_data_loaded"),
            adapter.get("market_data_status"),
            cert.get("market_data"),
        )
    if kind == "product":
        return _first_status(
            _mapping(endpoints.get("products")).get("status"),
            runtime.get("product_status"),
            runtime.get("product_price_status"),
            runtime.get("products_loaded") if int(runtime.get("products_loaded", 0) or 0) > 0 else None,
            cert.get("products"),
        )
    return STATUS_UNKNOWN


def _first_status(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            return STATUS_PASS if value else STATUS_UNAVAILABLE
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return STATUS_PASS if value > 0 else STATUS_UNAVAILABLE
        status = canonical_status(value)
        if status != STATUS_NOT_TESTED or str(value).strip():
            return status
    return STATUS_UNAVAILABLE


def _buying_power_status(runtime: Mapping[str, Any], adapter: Mapping[str, Any], margin: Mapping[str, Any]) -> str:
    if str(margin.get("margin_source", "") or "").upper() == "LIVE_UNAVAILABLE":
        return STATUS_UNAVAILABLE
    for payload in (runtime, adapter, margin):
        value = payload.get("buying_power")
        if value not in (None, "", "DATA UNAVAILABLE", "NOT_APPLICABLE"):
            return STATUS_PASS if finite_float(value, default=-1.0) >= 0 else STATUS_UNAVAILABLE
    return STATUS_UNAVAILABLE


def _margin_status(runtime: Mapping[str, Any], adapter: Mapping[str, Any], margin: Mapping[str, Any]) -> str:
    source = str(margin.get("margin_source", "") or "").upper()
    if source == "LIVE_UNAVAILABLE":
        return STATUS_UNAVAILABLE
    for payload in (runtime, adapter, margin):
        value = payload.get("margin_status") or payload.get("margin_state")
        if value:
            return canonical_status(value)
        if payload.get("margin_available") not in (None, "", "DATA UNAVAILABLE"):
            return STATUS_PASS if finite_float(payload.get("margin_available"), default=-1.0) >= 0 else STATUS_UNAVAILABLE
    return STATUS_UNAVAILABLE


def _order_submission_status(*payloads: Mapping[str, Any]) -> str:
    for payload in payloads:
        value = payload.get("order_submission_status") or payload.get("broker_execution_status")
        if value:
            text = str(value).upper()
            if text in {"ENABLED", "PASS", "READY"}:
                return STATUS_PASS
            if text in {"DISABLED", "BLOCKED"}:
                return STATUS_BLOCKED
            return canonical_status(text)
    return STATUS_BLOCKED


def _pre_validation_reasons(runtime: Mapping[str, Any], trace: Mapping[str, Any], cert: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if _truthy(runtime.get("execution_allowed")) and _truthy(runtime.get("live_trading_blocked", True)):
        reasons.append("execution_allowed_while_live_trading_blocked")
    if _truthy(runtime.get("broker_execution_armed")) and str(runtime.get("live_micro_pilot_state", runtime.get("pilot_state", "DISARMED"))).upper() == "DISARMED":
        reasons.append("broker_execution_armed_while_pilot_disarmed")
    if canonical_status(trace.get("authentication")) == STATUS_FAIL and str(cert.get("certification", "")).upper() in {"GREEN", "PASS"}:
        reasons.append("current_authentication_failure_overrides_stale_success")
    raw_auth = trace.get("authentication") if trace.get("authentication") is not None else runtime.get("broker_authenticated", runtime.get("authenticated"))
    raw_connected = runtime.get("broker_connected", runtime.get("connected", runtime.get("api_reachable")))
    if (raw_auth is False or canonical_status(raw_auth) == STATUS_FAIL) and _truthy(raw_connected):
        reasons.append("authentication_failed_but_connection_ready")
    raw_balance = runtime.get("balance_status") if runtime.get("balance_status") is not None else runtime.get("balances_loaded")
    balance_unavailable = raw_balance is False or canonical_status(raw_balance) == STATUS_UNAVAILABLE
    if balance_unavailable:
        if canonical_status(runtime.get("buying_power_status")) == STATUS_PASS or runtime.get("buying_power") not in (None, "", "DATA UNAVAILABLE", "UNAVAILABLE", "NOT_APPLICABLE"):
            reasons.append("balance_unavailable_but_buying_power_ready")
        if canonical_status(runtime.get("margin_status")) == STATUS_PASS or runtime.get("margin_available") not in (None, "", "DATA UNAVAILABLE", "UNAVAILABLE", "NOT_APPLICABLE"):
            reasons.append("balance_unavailable_but_margin_ready")
    return reasons


def _overall_status(*statuses_and_payloads: Any) -> str:
    credential, auth, account, balance, market, product, environment, cert, runtime = statuses_and_payloads
    if isinstance(environment, Mapping) and environment.get("status") == "FAIL":
        return OVERALL_RED
    if credential == STATUS_PASS and auth == STATUS_PASS and account == STATUS_PASS and balance == STATUS_PASS and market == STATUS_PASS:
        return OVERALL_GREEN
    if auth == STATUS_PASS and market == STATUS_PASS and account in {STATUS_UNAVAILABLE, STATUS_FAIL}:
        return OVERALL_AMBER
    cert_status = canonical_overall(_mapping(cert).get("certification") or _mapping(runtime).get("broker_health"))
    if cert_status in {OVERALL_GREEN, OVERALL_AMBER} and auth == STATUS_PASS:
        return cert_status
    return OVERALL_RED


def _failure_reason(runtime: Mapping[str, Any], trace: Mapping[str, Any], adapter: Mapping[str, Any], cert: Mapping[str, Any], environment: Mapping[str, Any]) -> str:
    if environment.get("status") == "FAIL":
        return "ENVIRONMENT_CONTAMINATION"
    for payload in (trace, adapter, runtime, cert):
        for key in ("failure_reason", "connection_error", "coinbase_error_code", "error_code"):
            value = payload.get(key)
            if value:
                return _structured_reason(value)
        blockers = payload.get("blockers") or payload.get("blocker_reasons") or payload.get("failure_reasons")
        if isinstance(blockers, list) and blockers:
            return _structured_reason(blockers[0])
    return _derive_structured_failure_reason(runtime, trace, adapter, cert)


def _account_evidence(
    *,
    runtime: Mapping[str, Any],
    trace: Mapping[str, Any],
    adapter: Mapping[str, Any],
    cert: Mapping[str, Any],
    transport_status: str,
    authentication_status: str,
    connection_status: str,
    account_status: str,
    balance_status: str,
    buying_power_status: str,
    margin_status: str,
    market_data_status: str,
    product_status: str,
) -> dict[str, Any]:
    balances_loaded = balance_status == STATUS_PASS
    return {
        "transport_reachable": transport_status == STATUS_PASS,
        "authenticated": authentication_status == STATUS_PASS,
        "connected": connection_status == STATUS_PASS,
        "account_loaded": account_status == STATUS_PASS,
        "balances_loaded": balances_loaded,
        "buying_power_loaded": balances_loaded and buying_power_status == STATUS_PASS,
        "margin_loaded": balances_loaded and margin_status == STATUS_PASS,
        "products_loaded": product_status == STATUS_PASS,
        "market_data_loaded": market_data_status == STATUS_PASS,
        "equity_loaded": balances_loaded and _equity_loaded(runtime, adapter, cert),
        "account_type": str(runtime.get("account_type") or adapter.get("account_type") or cert.get("account_type") or "UNKNOWN"),
        "portfolio_loaded": _portfolio_loaded(runtime, trace, adapter, cert),
    }


def _status_provenance(
    *,
    mode: str,
    runtime: Mapping[str, Any],
    trace: Mapping[str, Any],
    adapter: Mapping[str, Any],
    cert: Mapping[str, Any],
    margin: Mapping[str, Any],
    credential_status: str,
    transport_status: str,
    authentication_status: str,
    connection_status: str,
    account_status: str,
    balance_status: str,
    buying_power_status: str,
    margin_status: str,
    market_data_status: str,
    product_status: str,
) -> dict[str, Any]:
    margin_source = _provenance_from_margin(margin)
    return {
        "credentials": _provenance_for_status(credential_status, mode, runtime, trace, adapter, cert),
        "transport": _provenance_for_status(transport_status, mode, runtime, trace, adapter, cert),
        "authentication": _provenance_for_status(authentication_status, mode, runtime, trace, adapter, cert),
        "connection": _provenance_for_status(connection_status, mode, runtime, trace, adapter, cert),
        "account": _provenance_for_status(account_status, mode, runtime, trace, adapter, cert),
        "balances": _provenance_for_status(balance_status, mode, runtime, trace, adapter, cert),
        "buying_power": margin_source if buying_power_status == STATUS_PASS else _provenance_for_status(buying_power_status, mode, runtime, trace, adapter, cert),
        "margin": margin_source if margin_status == STATUS_PASS else _provenance_for_status(margin_status, mode, runtime, trace, adapter, cert),
        "market_data": _provenance_for_status(market_data_status, mode, runtime, trace, adapter, cert),
        "products": _provenance_for_status(product_status, mode, runtime, trace, adapter, cert),
        "overall": "LIVE" if mode == "live" and all(
            status == STATUS_PASS
            for status in (credential_status, authentication_status, connection_status, account_status, balance_status, market_data_status)
        ) else "UNAVAILABLE",
    }


def _provenance_for_status(status: str, mode: str, *payloads: Mapping[str, Any]) -> str:
    for payload in payloads:
        explicit = str(payload.get("provenance") or payload.get("source_provenance") or payload.get("data_provenance") or "").strip().upper()
        if explicit in {"LIVE", "CACHE", "HISTORICAL", "SIMULATION", "UNAVAILABLE", "UNKNOWN"}:
            return explicit
    if status == STATUS_PASS:
        return "LIVE" if str(mode).lower() == "live" else "SIMULATION"
    if status in {STATUS_FAIL, STATUS_UNAVAILABLE, STATUS_BLOCKED}:
        return "UNAVAILABLE"
    return "UNKNOWN"


def _provenance_from_margin(margin: Mapping[str, Any]) -> str:
    source = str(margin.get("margin_source") or margin.get("source_provenance") or "").strip().upper()
    if source in {"CACHE", "CACHED"}:
        return "CACHE"
    if source in {"HISTORICAL", "HISTORY"}:
        return "HISTORICAL"
    if source in {"SIMULATED", "SIMULATION"}:
        return "SIMULATION"
    if source in {"LIVE", "BROKER"}:
        return "LIVE"
    if source in {"LIVE_UNAVAILABLE", "UNAVAILABLE", "BROKER_UNAVAILABLE"}:
        return "UNAVAILABLE"
    return "UNKNOWN"


def _derive_structured_failure_reason(*payloads: Mapping[str, Any]) -> str:
    statuses = {}
    for payload in payloads:
        statuses.update({key: payload.get(key) for key in payload if key.endswith("_status") or key in {"authentication", "balances", "account", "market_data"}})
    if canonical_status(statuses.get("authentication")) == STATUS_FAIL:
        return "AUTHENTICATION_FAILED"
    if canonical_status(statuses.get("account") or statuses.get("account_status")) in {STATUS_FAIL, STATUS_UNAVAILABLE}:
        return "ACCOUNT_UNAVAILABLE"
    if canonical_status(statuses.get("balances") or statuses.get("balance_status")) in {STATUS_FAIL, STATUS_UNAVAILABLE}:
        return "BALANCE_UNAVAILABLE"
    if canonical_status(statuses.get("market_data") or statuses.get("market_data_status")) in {STATUS_FAIL, STATUS_UNAVAILABLE}:
        return "MARKET_DATA_UNAVAILABLE"
    return "NO_FAILURE"


def _structured_reason(value: Any) -> str:
    text = str(value or "").strip().upper().replace("COINBASE_", "")
    if not text or text == "NONE":
        return "UNKNOWN"
    aliases = {
        "COINBASE_HTTP_401": "HTTP_401",
        "HTTP_401": "HTTP_401",
        "COINBASE_HTTP_403": "HTTP_403",
        "HTTP_403": "HTTP_403",
        "COINBASE_CLOCK_SKEW": "CLOCK_SKEW",
        "CLOCK_SKEW": "CLOCK_SKEW",
        "COINBASE_INVALID_JWT": "JWT_INVALID",
        "INVALID_JWT": "JWT_INVALID",
        "COINBASE_BALANCES_UNAVAILABLE": "BALANCE_UNAVAILABLE",
        "BALANCES_UNAVAILABLE": "BALANCE_UNAVAILABLE",
        "COINBASE_ACCOUNT_UNAVAILABLE": "ACCOUNT_UNAVAILABLE",
        "ACCOUNT_UNAVAILABLE": "ACCOUNT_UNAVAILABLE",
        "COINBASE_MARKET_DATA_ONLY": "MARKET_DATA_ONLY",
        "MARKET_DATA_ONLY": "MARKET_DATA_ONLY",
        "COINBASE_TIMEOUT": "BROKER_TIMEOUT",
        "TIMEOUT": "BROKER_TIMEOUT",
        "COINBASE_DNS_ERROR": "DNS_FAILURE",
        "DNS_ERROR": "DNS_FAILURE",
        "COINBASE_TLS_ERROR": "TLS_FAILURE",
        "TLS_ERROR": "TLS_FAILURE",
        "COINBASE_LIVE_ENVIRONMENT_CONTAMINATION": "ENVIRONMENT_CONTAMINATION",
        "LIVE_ENVIRONMENT_CONTAMINATION": "ENVIRONMENT_CONTAMINATION",
    }
    return aliases.get(text, text)


def _portfolio_loaded(runtime: Mapping[str, Any], trace: Mapping[str, Any], adapter: Mapping[str, Any], cert: Mapping[str, Any]) -> bool:
    endpoints = _mapping(trace.get("endpoint_verification"))
    portfolio_status = _first_status(
        _mapping(endpoints.get("portfolios")).get("status"),
        runtime.get("portfolio_loaded"),
        adapter.get("portfolio_loaded"),
        cert.get("portfolio_access") or cert.get("portfolio"),
    )
    return portfolio_status == STATUS_PASS


def _equity_loaded(runtime: Mapping[str, Any], adapter: Mapping[str, Any], cert: Mapping[str, Any]) -> bool:
    for payload in (runtime, adapter, cert):
        for key in ("account_equity", "equity", "portfolio_value", "balance", "cash"):
            value = payload.get(key)
            if value not in (None, "", "DATA UNAVAILABLE", "UNAVAILABLE", "NOT_APPLICABLE"):
                return finite_float(value, default=-1.0) >= 0
    return False


def _warning_reasons(*payloads: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    for payload in payloads:
        for key in ("warning_reasons", "warnings", "blocker_reasons"):
            value = payload.get(key)
            if isinstance(value, list):
                warnings.extend(str(item) for item in value if str(item))
    return list(dict.fromkeys(warnings))


def _environment_evidence(
    broker: str,
    mode: str,
    env: Mapping[str, Any] | None,
    runtime: Mapping[str, Any],
    trace: Mapping[str, Any],
    margin: Mapping[str, Any],
) -> dict[str, Any]:
    if broker == "COINBASE":
        evidence = classify_coinbase_environment(env or {}, mode=mode)
    else:
        evidence = {"broker": broker, "mode": mode, "status": "PASS", "contamination_keys": [], "findings": []}
    if isinstance(runtime.get("environment_diagnostics"), Mapping):
        diag = dict(runtime.get("environment_diagnostics"))
        if diag.get("contamination_keys"):
            evidence["contamination_keys"] = list(diag.get("contamination_keys"))
            evidence["status"] = "FAIL"
    if isinstance(trace.get("environment"), Mapping):
        diag = dict(trace.get("environment"))
        if diag.get("contamination_keys"):
            evidence["contamination_keys"] = list(diag.get("contamination_keys"))
            evidence["status"] = "FAIL"
    source = str(margin.get("margin_source", "") or "").upper()
    if mode == "live" and source == "SIMULATED" and finite_float(margin.get("buying_power"), default=0.0) > 0:
        evidence["positive_simulated_live_margin"] = True
    if margin.get("buying_power") not in (None, ""):
        evidence["live_buying_power"] = margin.get("buying_power")
    return evidence


def _readiness_score(*payloads: Mapping[str, Any]) -> float:
    for payload in payloads:
        value = payload.get("readiness_score") or payload.get("connectivity_score")
        if value is not None:
            return finite_float(value, default=0.0)
    return 0.0


def _latency(*payloads: Mapping[str, Any]) -> int | None:
    for payload in payloads:
        latency = payload.get("latency_ms") or _mapping(payload.get("latency")).get("overall_ms") or payload.get("authentication_latency_ms")
        if latency is not None:
            return finite_int(latency)
    return None


def _http_status(*payloads: Mapping[str, Any]) -> int | None:
    for payload in payloads:
        value = payload.get("http_status")
        if value is not None:
            return finite_int(value)
    return None


def _source_modules(*payloads: Mapping[str, Any]) -> tuple[str, ...]:
    modules = []
    for payload in payloads:
        source = payload.get("source") or payload.get("validation_source")
        if source:
            modules.append(str(source))
    return tuple(modules or ["canonical_broker_state_builder"])


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled", "armed", "live"}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "SOURCE_PRECEDENCE",
    "build_canonical_broker_runtime_state",
    "canonical_state_from_payload",
]

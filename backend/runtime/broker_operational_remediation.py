from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from backend.runtime.broker_market_data_evidence import discover_server_health_endpoints


PASS = "PASS"
FAIL = "FAIL"
GREEN = "GREEN"
AMBER = "AMBER"
RED = "RED"
PAYLOAD_VERSION = "css.phase156e.operational_broker_readiness_remediation.v1"

ClockFn = Callable[[], float]


def collect_read_only_authentication_evidence(
    adapter: Any,
    *,
    broker: str,
    clock: ClockFn = time.perf_counter,
) -> dict[str, Any]:
    """Collect advisory authentication evidence without using execution paths."""

    started = clock()
    broker_key = _normalize_broker(broker)
    primary_candidates = [
        ("authenticate", ()),
        ("verify_authentication", ()),
        ("validate_authentication", ()),
        ("get_server_time", ()),
        ("get_server_status", ()),
        ("is_configured", ()),
    ]
    fallback_candidates: list[tuple[str, tuple[Any, ...]]] = []
    if broker_key == "oanda":
        fallback_candidates.append(("get_account_summary", ()))
    elif broker_key == "coinbase":
        fallback_candidates.extend(
            [
                ("get_accounts", ()),
                ("get_account", ()),
                ("get_account_balance", ()),
                ("get_balance", ()),
            ]
        )

    attempts: list[dict[str, str]] = []
    primary_seen = False
    for method_name, args in primary_candidates:
        method = getattr(adapter, method_name, None)
        if not callable(method):
            continue
        primary_seen = True
        try:
            payload = method(*args)
        except Exception as exc:  # noqa: BLE001 - advisory evidence records read-only failures.
            reason = _failure_reason(exc)
            attempts.append({"source": method_name, "reason": reason})
            return _auth_failure(broker_key, reason, started, clock, attempts)
        ok, reason = _read_success(payload)
        if ok:
            return {
                "success": True,
                "broker": broker_key,
                "source": method_name,
                "latency_ms": _elapsed_ms(clock, started),
                "payload_type": type(payload).__name__,
                "attempts": attempts,
                **_advisory_flags(),
            }
        attempts.append({"source": method_name, "reason": reason})
        return _auth_failure(broker_key, reason, started, clock, attempts)

    if primary_seen:
        return _auth_failure(broker_key, _last_reason(attempts) or "authentication_failed", started, clock, attempts)

    for method_name, args in fallback_candidates:
        method = getattr(adapter, method_name, None)
        if not callable(method):
            continue
        try:
            payload = method(*args)
        except Exception as exc:  # noqa: BLE001 - advisory evidence records read-only failures.
            attempts.append({"source": method_name, "reason": _failure_reason(exc)})
            continue
        ok, reason = _read_success(payload)
        if ok:
            return {
                "success": True,
                "broker": broker_key,
                "source": method_name,
                "latency_ms": _elapsed_ms(clock, started),
                "payload_type": type(payload).__name__,
                "attempts": attempts,
                **_advisory_flags(),
            }
        attempts.append({"source": method_name, "reason": reason})

    return {
        "success": False,
        "broker": broker_key,
        "source": "",
        "reason": _last_reason(attempts) or "read_only_method_unavailable",
        "latency_ms": _elapsed_ms(clock, started),
        "attempts": attempts,
        **_advisory_flags(),
    }


def classify_oanda_http_401(
    *,
    env: Mapping[str, Any] | None = None,
    adapter: Any | None = None,
    response_payload: Any | None = None,
) -> dict[str, Any]:
    """Classify OANDA 401 causes without exposing or modifying credentials."""

    source = env or os.environ
    base_url = str(_adapter_or_env(adapter, source, "base_url", "OANDA_BASE_URL") or "").strip().lower()
    configured_env = str(_adapter_or_env(adapter, source, "env", "OANDA_ENV") or "").strip().lower()
    account_id_present = bool(str(_adapter_or_env(adapter, source, "account_id", "OANDA_ACCOUNT_ID") or "").strip())
    token_present = bool(str(_adapter_or_env(adapter, source, "api_key", "OANDA_API_KEY") or source.get("OANDA_TOKEN") or source.get("OANDA_ACCESS_TOKEN") or "").strip())
    authorization_header_valid = _authorization_header_valid(adapter)
    response_text = json.dumps(response_payload, default=str).lower() if response_payload is not None else ""

    blockers: list[str] = []
    if not token_present:
        blockers.append("TOKEN_MISSING")
    if not account_id_present:
        blockers.append("ACCOUNT_ID_MISSING")
    if not base_url:
        blockers.append("BASE_URL_MISSING")
    if configured_env in {"practice", "demo", "paper"} and base_url and "practice" not in base_url:
        blockers.append("PRACTICE_ENV_WITH_LIVE_BASE_URL")
    if configured_env in {"live", "production", "prod"} and "practice" in base_url:
        blockers.append("LIVE_ENV_WITH_PRACTICE_BASE_URL")
    if not authorization_header_valid:
        blockers.append("AUTHORIZATION_HEADER_FORMAT_INVALID")
    if "account" in response_text and any(marker in response_text for marker in ("invalid", "not found", "not exist", "unauthor")):
        blockers.append("ACCOUNT_ID_OR_ACCOUNT_PERMISSION_MISMATCH")
    if any(marker in response_text for marker in ("token", "invalid authorization", "insufficient authorization", "unauthor")):
        blockers.append("TOKEN_OR_PERMISSION_FAILURE")
    if any(marker in response_text for marker in ("clock", "skew", "timestamp")):
        blockers.append("CLOCK_SKEW_EVIDENCE")

    if not blockers:
        blockers.append("OANDA_HTTP_401_TOKEN_PERMISSION_OR_ENDPOINT_MISMATCH")

    endpoint_alignment = "UNKNOWN"
    if "PRACTICE_ENV_WITH_LIVE_BASE_URL" in blockers or "LIVE_ENV_WITH_PRACTICE_BASE_URL" in blockers:
        endpoint_alignment = "MISMATCH"
    elif base_url and configured_env:
        endpoint_alignment = "CONSISTENT"

    classification = blockers[0]
    return {
        "broker": "OANDA",
        "status": RED,
        "classification": classification,
        "blockers": blockers,
        "checks": {
            "token_present": token_present,
            "account_id_present": account_id_present,
            "base_url_present": bool(base_url),
            "configured_env_present": bool(configured_env),
            "endpoint_alignment": endpoint_alignment,
            "authorization_header_format": "VALID" if authorization_header_valid else "INVALID",
            "clock_skew_evidence": "CLOCK_SKEW_EVIDENCE" in blockers,
        },
        "recommendations": _oanda_401_recommendations(blockers),
        "secrets_redacted": True,
        **_advisory_flags(),
    }


def discover_css_health_endpoint(
    *,
    env: Mapping[str, Any] | None = None,
    timeout_seconds: float = 1.5,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"env": env, "timeout_seconds": timeout_seconds}
    if opener is not None:
        kwargs["opener"] = opener
    report = discover_server_health_endpoints(**kwargs)
    selected = report.get("selected_endpoint") if isinstance(report.get("selected_endpoint"), Mapping) else None
    health_state = str(report.get("health_state") or (GREEN if selected else RED)).upper()
    return {
        "selected_endpoint": selected.get("url") if selected else None,
        "response_time": selected.get("response_time_ms") if selected else None,
        "response_time_ms": selected.get("response_time_ms") if selected else None,
        "health_state": health_state,
        "details": report,
        **_advisory_flags(),
    }


def build_operational_readiness_summary(
    *,
    broker_reports: Mapping[str, Mapping[str, Any]],
    health_endpoint: Mapping[str, Any] | None = None,
    previous_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    brokers: dict[str, Any] = {}
    for broker in ("oanda", "coinbase"):
        phase156a = dict(broker_reports.get(f"{broker}_phase156a", {}))
        phase156b = dict(broker_reports.get(f"{broker}_phase156b", {}))
        phase156c = dict(broker_reports.get(f"{broker}_phase156c", {}))
        broker_name = broker.upper()
        blockers = sorted(
            {
                str(item)
                for item in (
                    list(phase156a.get("blocker_reasons", []))
                    + list(phase156b.get("blocker_reasons", []))
                    + list(phase156c.get("blocker_reasons", []))
                )
                if str(item)
            }
        )
        remediation = None
        if broker == "oanda" and any("http_401" in item for item in blockers):
            remediation = classify_oanda_http_401()

        brokers[broker_name] = {
            "broker": broker_name,
            "credential_status": phase156a.get("credentials", "UNKNOWN"),
            "bootstrap": phase156a.get("bootstrap", "UNKNOWN"),
            "authentication": phase156b.get("authentication", phase156a.get("authentication", "UNKNOWN")),
            "account_access": phase156b.get("account", phase156a.get("account", "UNKNOWN")),
            "market_data": phase156b.get("market_data", phase156a.get("market_data", "UNKNOWN")),
            "latency": phase156b.get("latency", phase156a.get("latency", {})),
            "firewall": _firewall_summary(phase156a, phase156b, phase156c),
            "health": phase156c.get("health", "UNKNOWN"),
            "blockers": blockers,
            "recommendations": _broker_recommendations(broker, blockers, remediation),
            "remediation": remediation,
        }

    all_blockers = sorted({blocker for payload in brokers.values() for blocker in payload.get("blockers", [])})
    health = dict(health_endpoint or {})
    if health and str(health.get("health_state", "")).upper() != GREEN:
        all_blockers.append("health_endpoint_not_green")

    return {
        "payload_version": PAYLOAD_VERSION,
        "generated_at": _iso_timestamp(),
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "brokers": brokers,
        "health_endpoint": health,
        "blockers": sorted(set(all_blockers)),
        "previous_broker_status": previous_summary.get("broker_status") if previous_summary else None,
        "recommendation": "GO" if not all_blockers else "NO_GO",
        **_advisory_flags(),
    }


def write_operational_readiness_summary(
    *,
    broker_reports: Mapping[str, Mapping[str, Any]],
    report_dir: str | Path = "runtime_reports/broker_validation",
    health_endpoint: Mapping[str, Any] | None = None,
    previous_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    target = Path(report_dir)
    target.mkdir(parents=True, exist_ok=True)
    summary = build_operational_readiness_summary(
        broker_reports=broker_reports,
        health_endpoint=health_endpoint,
        previous_summary=previous_summary,
    )
    (target / "operational_readiness_summary.json").write_text(json.dumps(_json_safe(summary), indent=2, sort_keys=True), encoding="utf-8")
    (target / "operational_readiness_summary.md").write_text(_summary_markdown(summary), encoding="utf-8")
    return summary


def _firewall_summary(*reports: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        "all_reports_blocked": all(
            report.get("execution_allowed") is False
            and report.get("live_trading_blocked") is True
            and report.get("broker_execution_armed") is False
            and report.get("advisory_only") is True
            for report in reports
            if report
        ),
    }


def _broker_recommendations(broker: str, blockers: list[str], remediation: Mapping[str, Any] | None) -> list[str]:
    recommendations: list[str] = []
    if remediation and remediation.get("recommendations"):
        recommendations.extend(str(item) for item in remediation.get("recommendations", []))
    if any("authentication" in blocker for blocker in blockers) and broker == "coinbase":
        recommendations.append("Use existing read-only Coinbase account or balance retrieval as authentication evidence; do not enable execution.")
    if any("market_data" in blocker for blocker in blockers):
        recommendations.append("Verify read-only market-data evidence sources before controlled live validation planning.")
    if not recommendations:
        recommendations.append("No operational remediation blockers detected.")
    return sorted(dict.fromkeys(recommendations))


def _oanda_401_recommendations(blockers: list[str]) -> list[str]:
    recommendations: list[str] = []
    if any("BASE_URL" in blocker or "ENV" in blocker for blocker in blockers):
        recommendations.append("Verify OANDA_ENV matches OANDA_BASE_URL practice/live host.")
    if any("TOKEN" in blocker or "PERMISSION" in blocker for blocker in blockers):
        recommendations.append("Verify the configured token belongs to the selected OANDA environment and account.")
    if any("ACCOUNT" in blocker for blocker in blockers):
        recommendations.append("Verify OANDA_ACCOUNT_ID belongs to the token and selected practice/live environment.")
    if "AUTHORIZATION_HEADER_FORMAT_INVALID" in blockers:
        recommendations.append("Verify the adapter sends Authorization as Bearer plus the raw token value.")
    if "CLOCK_SKEW_EVIDENCE" in blockers:
        recommendations.append("Verify host clock synchronization before retrying read-only validation.")
    if not recommendations:
        recommendations.append("Inspect OANDA credential/environment pairing; no secrets were read or modified.")
    return sorted(dict.fromkeys(recommendations))


def _summary_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Operational Broker Readiness Summary",
        "",
        f"Generated: {summary.get('generated_at')}",
        "",
        "## Brokers",
    ]
    brokers = summary.get("brokers", {})
    if isinstance(brokers, Mapping):
        for name, payload in brokers.items():
            if not isinstance(payload, Mapping):
                continue
            blockers = ", ".join(str(item) for item in payload.get("blockers", [])) or "none"
            lines.append(
                f"- {name}: credentials={payload.get('credential_status')} bootstrap={payload.get('bootstrap')} "
                f"authentication={payload.get('authentication')} account={payload.get('account_access')} "
                f"market_data={payload.get('market_data')} health={payload.get('health')} blockers={blockers}"
            )
    health = summary.get("health_endpoint", {}) if isinstance(summary.get("health_endpoint"), Mapping) else {}
    lines.extend(
        [
            "",
            "## Health Endpoint",
            f"- selected_endpoint: {health.get('selected_endpoint')}",
            f"- response_time_ms: {health.get('response_time_ms')}",
            f"- health_state: {health.get('health_state')}",
            "",
            "## Recommendation",
            str(summary.get("recommendation", "NO_GO")),
            "",
        ]
    )
    return "\n".join(lines)


def _read_success(value: Any) -> tuple[bool, str]:
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
        return bool(value), "empty_broker_response" if not value else ""
    if isinstance(value, (list, tuple, set)):
        return bool(value), "empty_broker_response" if not value else ""
    return True, ""


def _auth_failure(
    broker: str,
    reason: str,
    started: float,
    clock: ClockFn,
    attempts: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "success": False,
        "broker": broker,
        "source": "",
        "reason": reason or "authentication_failed",
        "latency_ms": _elapsed_ms(clock, started),
        "attempts": attempts,
        **_advisory_flags(),
    }


def _adapter_or_env(adapter: Any | None, env: Mapping[str, Any], adapter_attr: str, env_key: str) -> Any:
    if adapter is not None and hasattr(adapter, adapter_attr):
        return getattr(adapter, adapter_attr)
    return env.get(env_key)


def _authorization_header_valid(adapter: Any | None) -> bool:
    if adapter is None or not callable(getattr(adapter, "_headers", None)):
        return True
    try:
        authorization = str(adapter._headers().get("Authorization", ""))
    except Exception:
        return False
    return authorization.startswith("Bearer ") and len(authorization.strip()) > len("Bearer ")


def _last_reason(attempts: list[dict[str, str]]) -> str:
    for attempt in reversed(attempts):
        reason = str(attempt.get("reason", "") or "")
        if reason:
            return reason
    return ""


def _elapsed_ms(clock: ClockFn, started: float) -> int:
    return max(0, int(round((clock() - started) * 1000)))


def _failure_reason(exc: BaseException) -> str:
    if isinstance(exc, TimeoutError):
        return "TIMEOUT"
    text = f"{exc.__class__.__name__} {exc}".lower()
    if "401" in text or "unauthor" in text:
        return "AUTH_FAILED"
    if "unavailable" in text or "503" in text:
        return "BROKER_UNAVAILABLE"
    if "timeout" in text or "timed out" in text:
        return "TIMEOUT"
    return str(exc) or exc.__class__.__name__


def _normalize_broker(broker: str) -> str:
    return str(broker or "").strip().lower()


def _iso_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _advisory_flags() -> dict[str, bool]:
    return {
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)

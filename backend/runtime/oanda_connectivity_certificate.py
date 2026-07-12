from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.runtime.oanda_authentication_trace import PASS, trace_oanda_authentication


PAYLOAD_VERSION = "css.phase165e.oanda_connectivity_certificate.v1"


def certify_oanda_read_only_connectivity(
    adapter: Any,
    *,
    env: Mapping[str, Any] | None = None,
    mode: str = "live",
    require_credentials: bool = True,
) -> dict[str, Any]:
    trace = trace_oanda_authentication(
        adapter,
        env=env,
        mode=mode,
        require_credentials=require_credentials,
    )
    endpoints = trace.get("endpoint_verification") if isinstance(trace.get("endpoint_verification"), Mapping) else {}
    account_presence = _merged_account_presence(endpoints)
    safety = _safety_payload()
    fields = {
        "credential_validation": PASS if _stage_status(trace.get("credential_validation")) == PASS else "FAIL",
        "authentication": PASS if trace.get("authentication") == PASS else "FAIL",
        "account_access": PASS if _account_access_ok(endpoints) else "FAIL",
        "balance_access": PASS if account_presence.get("balance") else "FAIL",
        "nav_access": PASS if account_presence.get("nav") else "FAIL",
        "margin_access": PASS if account_presence.get("margin_available") else "FAIL",
        "instrument_access": PASS if _stage_status(endpoints.get("instruments")) == PASS else "FAIL",
        "pricing_access": PASS if _stage_status(endpoints.get("pricing")) == PASS else "FAIL",
        "open_trades_access": PASS if _stage_status(endpoints.get("open_trades")) == PASS else "FAIL",
        "open_positions_access": PASS if _stage_status(endpoints.get("positions")) == PASS else "FAIL",
        "safety_gates_status": PASS if safety["execution_authority"] == "BLOCKED" else "FAIL",
    }
    blockers = [name for name, status in fields.items() if status != PASS]
    latency = {
        "authentication_ms": trace.get("authentication_latency_ms"),
        "account_summary_ms": _latency(endpoints.get("account_summary")),
        "account_details_ms": _latency(endpoints.get("account_details")),
        "instruments_ms": _latency(endpoints.get("instruments")),
        "pricing_ms": _latency(endpoints.get("pricing")),
        "open_trades_ms": _latency(endpoints.get("open_trades")),
        "positions_ms": _latency(endpoints.get("positions")),
    }
    latency_status = _latency_status(latency)
    read_only_certification = PASS if not blockers else "FAIL"
    canonical_state = "READ_ONLY_CERTIFIED" if read_only_certification == PASS else "READ_ONLY_BLOCKED"
    return {
        "payload_version": PAYLOAD_VERSION,
        "broker": "OANDA",
        "mode": mode,
        **fields,
        "latency": latency,
        "latency_status": latency_status,
        "authentication_trace": trace,
        "canonical_broker_state": canonical_state,
        "health_color": _health_color(read_only_certification, latency_status),
        "safety_gates": safety,
        "execution_authority": "BLOCKED",
        "read_only_certification": read_only_certification,
        "certification": read_only_certification,
        "blocker_reasons": blockers,
        "recommendations": _recommendations(blockers, latency_status),
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def oanda_connectivity_certificate_json(report: Mapping[str, Any], *, indent: int = 2) -> str:
    return json.dumps(_json_safe(report), indent=indent, sort_keys=True)


def write_oanda_connectivity_certificate(report: Mapping[str, Any], path: str | Path, *, indent: int = 2) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(oanda_connectivity_certificate_json(report, indent=indent), encoding="utf-8")


def _stage_status(value: Any) -> str:
    return str(value.get("status", "FAIL")).upper() if isinstance(value, Mapping) else "FAIL"


def _latency(value: Any) -> int | None:
    if isinstance(value, Mapping):
        latency = value.get("latency_ms")
        return int(latency) if isinstance(latency, int) else None
    return None


def _merged_account_presence(endpoints: Mapping[str, Any]) -> dict[str, bool]:
    merged = {
        "account_id": False,
        "alias": False,
        "currency": False,
        "balance": False,
        "nav": False,
        "margin_available": False,
    }
    for name in ("authentication", "account_summary", "account_details"):
        stage = endpoints.get(name)
        if not isinstance(stage, Mapping):
            continue
        presence = stage.get("field_presence")
        if not isinstance(presence, Mapping):
            continue
        for key in merged:
            merged[key] = merged[key] or bool(presence.get(key))
    return merged


def _account_access_ok(endpoints: Mapping[str, Any]) -> bool:
    return _stage_status(endpoints.get("account_summary")) == PASS or _stage_status(endpoints.get("account_details")) == PASS


def _latency_status(latency: Mapping[str, int | None]) -> str:
    values = [value for value in latency.values() if isinstance(value, int)]
    if not values:
        return "RED"
    if max(values) <= 1000:
        return "GREEN"
    if max(values) <= 5000:
        return "AMBER"
    return "RED"


def _health_color(certification: str, latency_status: str) -> str:
    if certification != PASS:
        return "RED"
    if latency_status in {"AMBER", "RED"}:
        return "AMBER"
    return "GREEN"


def _safety_payload() -> dict[str, Any]:
    return {
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "execution_authority": "BLOCKED",
        "order_submission": "DISABLED",
        "order_cancellation": "DISABLED",
        "advisory_only": True,
    }


def _recommendations(blockers: list[str], latency_status: str) -> list[str]:
    if blockers:
        return [f"Resolve OANDA read-only blocker: {blocker}." for blocker in blockers]
    if latency_status == "RED":
        return ["OANDA read-only connectivity is certified with high latency; keep live execution blocked and monitor latency before pilot planning."]
    if latency_status == "AMBER":
        return ["OANDA read-only connectivity is functional with elevated latency; continue monitoring before pilot planning."]
    return ["OANDA read-only connectivity is certified; live execution remains blocked."]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


__all__ = [
    "certify_oanda_read_only_connectivity",
    "oanda_connectivity_certificate_json",
    "write_oanda_connectivity_certificate",
]

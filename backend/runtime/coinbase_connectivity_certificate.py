from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.runtime.coinbase_authentication_trace import (
    PASS,
    trace_coinbase_authentication,
)


PAYLOAD_VERSION = "css.phase165e.coinbase_connectivity_certificate.v1"


def certify_coinbase_read_only_connectivity(
    adapter: Any,
    *,
    env: Mapping[str, Any] | None = None,
    mode: str = "live",
    require_credentials: bool = True,
) -> dict[str, Any]:
    trace = trace_coinbase_authentication(
        adapter,
        env=env,
        mode=mode,
        require_credentials=require_credentials,
    )
    endpoints = trace.get("endpoint_verification") if isinstance(trace.get("endpoint_verification"), Mapping) else {}
    products_loaded = _product_count(endpoints.get("products") if isinstance(endpoints, Mapping) else {})
    safety = _safety_payload()
    fields = {
        "credential_validation": PASS if _stage_status(trace.get("credential_validation")) in {PASS, "UNKNOWN"} else "FAIL",
        "authentication": PASS if trace.get("authentication") == PASS else "FAIL",
        "account_access": PASS if _stage_status(endpoints.get("accounts")) == PASS else "FAIL",
        "balances": PASS if _stage_status(endpoints.get("balances")) == PASS else "FAIL",
        "portfolio_information": PASS if _stage_status(endpoints.get("portfolios")) == PASS else "FAIL",
        "products": PASS if _stage_status(endpoints.get("products")) == PASS and products_loaded > 0 else "FAIL",
        "market_data": PASS if _stage_status(endpoints.get("market_data")) == PASS else "FAIL",
        "safety_gates_status": PASS if safety["execution_authority"] == "BLOCKED" else "FAIL",
    }
    blockers = [name for name, status in fields.items() if status != PASS]
    read_only_certification = PASS if not blockers else "FAIL"
    return {
        "payload_version": PAYLOAD_VERSION,
        "broker": "COINBASE",
        "mode": mode,
        **fields,
        "products_loaded": products_loaded,
        "latency": {
            "authentication_ms": trace.get("authentication_latency_ms"),
            "accounts_ms": _latency(endpoints.get("accounts")),
            "balances_ms": _latency(endpoints.get("balances")),
            "products_ms": _latency(endpoints.get("products")),
            "market_data_ms": _latency(endpoints.get("market_data")),
        },
        "authentication_trace": trace,
        "safety_gates": safety,
        "execution_authority": "BLOCKED",
        "read_only_certification": read_only_certification,
        "certification": read_only_certification,
        "blocker_reasons": blockers,
        "recommendations": _recommendations(blockers),
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def coinbase_connectivity_certificate_json(report: Mapping[str, Any], *, indent: int = 2) -> str:
    return json.dumps(_json_safe(report), indent=indent, sort_keys=True)


def write_coinbase_connectivity_certificate(report: Mapping[str, Any], path: str | Path, *, indent: int = 2) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(coinbase_connectivity_certificate_json(report, indent=indent), encoding="utf-8")


def _stage_status(value: Any) -> str:
    return str(value.get("status", "FAIL")).upper() if isinstance(value, Mapping) else "FAIL"


def _latency(value: Any) -> int | None:
    if isinstance(value, Mapping):
        latency = value.get("latency_ms")
        return int(latency) if isinstance(latency, int) else None
    return None


def _product_count(products_stage: Any) -> int:
    if not isinstance(products_stage, Mapping) or products_stage.get("status") != PASS:
        return 0
    return int(products_stage.get("item_count", 0) or 0)


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


def _recommendations(blockers: list[str]) -> list[str]:
    if not blockers:
        return ["Coinbase read-only connectivity is certified; live execution remains blocked."]
    return [f"Resolve Coinbase read-only blocker: {blocker}." for blocker in blockers]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


__all__ = [
    "certify_coinbase_read_only_connectivity",
    "coinbase_connectivity_certificate_json",
    "write_coinbase_connectivity_certificate",
]

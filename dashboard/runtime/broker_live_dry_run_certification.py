from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.app.brokers.broker_registry import get_broker_spec
from dashboard.runtime.broker_balance_reconciliation import (
    BROKER_RECONCILED,
    reconcile_dashboard_payload,
)


BROKER_LIVE_DRY_RUN_CERTIFICATION_PAYLOAD_VERSION = (
    "css.broker_live_dry_run_certification.v1"
)
LIVE_DRY_RUN_CERTIFIED = "LIVE_DRY_RUN_CERTIFIED"
LIVE_DRY_RUN_DEGRADED = "LIVE_DRY_RUN_DEGRADED"
LIVE_DRY_RUN_BLOCKED = "LIVE_DRY_RUN_BLOCKED"

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "credential",
    "private",
    "pem",
    "authorization",
    "bearer",
)


@dataclass(frozen=True)
class DryRunCertificationCheck:
    code: str
    passed: bool
    severity: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True)
class BrokerLiveDryRunCertificationReport:
    broker: str
    mode: str
    status: str
    certified_for_live: bool
    safe_degradation_required: bool
    recommended_runtime_mode: str
    checks: tuple[DryRunCertificationCheck, ...]
    generated_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    broker_display_name: str = ""
    broker_registered: bool = False
    broker_connected: bool = False
    broker_supports_live: bool = False
    missing_credentials: bool = True
    live_trading_enabled: bool = False
    readiness_status: str = "BROKER_BLOCKED"
    account_readiness: str = "UNKNOWN"
    reconciliation_status: str = "BROKER_UNAVAILABLE"
    account_snapshot_present: bool = False
    position_snapshot_present: bool = False
    order_probe_status: str = "MISSING"
    order_probe: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return _json_safe(
            {
                "payload_version": BROKER_LIVE_DRY_RUN_CERTIFICATION_PAYLOAD_VERSION,
                "generated_utc": self.generated_utc,
                "broker": self.broker,
                "broker_display_name": self.broker_display_name,
                "mode": self.mode,
                "status": self.status,
                "certified_for_live": self.certified_for_live,
                "safe_degradation_required": self.safe_degradation_required,
                "recommended_runtime_mode": self.recommended_runtime_mode,
                "broker_registered": self.broker_registered,
                "broker_connected": self.broker_connected,
                "broker_supports_live": self.broker_supports_live,
                "missing_credentials": self.missing_credentials,
                "live_trading_enabled": self.live_trading_enabled,
                "readiness_status": self.readiness_status,
                "account_readiness": self.account_readiness,
                "reconciliation_status": self.reconciliation_status,
                "account_snapshot_present": self.account_snapshot_present,
                "position_snapshot_present": self.position_snapshot_present,
                "order_probe_status": self.order_probe_status,
                "order_probe": dict(self.order_probe),
                "checks": [check.as_dict() for check in self.checks],
                "summary": {
                    "check_count": len(self.checks),
                    "failed_check_count": sum(
                        1 for check in self.checks if not check.passed
                    ),
                    "error_count": sum(
                        1
                        for check in self.checks
                        if not check.passed and check.severity == "error"
                    ),
                },
            }
        )


def certify_broker_live_dry_run(
    dashboard_payload: Mapping[str, Any],
    *,
    order_probe: Mapping[str, Any] | None = None,
) -> BrokerLiveDryRunCertificationReport:
    """
    Certify broker live dry-run readiness from sanitized runtime snapshots.

    This function never calls a broker and never executes an order. The caller
    must provide a non-executing order_probe if a broker-specific dry run was
    performed elsewhere.
    """

    broker_summary = _mapping(dashboard_payload.get("broker_summary"))
    session = _mapping(dashboard_payload.get("session"))
    broker_name = _broker_name(broker_summary.get("selected_broker"))
    mode = _mode(
        dashboard_payload.get(
            "resolved_mode",
            broker_summary.get("broker_mode", session.get("live_or_paper")),
        )
    )
    readiness_status = str(
        broker_summary.get("readiness_status", "BROKER_BLOCKED")
    ).upper()
    account_readiness = str(
        broker_summary.get("account_readiness", "UNKNOWN")
    ).upper()
    broker_connected = _bool(broker_summary.get("connected"))
    missing_credentials = _bool(broker_summary.get("missing_credentials"))
    live_trading_enabled = _bool(broker_summary.get("live_trading_enabled"))
    account_snapshot_present = bool(_broker_account_snapshot(broker_summary))
    position_snapshot_present = _position_snapshot_present(broker_summary)
    probe = _mapping(order_probe)

    checks: list[DryRunCertificationCheck] = []

    broker_registered = False
    broker_supports_live = False
    broker_display_name = ""
    try:
        spec = get_broker_spec(broker_name)
        broker_registered = True
        broker_supports_live = bool(spec.supports_live)
        broker_display_name = spec.display_name
    except Exception:
        spec = None

    _add_check(
        checks,
        "broker_registered",
        broker_registered,
        "error",
        f"Broker '{broker_name or 'NONE'}' must be registered before live certification.",
    )
    _add_check(
        checks,
        "broker_supports_live",
        broker_registered and broker_supports_live,
        "error",
        "Broker registry must explicitly support live mode.",
    )
    _add_check(
        checks,
        "mode_is_live",
        mode == "live",
        "error",
        "Dry-run live certification only applies to resolved live mode.",
    )
    _add_check(
        checks,
        "credentials_present",
        not missing_credentials,
        "error",
        "Broker credentials must be present, without exposing secret values.",
    )
    _add_check(
        checks,
        "broker_connected",
        broker_connected,
        "error",
        "Broker must report connected state from a sanitized runtime snapshot.",
    )
    _add_check(
        checks,
        "readiness_ready",
        readiness_status == "BROKER_READY",
        "error",
        "Broker readiness status must be BROKER_READY.",
    )
    _add_check(
        checks,
        "account_readiness_live_ready",
        account_readiness in {"LIVE_READY", "READY"},
        "error",
        "Broker account readiness must indicate LIVE_READY or READY.",
    )
    _add_check(
        checks,
        "account_snapshot_present",
        account_snapshot_present,
        "error",
        "A sanitized broker account snapshot is required.",
    )

    reconciliation = reconcile_dashboard_payload(dashboard_payload)
    _add_check(
        checks,
        "broker_reconciliation_clean",
        reconciliation.status == BROKER_RECONCILED,
        "error",
        "Broker reconciliation must be clean before live certification.",
    )

    probe_status = _order_probe_status(probe)
    _add_check(
        checks,
        "dry_run_probe_present",
        bool(probe),
        "error",
        "A non-executing dry-run order probe result is required.",
    )
    _add_check(
        checks,
        "dry_run_probe_non_executing",
        probe_status == "DRY_RUN_ACKNOWLEDGED",
        "error",
        "Dry-run probe must be acknowledged and must not submit an order.",
    )

    status = _status_from_checks(checks)
    certified_for_live = status == LIVE_DRY_RUN_CERTIFIED
    return BrokerLiveDryRunCertificationReport(
        broker=broker_name or "NONE",
        broker_display_name=broker_display_name,
        mode=mode,
        status=status,
        certified_for_live=certified_for_live,
        safe_degradation_required=not certified_for_live,
        recommended_runtime_mode="live" if certified_for_live else "paper",
        broker_registered=broker_registered,
        broker_connected=broker_connected,
        broker_supports_live=broker_supports_live,
        missing_credentials=missing_credentials,
        live_trading_enabled=live_trading_enabled,
        readiness_status=readiness_status,
        account_readiness=account_readiness,
        reconciliation_status=reconciliation.status,
        account_snapshot_present=account_snapshot_present,
        position_snapshot_present=position_snapshot_present,
        order_probe_status=probe_status,
        order_probe=_safe_probe_summary(probe),
        checks=tuple(checks),
    )


def build_broker_live_dry_run_certification_payload(
    dashboard_payload: Mapping[str, Any],
    *,
    order_probe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return certify_broker_live_dry_run(
        dashboard_payload,
        order_probe=order_probe,
    ).as_dict()


def append_broker_live_dry_run_certification_log(
    report: BrokerLiveDryRunCertificationReport,
    path: str | Path,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(report.as_dict(), sort_keys=True) + "\n")


def _add_check(
    checks: list[DryRunCertificationCheck],
    code: str,
    passed: bool,
    severity: str,
    message: str,
) -> None:
    checks.append(
        DryRunCertificationCheck(
            code=code,
            passed=bool(passed),
            severity=severity,
            message=message,
        )
    )


def _status_from_checks(
    checks: Sequence[DryRunCertificationCheck],
) -> str:
    failed = [check for check in checks if not check.passed]
    if not failed:
        return LIVE_DRY_RUN_CERTIFIED
    if any(check.severity == "error" for check in failed):
        return LIVE_DRY_RUN_BLOCKED
    return LIVE_DRY_RUN_DEGRADED


def _order_probe_status(probe: Mapping[str, Any]) -> str:
    if not probe:
        return "MISSING"
    checks = (
        _bool(probe.get("dry_run")),
        "submitted_to_broker" in probe and _bool(probe.get("submitted_to_broker")) is False,
        _bool(probe.get("order_intent_valid")),
        _bool(probe.get("broker_acknowledged")),
        "would_place_live_order" in probe and _bool(probe.get("would_place_live_order")) is False,
    )
    if all(checks):
        return "DRY_RUN_ACKNOWLEDGED"
    return "INVALID_DRY_RUN_PROBE"


def _safe_probe_summary(probe: Mapping[str, Any]) -> dict[str, Any]:
    if not probe:
        return {}
    allowed_keys = (
        "broker",
        "symbol",
        "asset_class",
        "side",
        "order_type",
        "dry_run",
        "submitted_to_broker",
        "would_place_live_order",
        "order_intent_valid",
        "broker_acknowledged",
        "estimated_notional",
        "estimated_cost",
        "reason",
    )
    return {key: probe.get(key) for key in allowed_keys if key in probe}


def _broker_account_snapshot(broker_summary: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(
        broker_summary.get("account_snapshot")
        or broker_summary.get("broker_account_snapshot")
        or broker_summary.get("account")
    )


def _position_snapshot_present(broker_summary: Mapping[str, Any]) -> bool:
    if any(
        key in broker_summary
        for key in ("position_snapshot", "broker_position_snapshot", "positions")
    ):
        return True
    return False


def _broker_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "" if text in {"", "none", "no_broker_selected"} else text


def _mode(value: Any) -> str:
    return "live" if str(value or "").strip().lower() == "live" else "paper"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                "REDACTED" if _is_sensitive_key(str(key)) else _json_safe(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


__all__ = [
    "BROKER_LIVE_DRY_RUN_CERTIFICATION_PAYLOAD_VERSION",
    "LIVE_DRY_RUN_BLOCKED",
    "LIVE_DRY_RUN_CERTIFIED",
    "LIVE_DRY_RUN_DEGRADED",
    "BrokerLiveDryRunCertificationReport",
    "DryRunCertificationCheck",
    "append_broker_live_dry_run_certification_log",
    "build_broker_live_dry_run_certification_payload",
    "certify_broker_live_dry_run",
]

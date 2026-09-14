from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class BrokerDryRunCertificationInput:
    broker: str
    broker_mode: str
    broker_connected: bool
    readiness_status: str
    reconciliation_status: str
    credential_ready: bool
    dry_run_probe: Mapping[str, Any] | None = None


def build_broker_live_dry_run_certification(
    data: BrokerDryRunCertificationInput,
) -> dict[str, Any]:
    probe = dict(data.dry_run_probe or {})
    reasons: list[str] = []

    if not data.broker.strip() or data.broker.upper() in {"NONE", "UNKNOWN"}:
        reasons.append("BROKER_NOT_SELECTED")
    if data.broker_mode.lower() != "live":
        reasons.append("LIVE_MODE_NOT_SELECTED")
    if not data.broker_connected:
        reasons.append("BROKER_NOT_CONNECTED")
    if str(data.readiness_status).upper() not in {"BROKER_READY", "READY", "LIVE_READY"}:
        reasons.append("BROKER_READINESS_NOT_CONFIRMED")
    if str(data.reconciliation_status).upper() not in {"BROKER_RECONCILED", "RECONCILED", "PASS"}:
        reasons.append("RECONCILIATION_NOT_CONFIRMED")
    if not data.credential_ready:
        reasons.append("CREDENTIAL_ATTESTATION_NOT_READY")

    if not probe:
        reasons.append("DRY_RUN_PROBE_MISSING")
    else:
        if probe.get("dry_run") is not True:
            reasons.append("DRY_RUN_FLAG_MISSING")
        if probe.get("submitted_to_broker") is True:
            reasons.append("DRY_RUN_PROBE_SUBMITTED")
        if probe.get("would_place_live_order") is True:
            reasons.append("DRY_RUN_PROBE_EXECUTION_RISK")
        if not str(probe.get("symbol") or "").strip():
            reasons.append("DRY_RUN_SYMBOL_MISSING")
        try:
            if float(probe.get("quantity") or 0) <= 0:
                reasons.append("DRY_RUN_QUANTITY_INVALID")
        except (TypeError, ValueError):
            reasons.append("DRY_RUN_QUANTITY_INVALID")

    passed = not reasons
    return {
        "payload_version": "css.broker_live_dry_run_certification.v1",
        "broker": data.broker.upper() if data.broker else "NONE",
        "broker_mode": data.broker_mode.lower(),
        "status": "PASS" if passed else "FAIL",
        "blocking_reasons": reasons,
        "dry_run_only": True,
        "operator_approval_required": True,
        "execution_allowed": False,
        "broker_execution_armed": False,
        "live_trading_authorized": False,
        "read_only": True,
    }


def build_from_dashboard_state(
    dashboard_payload: Mapping[str, Any],
    *,
    credential_ready: bool,
    dry_run_probe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    broker = dict(dashboard_payload.get("broker_summary") or {})
    reconciliation = dict(dashboard_payload.get("broker_reconciliation") or {})
    return build_broker_live_dry_run_certification(
        BrokerDryRunCertificationInput(
            broker=str(broker.get("selected_broker") or broker.get("broker_name") or "NONE"),
            broker_mode=str(broker.get("broker_mode") or "paper"),
            broker_connected=bool(broker.get("connected") or broker.get("broker_connected")),
            readiness_status=str(broker.get("readiness_status") or "UNKNOWN"),
            reconciliation_status=str(reconciliation.get("status") or "UNKNOWN"),
            credential_ready=bool(credential_ready),
            dry_run_probe=dry_run_probe,
        )
    )


__all__ = [
    "BrokerDryRunCertificationInput",
    "build_broker_live_dry_run_certification",
    "build_from_dashboard_state",
]

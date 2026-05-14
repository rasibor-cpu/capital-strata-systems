from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


RUNTIME_EVENT_PERSISTENCE_CHECKLIST_VERSION = (
    "css.runtime_event_persistence_checklist.v1"
)
READINESS_NOT_READY = "NOT_READY"
READINESS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
READINESS_ELIGIBLE_FOR_PROPOSAL = "ELIGIBLE_FOR_PROPOSAL"

_SENSITIVE_VALUE_MARKERS = (
    "api_key=",
    "apikey=",
    "bearer ",
    "private key",
    "secret=",
    "token=",
    "password=",
    "authorization:",
)
_CHECK_LABELS = {
    "persistence_disabled": "persistence_enabled is false",
    "simulation_only": "simulation_only is true",
    "no_writes_performed": "writes_performed is false",
    "recommended_backend_exists": "recommended backend exists",
    "governance_blockers_listed": "governance blockers are explicitly listed",
    "redaction_required": "redaction is required",
    "approval_token_required": "approval token is required",
    "operator_approval_required": "operator approval is required",
    "pcnrass_notes_exist": "PCNRASS readiness notes exist",
    "no_secrets_detected": "no secrets detected in report",
    "no_live_trading_dependency": "no live trading dependency",
}


@dataclass(frozen=True)
class RuntimeEventPersistenceChecklist:
    checklist_id: str
    generated_at_utc: str
    report_id: str
    readiness_status: str
    required_checks: list[dict[str, str]]
    passed_checks: list[dict[str, str]]
    failed_checks: list[dict[str, str]]
    blocking_items: list[str]
    warnings: list[str]
    operator_review_required: bool
    persistence_enabled: bool
    writes_performed: bool
    simulation_only: bool
    read_only: bool
    payload_version: str = RUNTIME_EVENT_PERSISTENCE_CHECKLIST_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_runtime_event_persistence_checklist(
    report: dict[str, Any] | None = None,
    *,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    dry_run_report = report or {}
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    check_results = _check_results(dry_run_report)
    failed = [item for item in check_results if item["status"] == "FAIL"]
    passed = [item for item in check_results if item["status"] == "PASS"]
    blockers = _blocking_items(dry_run_report, failed)
    warnings = _warnings(dry_run_report)
    readiness = _readiness_status(dry_run_report, failed, blockers)
    report_id = str(dry_run_report.get("report_id") or "")

    checklist = RuntimeEventPersistenceChecklist(
        checklist_id=_checklist_id(
            {
                "generated_at_utc": generated,
                "report_id": report_id,
                "readiness_status": readiness,
            }
        ),
        generated_at_utc=generated,
        report_id=report_id,
        readiness_status=readiness,
        required_checks=[
            {"check_id": check_id, "label": label}
            for check_id, label in _CHECK_LABELS.items()
        ],
        passed_checks=passed,
        failed_checks=failed,
        blocking_items=blockers,
        warnings=warnings,
        operator_review_required=True,
        persistence_enabled=False,
        writes_performed=False,
        simulation_only=True,
        read_only=True,
    )
    return _json_safe(checklist.as_dict())


def _check_results(report: dict[str, Any]) -> list[dict[str, str]]:
    checks = {
        "persistence_disabled": report.get("persistence_enabled") is False,
        "simulation_only": report.get("simulation_only") is True,
        "no_writes_performed": report.get("writes_performed") is False,
        "recommended_backend_exists": bool(str(report.get("recommended_backend") or "").strip())
        and str(report.get("recommended_backend") or "").upper() != "NONE",
        "governance_blockers_listed": isinstance(
            report.get("governance_blockers"),
            list,
        ),
        "redaction_required": report.get("retention_policy_summary", {}).get(
            "redaction_required",
        )
        is True
        and report.get("persistence_approval_policy_summary", {}).get(
            "redaction_required",
        )
        is True,
        "approval_token_required": report.get(
            "persistence_approval_policy_summary",
            {},
        ).get("approval_token_required")
        is True,
        "operator_approval_required": report.get(
            "persistence_approval_policy_summary",
            {},
        ).get("operator_approval_required")
        is True,
        "pcnrass_notes_exist": bool(report.get("pcnrass_readiness_notes")),
        "no_secrets_detected": not _contains_secret_values(report),
        "no_live_trading_dependency": "NO_BROKER_OR_TRADING_BEHAVIOR_CHANGED"
        in set(report.get("safety_assertions") or []),
    }
    return [
        {
            "check_id": check_id,
            "label": _CHECK_LABELS[check_id],
            "status": "PASS" if passed else "FAIL",
        }
        for check_id, passed in checks.items()
    ]


def _blocking_items(report: dict[str, Any], failed: list[dict[str, str]]) -> list[str]:
    items = [f"FAILED_CHECK:{item['check_id']}" for item in failed]
    items.extend(str(item) for item in report.get("governance_blockers") or [])
    if report.get("persistence_enabled") is not False:
        items.append("PERSISTENCE_FLAG_NOT_FALSE")
    if report.get("writes_performed") is not False:
        items.append("WRITE_FLAG_NOT_FALSE")
    return list(dict.fromkeys(items))


def _warnings(report: dict[str, Any]) -> list[str]:
    warnings = ["OPERATOR_REVIEW_REQUIRED_BEFORE_ANY_PROPOSAL"]
    if report.get("remaining_approval_requirements"):
        warnings.append("APPROVAL_REQUIREMENTS_REMAIN")
    if report.get("governance_blockers"):
        warnings.append("GOVERNANCE_BLOCKERS_REMAIN")
    if report.get("simulator_summary", {}).get("rejected_events_count"):
        warnings.append("SIMULATION_REJECTIONS_PRESENT")
    return list(dict.fromkeys(warnings))


def _readiness_status(
    report: dict[str, Any],
    failed: list[dict[str, str]],
    blockers: list[str],
) -> str:
    if failed or blockers:
        return READINESS_NOT_READY
    if report.get("operator_review_completed") is True and not report.get(
        "remaining_approval_requirements",
    ):
        return READINESS_ELIGIBLE_FOR_PROPOSAL
    return READINESS_REVIEW_REQUIRED


def _contains_secret_values(value: Any) -> bool:
    serialized = json.dumps(value, sort_keys=True, default=str).lower()
    return any(marker in serialized for marker in _SENSITIVE_VALUE_MARKERS)


def _json_safe(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, sort_keys=True, default=str))


def _checklist_id(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"EVCHECK-{digest}"


__all__ = [
    "READINESS_ELIGIBLE_FOR_PROPOSAL",
    "READINESS_NOT_READY",
    "READINESS_REVIEW_REQUIRED",
    "RUNTIME_EVENT_PERSISTENCE_CHECKLIST_VERSION",
    "RuntimeEventPersistenceChecklist",
    "build_runtime_event_persistence_checklist",
]
